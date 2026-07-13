"""U1 Repository の実 D1 統合テスト worker（Build & Test）。

純粋ロジック（domain/schema/serializer）は PBT で検証済み。ここでは Repository を
**実 D1（miniflare/本番同型ランタイム）**に対して実行し、実 DDL（migrations/0001_init.sql）
の下で以下を検証する:

  1. save_pair_sequence: Session + PairSequence を単一 batch で原子コミット（DP-01）
  2. save_pair_sequence 原子性: batch 途中失敗で全ロールバック（半端ペア列を残さない）
  3. insert_judgment: ON CONFLICT DO NOTHING + 既存 choice 返却で冪等（DP-02）
  4. read_exposure_counts: derive_exposure と一致（H-2, 非アクティブ除外込み）

`GET /run` が全シナリオを実行し overall_pass と項目別 PASS/FAIL を JSON で返す。
raw workers API + module-level on_fetch（F-4/F-5）。schema/backend は本 dir に隔離コピー。
"""

from __future__ import annotations

import json

from workers import Response

from backend.domain import generate_pairs, updated_exposure
from backend.repo import Repository
from backend.repo._d1 import to_py
from schema import AssignmentParams, Item, Layer, Session

NOW = "2026-07-13T00:00:00Z"


async def _reset(env):
    for table in ("judgments", "pairs", "sessions", "likert_responses",
                  "survey_responses", "tokens", "items"):
        await env.DB.prepare(f"DELETE FROM {table}").run()


async def _seed_items(env) -> list[Item]:
    layers = list(Layer)
    pool = [Item(item_id=f"it{i:03d}", layer=layers[i % 4], body_ref=f"ref{i}")
            for i in range(8)]
    for it in pool:
        await env.DB.prepare(
            "INSERT INTO items (item_id, layer, body_ref) VALUES (?, ?, ?)"
        ).bind(it.item_id, it.layer.value, it.body_ref).run()
    return pool


async def _insert_token(env, token: str):
    await env.DB.prepare(
        "INSERT INTO tokens (token, status, issued_at, last_active_at) "
        "VALUES (?, 'unused', ?, NULL)"
    ).bind(token, NOW).run()


async def _count(env, sql, *binds) -> int:
    stmt = env.DB.prepare(sql)
    if binds:
        stmt = stmt.bind(*binds)
    return to_py(await stmt.first("c"))


async def scenario_save_commit(env):
    repo = Repository(env.DB)
    pool = await _seed_items(env)
    await _insert_token(env, "tok_commit")
    params = AssignmentParams(session_pairs=4, practice_pairs=1, max_item_occurrence_k=3)
    pairs = generate_pairs(pool, {}, seed=7, params=params)
    session = Session(token="tok_commit", seed=7, exposure_snapshot={}, created_at=NOW)
    await repo.save_pair_sequence(session, pairs)

    saved_pairs = await _count(env, "SELECT COUNT(*) AS c FROM pairs WHERE token = ?", "tok_commit")
    has_session = await _count(env, "SELECT COUNT(*) AS c FROM sessions WHERE token = ?", "tok_commit")
    ok = saved_pairs == len(pairs) and has_session == 1 and len(pairs) > 0
    return {"item": "1-save-commit", "pass": ok,
            "detail": {"generated": len(pairs), "saved_pairs": saved_pairs, "session_rows": has_session}}


async def scenario_save_atomic_rollback(env):
    """pair_id 重複（PK 違反）で batch が途中失敗 → Session ごと全ロールバック。"""
    repo = Repository(env.DB)
    await _insert_token(env, "tok_rb")
    pool = await env.DB.prepare("SELECT item_id FROM items LIMIT 2").all()
    ids = [r["item_id"] for r in to_py(pool)["results"]]
    from schema import Pair
    dup_pairs = [
        Pair(pair_id="dup", index=0, item_left=ids[0], item_right=ids[1]),
        Pair(pair_id="dup", index=1, item_left=ids[1], item_right=ids[0]),  # PK 重複
    ]
    session = Session(token="tok_rb", seed=1, exposure_snapshot={}, created_at=NOW)
    raised = False
    try:
        await repo.save_pair_sequence(session, dup_pairs)
    except Exception:  # noqa: BLE001
        raised = True
    leftover_pairs = await _count(env, "SELECT COUNT(*) AS c FROM pairs WHERE token = ?", "tok_rb")
    leftover_session = await _count(env, "SELECT COUNT(*) AS c FROM sessions WHERE token = ?", "tok_rb")
    ok = raised and leftover_pairs == 0 and leftover_session == 0
    return {"item": "2-save-atomic-rollback", "pass": ok,
            "detail": {"raised": raised, "leftover_pairs": leftover_pairs, "leftover_session": leftover_session}}


async def scenario_judgment_idempotent(env):
    repo = Repository(env.DB)
    first = await repo.insert_judgment("tok_commit", "p001", "A", NOW)
    second = await repo.insert_judgment("tok_commit", "p001", "B", NOW)  # 重複 → 無視
    rows = await _count(env, "SELECT COUNT(*) AS c FROM judgments WHERE token = ? AND pair_id = ?",
                        "tok_commit", "p001")
    ok = first == "A" and second == "A" and rows == 1
    return {"item": "3-judgment-idempotent", "pass": ok,
            "detail": {"first": first, "second_returns_kept": second, "rows": rows}}


async def scenario_read_exposure(env):
    """save 済み tok_commit を in_progress+active にして露出集計 == updated_exposure。"""
    repo = Repository(env.DB)
    await repo.mark_token_in_progress("tok_commit", NOW)  # unused → in_progress
    await repo.touch_token("tok_commit", NOW)
    # DB 上の確定ペア列を復元してオラクル比較。
    pair_rows = to_py(await env.DB.prepare(
        "SELECT pair_id, idx, item_left, item_right, is_practice FROM pairs WHERE token = ?"
    ).bind("tok_commit").all())["results"]
    from schema import Pair
    pairs = [Pair(pair_id=r["pair_id"], index=r["idx"], item_left=r["item_left"],
                  item_right=r["item_right"], is_practice=bool(r["is_practice"])) for r in pair_rows]
    oracle = updated_exposure({}, pairs)
    derived = await repo.read_exposure_counts(now_iso=NOW, inactive_threshold_hours=48)
    ok = derived == oracle and sum(oracle.values()) > 0
    return {"item": "4-read-exposure", "pass": ok,
            "detail": {"oracle": oracle, "derived": derived}}


async def run_all(env):
    await _reset(env)
    results = [
        await scenario_save_commit(env),
        await scenario_save_atomic_rollback(env),
        await scenario_judgment_idempotent(env),
        await scenario_read_exposure(env),
    ]
    return {"overall_pass": all(r["pass"] for r in results), "results": results}


async def on_fetch(request, env):
    try:
        from urllib.parse import urlparse
        if urlparse(request.url).path == "/run":
            body = await run_all(env)
            return Response(json.dumps(body, ensure_ascii=False),
                            headers={"content-type": "application/json"})
        return Response(json.dumps({"endpoints": ["/run"]}))
    except Exception as e:  # noqa: BLE001
        import traceback
        return Response("IT-ERROR: " + repr(e) + "\n" + traceback.format_exc())
