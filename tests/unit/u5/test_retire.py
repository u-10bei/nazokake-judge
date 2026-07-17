"""U5 単体（example）: 契約・ワイヤリング・充足母数。

**責務の境界**: SQL の意味論（retire の冪等性・export の items 集合・凍結ガード非適用）は
**実 D1 の integration が正**（`tests/integration/drive_u5.py` = PU5-3 / PU5-4）。ここでは
D1 なしで確かめられる契約とワイヤリングを固定する。
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from backend.domain import pool_sufficiency
from backend.participant.session import get_likert_targets, start_or_resume
from schema import (
    AssignmentParams,
    Item,
    ItemRetireRequest,
    Layer,
    RetireResult,
    Session,
    Token,
)
from tests.fakes import FakeRepo

LAYERS = list(Layer)


def _pool(n: int = 20) -> list[Item]:
    return [Item(item_id=f"it{i:03d}", layer=LAYERS[i % 4], body=f"b{i}", body_ref=None)
            for i in range(n)]


def _params() -> AssignmentParams:
    return AssignmentParams(session_pairs=6, practice_pairs=2, likert_items=3,
                            cross_layer_min_ratio=0.65, max_item_occurrence_k=3)


# --------------------------------------------------------------- ペイロード契約
def test_retire_request_requires_at_least_one_item():
    """`item_ids` は 1 件以上（空リクエストは検証エラー → API は 400）。"""
    with pytest.raises(ValidationError):
        ItemRetireRequest(item_ids=[])


def test_retire_request_rejects_retired_at_from_client():
    """クライアントは `retired_at` を指定できない（廃止時刻はサーバが決める）。"""
    with pytest.raises(ValidationError):
        ItemRetireRequest.model_validate({"item_ids": ["a"], "retired_at": "2026-01-01"})


def test_item_contract_has_no_retired_at():
    """🔒 `Item`（投入契約）に `retired_at` を持たせない（BR-U5-12 / DP-U5-04）。

    → `pool_ingest` の経路から廃止・復活が**構造的に不可能**（ガードの穴を型で塞ぐ）。
    """
    assert "retired_at" not in Item.model_fields
    with pytest.raises(ValidationError):
        Item.model_validate({"item_id": "a", "layer": "pro", "body": "b",
                             "retired_at": "2026-01-01"})


def test_retire_result_defaults():
    r = RetireResult(ok=True)
    assert r.retired == 0 and r.already_retired == [] and r.not_found == []


# --------------------------------------------------------------- ワイヤリング
def test_new_session_excludes_retired_from_pairs_and_likert():
    """新規セッションは廃止 item をペア列・練習・Likert から除く（BR-U5-02a/02b）。"""
    items = _pool()
    retired = {"it000", "it001"}
    repo = FakeRepo(items, retired)
    token = "tok-a"
    repo.tokens[token] = Token(token=token, status="unused", issued_at="2026-07-17T00:00:00Z")

    asyncio.run(start_or_resume(repo, token, _params()))

    for p in repo.pairs[token]:
        assert p.item_left not in retired and p.item_right not in retired
    assert all(t not in retired for t in repo.sessions[token].likert_targets)


def test_build_view_bodies_resolve_retired_items_for_in_progress_session():
    """進行中セッションのペア列が廃止 item を含んでも `bodies` が解決できる（BR-U5-02a ④）。

    `build_view` の `bodies` は **全件**（`list_items()`）で作る。ここを active に絞ると
    進行中セッションの画面が壊れる（＝「新規のみ反映」の要件が守れない）。
    """
    items = _pool()
    repo = FakeRepo(items, retired={"it000"})
    # list_items（全件）には廃止 item が残る＝bodies が解決できる。
    all_ids = {i.item_id for i in asyncio.run(repo.list_items())}
    active_ids = {i.item_id for i in asyncio.run(repo.list_active_items())}
    assert "it000" in all_ids
    assert "it000" not in active_ids


def test_legacy_session_likert_falls_back_to_all_items():
    """旧セッション（`likert_targets IS NULL`）は全件から導出＝従来挙動（BR-U5-04）。"""
    items = _pool()
    repo = FakeRepo(items)
    token = "tok-legacy"
    repo.sessions[token] = Session(token=token, seed=7, exposure_snapshot={},
                                   created_at="2026-07-17T00:00:00Z", likert_targets=None)
    before = asyncio.run(get_likert_targets(repo, token, _params()))
    repo.retire("it000", "it001")
    after = asyncio.run(get_likert_targets(repo, token, _params()))
    assert before == after


def test_stored_targets_are_returned_verbatim():
    """保存済みセッションは保存値をそのまま返す（導出し直さない）。"""
    repo = FakeRepo(_pool())
    token = "tok-stored"
    stored = ["it005", "it003", "it001"]        # 順序も保持（提示順が意味を持つ）
    repo.sessions[token] = Session(token=token, seed=1, exposure_snapshot={},
                                   created_at="2026-07-17T00:00:00Z", likert_targets=stored)
    assert asyncio.run(get_likert_targets(repo, token, _params())) == stored


# --------------------------------------------------------------- 充足母数（BR-U5-09）
def test_sufficiency_uses_active_pool_only():
    """充足判定の母数は現役のみ。廃止でゲートを割ったら発行拒否が正しい（BR-U5-09）。"""
    params = AssignmentParams()             # 本番既定（総数 >= 27 / 4 層非空 / 層間供給）
    items = _pool(30)                       # 30 件なら充足
    repo = FakeRepo(items)

    all_items = asyncio.run(repo.list_items())
    assert pool_sufficiency(all_items, params).ok

    # 4 件廃止 → 現役 26 件 → 総数不足（27 未満）で発行拒否になるべき。
    repo.retire("it000", "it001", "it002", "it003")
    active = asyncio.run(repo.list_active_items())
    assert len(active) == 26
    result = pool_sufficiency(active, params)
    assert not result.ok
    assert any("総数不足" in s for s in result.shortfalls)
    # 全件で判定してしまうと「発行できるが割当が破綻する」状態になる（不採用の実証）。
    assert pool_sufficiency(all_items, params).ok
