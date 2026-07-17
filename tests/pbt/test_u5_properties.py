"""U5 出題停止の不変条件（PBT-03 が主 / PBT-02 も新たに該当, U5-NFR-05/06/07）。

**要件の両輪それぞれに独立した網を張る**（BR-U5-02 の禁止事項を踏んだら落ちる）:
  - **PU5-1**: 廃止済み item は**新規セッション**のペア列・練習・Likert に現れない。
  - **PU5-2**（**「新規のみ反映」の網**）: 旧セッション（`likert_targets IS NULL`）の
    Likert ターゲットは**廃止の前後で不変**。
  - **PBT-02**: `likert_targets` の JSON ラウンドトリップ（**順序を含めて一致**）。

**PU5-3（retire 冪等）/ PU5-4（export の items 集合が不変）は SQL の意味論**ゆえ
**実 D1 の integration が正**（`tests/integration/drive_u5.py`）。ダブルで再現しても
ダブルを検証することにしかならない。

ジェネレータは **廃止済み/現役が混在するプール**を生成する（U5-NFR-06。「廃止ゼロ件だけを
引くジェネレータでは反例探索が空回りする」＝U4b で単調性ジェネレータの適用範囲を誤った教訓）。
"""

from __future__ import annotations

import asyncio
import json

from hypothesis import given
from hypothesis import strategies as st

from backend.participant.session import get_likert_targets, start_or_resume
from schema import AssignmentParams, Item, Layer, Session, Token
from tests.fakes import FakeRepo

LAYERS = list(Layer)


