"""nazokake-judge smoke test worker — variant B (FastAPI なし).

deploy 時検証エラー 10021 (startup CPU 1757ms > 1000ms) を受けた切り分け用。
FastAPI を外し、workers 標準 API + 手動ルーティング + Pydantic のみで構成する。
これが通れば「重いのは FastAPI の import」と確定し、本実装のフレームワーク選定
(TSD-01) を「raw workers API + Pydantic」へ更新する判断材料になる。

検証項目の対応:
  1. python_workers ブート          (応答があること)
  2. HTTP ルーティング              (raw workers API。FastAPI は 10021 のため除外)
  3. Pydantic v2 import/validate    (TSD-02)
  4. D1 binding                     (R-1/R-2)
  5. D1 batch 原子性 + ON CONFLICT  (DP-01/DP-02)
"""

import json
import time
from urllib.parse import urlparse

import pydantic
from pydantic import BaseModel, Field, ValidationError
from workers import Response


def _to_py(obj):
    try:
        return obj.to_py()
    except AttributeError:
        return obj


def _to_js_maybe(x):
    try:
        from pyodide.ffi import to_js
        return to_js(x)
    except Exception:
        return x


class SmokeModel(BaseModel):
    name: str = Field(min_length=1)
    count: int = Field(ge=0)


async def smoke_routing():
    return {"item": "2-http-routing", "pass": True,
            "detail": "raw workers API のルーティングが応答 (FastAPI は 10021 のため除外)"}


async def smoke_pydantic():
    detail = {"pydantic_version": pydantic.VERSION}
    ok = pydantic.VERSION.startswith("2")
    detail["is_v2"] = ok
    m = SmokeModel(name="usu", count=3)
    detail["valid_roundtrip"] = m.model_dump()
    try:
        SmokeModel(name="", count=-1)
        detail["invalid_rejected"] = False
        ok = False
    except ValidationError:
        detail["invalid_rejected"] = True
    return {"item": "3-pydantic-v2", "pass": ok, "detail": detail}


async def smoke_d1(env):
    detail = {}
    try:
        one = await env.DB.prepare("SELECT 1 AS one").first("one")
        detail["select1"] = _to_py(one)
        marker = f"smoke-{int(time.time() * 1000)}"
        await env.DB.prepare("INSERT INTO smoke_items (name) VALUES (?)").bind(marker).run()
        row = await env.DB.prepare(
            "SELECT name FROM smoke_items WHERE name = ?").bind(marker).first("name")
        detail["insert_select_roundtrip"] = (_to_py(row) == marker)
        ok = detail["select1"] == 1 and detail["insert_select_roundtrip"]
        return {"item": "4-d1-binding", "pass": ok, "detail": detail}
    except Exception as e:  # noqa: BLE001
        detail["error"] = repr(e)
        return {"item": "4-d1-binding", "pass": False, "detail": detail}


async def smoke_d1_batch(env):
    detail = {}
    marker = f"batch-{int(time.time() * 1000)}"
    try:
        stmts = [
            env.DB.prepare("INSERT INTO smoke_items (name) VALUES (?)").bind(f"{marker}-a"),
            env.DB.prepare("INSERT INTO smoke_items (name) VALUES (?)").bind(f"{marker}-b"),
        ]
        await env.DB.batch(_to_js_maybe(stmts))
        cnt = await env.DB.prepare(
            "SELECT COUNT(*) AS c FROM smoke_items WHERE name LIKE ?"
        ).bind(f"{marker}-%").first("c")
        commit_ok = (_to_py(cnt) == 2)
        detail["batch_commit"] = commit_ok

        raised = False
        try:
            bad = [
                env.DB.prepare("INSERT INTO smoke_items (name) VALUES (?)").bind(
                    f"{marker}-should-rollback"),
                env.DB.prepare("INSERT INTO smoke_items (name) VALUES (NULL)"),
            ]
            await env.DB.batch(_to_js_maybe(bad))
        except Exception:  # noqa: BLE001
            raised = True
        leftover = await env.DB.prepare(
            "SELECT COUNT(*) AS c FROM smoke_items WHERE name = ?"
        ).bind(f"{marker}-should-rollback").first("c")
        rollback_ok = raised and (_to_py(leftover) == 0)
        detail["failing_batch_raised"] = raised
        detail["rollback_ok"] = rollback_ok

        sql = ("INSERT INTO smoke_judgments (token, pair_id, choice) "
               "VALUES (?, ?, ?) ON CONFLICT(token, pair_id) DO NOTHING")
        await env.DB.prepare(sql).bind(marker, "p1", "A").run()
        await env.DB.prepare(sql).bind(marker, "p1", "B").run()
        kept = await env.DB.prepare(
            "SELECT choice FROM smoke_judgments WHERE token = ? AND pair_id = ?"
        ).bind(marker, "p1").first("choice")
        upsert_ok = (_to_py(kept) == "A")
        detail["conflict_keeps_first"] = upsert_ok

        return {"item": "5-d1-batch", "pass": commit_ok and rollback_ok and upsert_ok,
                "detail": detail}
    except Exception as e:  # noqa: BLE001
        detail["error"] = repr(e)
        return {"item": "5-d1-batch", "pass": False, "detail": detail}


async def smoke_all(env):
    results = [
        {"item": "1-worker-boot", "pass": True,
         "detail": "この応答が返っている時点で python_workers での起動は成功"},
        await smoke_routing(),
        await smoke_pydantic(),
        await smoke_d1(env),
        await smoke_d1_batch(env),
    ]
    return {"overall_pass": all(r["pass"] for r in results), "results": results}


def _json_response(body):
    return Response(json.dumps(body, ensure_ascii=False))


async def on_fetch(request, env):
    try:
        path = urlparse(request.url).path
        if path == "/smoke/all":
            return _json_response(await smoke_all(env))
        if path == "/smoke/routing":
            return _json_response(await smoke_routing())
        if path == "/smoke/pydantic":
            return _json_response(await smoke_pydantic())
        if path == "/smoke/d1":
            return _json_response(await smoke_d1(env))
        if path == "/smoke/d1-batch":
            return _json_response(await smoke_d1_batch(env))
        return _json_response({"smoke_endpoints": [
            "/smoke/all", "/smoke/routing", "/smoke/pydantic",
            "/smoke/d1", "/smoke/d1-batch"]})
    except Exception as e:  # noqa: BLE001
        import traceback
        return Response("SMOKE-ERROR: " + repr(e) + "\n" + traceback.format_exc())
