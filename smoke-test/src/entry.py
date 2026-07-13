"""nazokake-judge smoke test worker.

目的: U1 Infrastructure Design §2 の R-1 先行検証 (Q1=A)。
検証項目 (infrastructure-design.md §2 と 1:1 対応):
  1. python_workers flag で Worker が起動する
  2. FastAPI (ASGI) がルーティングに応答する
  3. Pydantic v2 が import/validate できる (TSD-02)
  4. D1 binding 経由の最小クエリが成功する
  5. D1 batch の原子性 + ON CONFLICT DO NOTHING (DP-01/DP-02, R-2)

GET /smoke/all が全項目を実行し PASS/FAIL の JSON を返す。
このコードは使い捨て。本実装 (U1 Code Generation) には流用しない。
"""

import time

from fastapi import FastAPI, Request

import pydantic
from pydantic import BaseModel, Field, ValidationError

app = FastAPI()


# ---------------------------------------------------------------- helpers

def _to_py(obj):
    """JsProxy → Python 値。既に Python 値ならそのまま返す。"""
    try:
        return obj.to_py()
    except AttributeError:
        return obj


def _get_env(request: Request):
    """env バインディングの取得。runtime のバージョン差に備え 2 経路を試す。"""
    env = request.scope.get("env")
    if env is not None:
        return env
    # 新しめの runtime はグローバル import を提供する
    from workers import env as global_env  # type: ignore
    return global_env


def _to_js_maybe(x):
    """D1.batch は JS 配列を期待するため可能なら変換。"""
    try:
        from pyodide.ffi import to_js
        return to_js(x)
    except Exception:
        return x


# ---------------------------------------------------------- item 3: pydantic

class SmokeModel(BaseModel):
    """Pydantic v2 検証用の最小モデル。"""
    name: str = Field(min_length=1)
    count: int = Field(ge=0)


@app.get("/smoke/fastapi")
async def smoke_fastapi():
    return {"item": "2-fastapi-routing", "pass": True,
            "detail": "FastAPI ルーティングが応答"}


@app.get("/smoke/pydantic")
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


# ---------------------------------------------------------- item 4: d1 binding

@app.get("/smoke/d1")
async def smoke_d1(request: Request):
    detail = {}
    try:
        env = _get_env(request)
        one = await env.DB.prepare("SELECT 1 AS one").first("one")
        detail["select1"] = _to_py(one)

        marker = f"smoke-{int(time.time() * 1000)}"
        await env.DB.prepare(
            "INSERT INTO smoke_items (name) VALUES (?)"
        ).bind(marker).run()
        row = await env.DB.prepare(
            "SELECT name FROM smoke_items WHERE name = ?"
        ).bind(marker).first("name")
        detail["insert_select_roundtrip"] = (_to_py(row) == marker)

        ok = detail["select1"] == 1 and detail["insert_select_roundtrip"]
        return {"item": "4-d1-binding", "pass": ok, "detail": detail}
    except Exception as e:  # noqa: BLE001 - smoke test は全例外を報告
        detail["error"] = repr(e)
        return {"item": "4-d1-binding", "pass": False, "detail": detail}


# ------------------------------------------- item 5: d1 batch + on conflict

@app.get("/smoke/d1-batch")
async def smoke_d1_batch(request: Request):
    detail = {}
    marker = f"batch-{int(time.time() * 1000)}"
    try:
        env = _get_env(request)

        # (5a) 正常 batch: 2 件が両方コミットされる
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

        # (5b) 原子性: 2 文目が NOT NULL 違反 → batch 全体がロールバックされるべき
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

        # (5c) DP-02 セマンティクス: ON CONFLICT DO NOTHING が既存を維持する
        sql = ("INSERT INTO smoke_judgments (token, pair_id, choice) "
               "VALUES (?, ?, ?) ON CONFLICT(token, pair_id) DO NOTHING")
        await env.DB.prepare(sql).bind(marker, "p1", "A").run()
        await env.DB.prepare(sql).bind(marker, "p1", "B").run()  # 重複 → 無視されるべき
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


# ----------------------------------------------------------------- aggregate

@app.get("/smoke/all")
async def smoke_all(request: Request):
    results = [
        {"item": "1-worker-boot", "pass": True,
         "detail": "この応答が返っている時点で python_workers での起動は成功"},
        await smoke_fastapi(),
        await smoke_pydantic(),
        await smoke_d1(request),
        await smoke_d1_batch(request),
    ]
    return {"overall_pass": all(r["pass"] for r in results), "results": results}


@app.get("/")
async def root():
    return {"smoke_endpoints": ["/smoke/all", "/smoke/fastapi", "/smoke/pydantic",
                                "/smoke/d1", "/smoke/d1-batch"]}


# NOTE: workers-py 1.15.0 (open beta) のデフォルト fetch ハンドラは
# **モジュールレベルの `on_fetch(request, env, ctx)`** で定義する。
# クラスベース `WorkerEntrypoint.fetch`/`.on_fetch` はデフォルトとして認識されず
# "Method on_fetch does not exist" になる。2026-07-12 検証で確定した beta API ドリフト。
async def on_fetch(request, env, ctx):
    import asgi
    return await asgi.fetch(app, request, env)