@st.composite
def pool_with_retired(draw):
    """**廃止済み/現役が混在する**プールを生成する（U5-NFR-06）。

    4 層すべてを含み、現役だけでペア構成が可能な規模を保ちつつ、廃止件数を 0〜数件で振る
    （0 件も含めるのは「廃止なしでも壊れない」ことの確認のため。ただし 1 件以上を主に引く）。
    """
    n = draw(st.integers(min_value=16, max_value=28))
    items = [
        Item(item_id=f"it{i:03d}", layer=LAYERS[i % len(LAYERS)],
             body=f"body{i:03d}", body_ref=None)
        for i in range(n)
    ]
    ids = [it.item_id for it in items]
    # 廃止は最大でもプールの 1/4 まで（現役だけでペアが組める規模を維持）。
    k = draw(st.integers(min_value=0, max_value=max(1, n // 4)))
    retired = set(draw(st.lists(st.sampled_from(ids), min_size=k, max_size=k, unique=True)))
    return items, retired


def _params() -> AssignmentParams:
    # 小さめのプールでも構成可能なパラメータ（本番既定 40 ペアは 16 件プールには過大）。
    return AssignmentParams(session_pairs=6, practice_pairs=2, likert_items=3,
                            cross_layer_min_ratio=0.65, max_item_occurrence_k=3)


# ------------------------------------------------ PU5-1 新規セッションから消える
@given(pool_with_retired())
def test_pu5_1_retired_absent_from_new_session(data):
    """廃止済み item は新規セッションの**ペア列・練習・Likert のいずれにも現れない**。

    ワイヤリングの検証: `start_or_resume` が `list_active_items()` を使っていなければ落ちる。
    """
    items, retired = data
    repo = FakeRepo(items, retired)
    token = "tok-u5-1"
    repo.tokens[token] = Token(token=token, status="unused", issued_at="2026-07-17T00:00:00Z")

    asyncio.run(start_or_resume(repo, token, _params()))

    session = repo.sessions[token]
    pairs = repo.pairs[token]
    # ペア列（本番・練習の両方。練習は generate_pairs の同一呼び出し由来, BR-U5-02b）。
    for p in pairs:
        assert p.item_left not in retired, f"廃止 item がペアに出た: {p.item_left}"
        assert p.item_right not in retired, f"廃止 item がペアに出た: {p.item_right}"
    # Likert ターゲット（開始時確定・保存済み）。
    assert session.likert_targets is not None, "新規セッションは likert_targets を保存する"
    for t in session.likert_targets:
        assert t not in retired, f"廃止 item が Likert 対象に出た: {t}"


# --------------------------------- PU5-2 旧セッションは不変（「新規のみ反映」の網）
@given(pool_with_retired())
def test_pu5_2_legacy_session_likert_unchanged_by_retire(data):
    """`likert_targets IS NULL` の旧セッションは**廃止の前後で Likert ターゲットが一致**。

    フォールバックが `list_items()`（全件）から導出していなければ落ちる
    ＝**「新規のみ反映」の直接の検出網**（BR-U5-02 / BR-U5-04）。
    """
    items, retired = data
    repo = FakeRepo(items, retired=set())  # まだ何も廃止していない
    token = "tok-u5-2"
    # U5 以前に開始したセッションを模す（likert_targets=None）。
    repo.sessions[token] = Session(
        token=token, phase="likert", seed=12345,
        exposure_snapshot={}, created_at="2026-07-17T00:00:00Z",
        likert_targets=None,
    )
    params = _params()

    before = asyncio.run(get_likert_targets(repo, token, params))
    repo.retire(*retired)                       # ここで廃止が起きる
    after = asyncio.run(get_likert_targets(repo, token, params))

    assert before == after, "旧セッションの Likert ターゲットは廃止の影響を受けない"


@given(pool_with_retired())
def test_pu5_2b_stored_session_likert_unchanged_by_retire(data):
    """保存済み（U5 以降）のセッションも廃止の前後で不変（保存値をそのまま返す）。"""
    items, retired = data
    repo = FakeRepo(items, retired=set())
    token = "tok-u5-2b"
    stored = [it.item_id for it in items[:3]]
    repo.sessions[token] = Session(
        token=token, phase="likert", seed=1, exposure_snapshot={},
        created_at="2026-07-17T00:00:00Z", likert_targets=stored,
    )
    params = _params()

    before = asyncio.run(get_likert_targets(repo, token, params))
    repo.retire(*retired)
    after = asyncio.run(get_likert_targets(repo, token, params))

    assert before == after == stored


# ------------------------------------------------ PBT-02 ラウンドトリップ
def _roundtrip(session: Session) -> Session:
    """Repository の保存/復元と同じイディオム（save_pair_sequence / get_session 相当）。"""
    # 保存側: None は SQL リテラル NULL（D1 は Python None の bind を拒否するため）。
    raw = json.dumps(session.likert_targets) if session.likert_targets is not None else None
    # 復元側: `[]`（対象なし確定）と NULL（旧セッション）を混同しないため `is not None`。
    restored = json.loads(raw) if raw is not None else None
    d = session.model_dump()
    d["likert_targets"] = restored
    return Session.model_validate(d)


@given(st.lists(st.text(min_size=1, max_size=12), min_size=0, max_size=10))
def test_pbt02_likert_targets_json_roundtrip(targets):
    """`likert_targets` の JSON 保存/復元が**順序を含めて一致**する（U5-NFR-07）。

    順序は提示順として意味を持つため保存されなければならない。**空配列も `[]` のまま**
    復元されること（下記 None との区別を参照）。
    """
    back = _roundtrip(Session(token="t", seed=1, created_at="2026-07-17T00:00:00Z",
                              likert_targets=targets))
    assert back.likert_targets == targets       # 順序を含めて一致（[] も [] のまま）


def test_pbt02_empty_list_and_none_are_distinct():
    """`[]`（Likert 対象なしが確定）と `None`（旧セッション）を**混同しない**。

    `[]` を None に潰すと `get_likert_targets` が全件導出フォールバックに落ち、
    **本来ないはずの Likert 対象が生える**（BR-U5-04 の保証が壊れる）。
    """
    empty = _roundtrip(Session(token="t", seed=1, created_at="2026-07-17T00:00:00Z",
                               likert_targets=[]))
    legacy = _roundtrip(Session(token="t", seed=1, created_at="2026-07-17T00:00:00Z",
                                likert_targets=None))
    assert empty.likert_targets == []       # 対象なしが確定済み → フォールバックしない
    assert legacy.likert_targets is None    # 未保存 → 全件導出にフォールバックする
    assert empty.likert_targets != legacy.likert_targets


def test_get_likert_targets_respects_empty_stored_list():
    """保存値が `[]` のセッションは**フォールバックせず空を返す**（[] と None の区別の実効）。"""
    items = [Item(item_id=f"it{i:03d}", layer=LAYERS[i % 4], body="b", body_ref=None)
             for i in range(8)]
    repo = FakeRepo(items)
    token = "tok-empty"
    repo.sessions[token] = Session(token=token, seed=1, exposure_snapshot={},
                                   created_at="2026-07-17T00:00:00Z", likert_targets=[])
    assert asyncio.run(get_likert_targets(repo, token, _params())) == []
