"""U6 単体（example）: 層フィルタ・引き当て・★Likert 配線・補充トークン。

**責務の境界**（U5 と同じ）: SQL の意味論（プラン投入・activate ガード・0005 の適用）は
**実 D1 の integration が正**（`tests/integration/drive_u6.py`）。ここでは D1 なしで
確かめられる**契約とワイヤリング**を固定する。
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from backend.domain import pool_sufficiency
from backend.participant.session import start_or_resume
from schema import (
    POOL_LAYERS,
    REQUIRED_LAYERS,
    AssignmentParams,
    Item,
    Layer,
    Pair,
    PlanIngestRequest,
    Token,
)
from tests.fakes import FakeRepo


def _pool(counts: dict[Layer, int]) -> list[Item]:
    out, i = [], 0
    for layer, n in counts.items():
        for _ in range(n):
            out.append(Item(item_id=f"{layer.value}{i:03d}", layer=layer,
                            body=f"b{i}", body_ref=None))
            i += 1
    return out


def _params(**kw) -> AssignmentParams:
    base = dict(session_pairs=6, practice_pairs=2, likert_items=3,
                cross_layer_min_ratio=0.65, max_item_occurrence_k=3)
    base.update(kw)
    return AssignmentParams(**base)


# ------------------------------------------------- 層の用途別リスト（BR-U6-05）
def test_pool_layers_excludes_practice_required_excludes_anchor():
    """`POOL_LAYERS`（母数）は `practice` を除き、`REQUIRED_LAYERS`（非空要求）は
    `anchor` を除く——**両者は別概念**（BR-U6-05）。"""
    assert Layer.PRACTICE not in POOL_LAYERS
    assert Layer.ANCHOR in POOL_LAYERS          # 母数には入る（層間ペアの相手になる）
    assert Layer.ANCHOR not in REQUIRED_LAYERS  # 非空は要求しない（研究上の要請）
    assert set(REQUIRED_LAYERS) == {Layer.PRO, Layer.AI, Layer.EDIT, Layer.RULE}


def test_sufficiency_practice_is_out_of_denominator():
    """`practice` を大量に足しても**充足の母数に入らない**（BR-U6-05）。"""
    p = AssignmentParams()
    base = _pool({Layer.PRO: 10, Layer.ANCHOR: 2, Layer.EDIT: 14,
                  Layer.AI: 9, Layer.RULE: 3})
    assert pool_sufficiency(base, p).ok
    # 練習素材を 50 件足しても判定は変わらない（母数外）
    padded = base + _pool({Layer.PRACTICE: 50})
    assert pool_sufficiency(padded, p).ok
    # 逆に本番層を削れば落ちる（母数が効いている証拠）
    thin = _pool({Layer.PRO: 3, Layer.ANCHOR: 1, Layer.EDIT: 3, Layer.AI: 3, Layer.RULE: 2})
    assert not pool_sufficiency(thin, p).ok


def test_sufficiency_passes_without_anchor():
    """★`anchor` 不在でもゲートは落ちない（ドライラン・将来の構成変更, BR-U6-05）。

    `anchor` の投入忘れは `plan_generate` の期待組成チェックで検出する（BR-U6-22）。
    """
    p = AssignmentParams()
    no_anchor = _pool({Layer.PRO: 10, Layer.EDIT: 14, Layer.AI: 9, Layer.RULE: 5})
    r = pool_sufficiency(no_anchor, p)
    assert r.ok, r.shortfalls


# --------------------------------------------------- プラン引き当て（LC-U6-10）
def _plan_repo(*, likert_targets, n_prod=6):
    pool = _pool({Layer.PRO: 4, Layer.ANCHOR: 2, Layer.EDIT: 5, Layer.AI: 4, Layer.RULE: 3})
    ids = [it.item_id for it in pool]
    repo = FakeRepo(pool)
    rows = [Pair(pair_id="p0000", index=0, item_left=ids[0], item_right=ids[1],
                 is_practice=True)]
    rows += [Pair(pair_id=f"p{i:04d}", index=i, item_left=ids[i % len(ids)],
                  item_right=ids[(i + 5) % len(ids)]) for i in range(1, n_prod + 1)]
    repo.plans = {"primary": {0: rows}}
    repo.plan_meta = {"primary": {"n_slots": 8, "likert_targets": list(likert_targets)}}
    repo.active_plan_set = "primary"
    return repo, pool, ids


def test_plan_path_uses_plan_pairs_not_generation():
    """プラン経路では**プラン記載のペア列がそのまま**保存される（実行時に抽選しない）。"""
    repo, _, _ = _plan_repo(likert_targets=[])
    repo.plan_bindings = {"tk": ("primary", 0)}
    repo.tokens["tk"] = Token(token="tk", status="unused", issued_at="2026-07-20T00:00:00Z")
    asyncio.run(start_or_resume(repo, "tk", _params()))
    saved = repo.pairs["tk"]
    expected = repo.plans["primary"][0]
    assert [p.pair_id for p in saved] == [p.pair_id for p in expected]
    assert saved[0].is_practice and saved[0].index == 0     # 練習が先頭（BR-U6-16）


def test_plan_path_likert_uses_fixed_list():
    """★**Likert がプラン記載の固定リストと一致**する（BR-U6-06 / FD Q2=D）。

    **これがラウンドロビンに落ちていないことの直接の検出網**。配線がないと
    `api.py` の `AssignmentParams()` 既定（`likert_fixed_targets=None`）のまま
    `select_likert_targets` が走り、**5 層ラウンドロビン**にフォールバックする
    ＝FD Q2 で否決した挙動が本番経路で復活する。
    """
    repo, _, ids = _plan_repo(likert_targets=[])
    fixed = [ids[7], ids[3], ids[11], ids[1], ids[15]]      # 順序も意味を持つ
    repo.plan_meta["primary"]["likert_targets"] = fixed
    repo.plan_bindings = {"tk": ("primary", 0)}
    repo.tokens["tk"] = Token(token="tk", status="unused", issued_at="2026-07-20T00:00:00Z")

    asyncio.run(start_or_resume(repo, "tk", _params(likert_items=len(fixed))))
    assert repo.sessions["tk"].likert_targets == fixed, "ラウンドロビンに落ちている"


def test_plan_likert_shorter_than_likert_items_does_not_backfill():
    """★**固定リストが `likert_items` より短くても補充されない**（integration で発覚）。

    `select_likert_targets` は `want = min(likert_items, |pool|)` 件を返すため、固定リストが
    3 件で `likert_items=10` だと**残り 7 件をラウンドロビンが補充**してしまう
    ＝FD Q2 で否決した挙動が部分的に復活する。→ プラン経路では**件数もプランを権威**にし
    （`likert_items = len(fixed)`）、補充ループに入らせない。
    """
    repo, _, ids = _plan_repo(likert_targets=[])
    fixed = [ids[2], ids[5], ids[9]]                        # 3 件だけ指名
    repo.plan_meta["primary"]["likert_targets"] = fixed
    repo.plan_bindings = {"tk": ("primary", 0)}
    repo.tokens["tk"] = Token(token="tk", status="unused", issued_at="2026-07-20T00:00:00Z")

    # likert_items は既定より大きい 10 を渡す（補充が起きうる条件）
    asyncio.run(start_or_resume(repo, "tk", _params(likert_items=10)))
    assert repo.sessions["tk"].likert_targets == fixed, "ラウンドロビンが補充している"


def test_fallback_path_when_no_plan_binding():
    """`plan_index` 未束縛なら**従来のオンライン生成**（U6-NFR-14・dev 専用）。"""
    pool = _pool({Layer.PRO: 6, Layer.EDIT: 6, Layer.AI: 5, Layer.RULE: 4})
    repo = FakeRepo(pool)
    repo.tokens["nb"] = Token(token="nb", status="unused", issued_at="2026-07-20T00:00:00Z")
    asyncio.run(start_or_resume(repo, "nb", _params()))
    assert repo.pairs["nb"], "フォールバック経路でペアが生成されない"
    assert repo.sessions["nb"].likert_targets is not None


# ------------------------------------------------- 補充トークン（BR-U6-15）
def test_replacement_inherits_only_unanswered_production():
    """★補充トークンは**本番の未回答分のみ**を引き継ぐ（m を超えさせない）。

    スロット全体をやり直すと既回答分が二重に判定され、該当 item の比較数が m を超えて
    **露出 gap≠0** になる＝事前生成の前提が壊れる。
    """
    repo, _, _ = _plan_repo(likert_targets=[], n_prod=6)
    repo.plan_bindings = {"sub": ("primary", 0)}
    repo.tokens["sub"] = Token(token="sub", status="unused", issued_at="2026-07-20T00:00:00Z")
    repo.slot_answered = {("primary", 0): {"p0001", "p0002", "p0003"}}

    asyncio.run(start_or_resume(repo, "sub", _params()))
    got = repo.pairs["sub"]
    prod = [p.pair_id for p in got if not p.is_practice]
    assert set(prod).isdisjoint({"p0001", "p0002", "p0003"}), "回答済みが二重に配られている"
    assert prod == ["p0004", "p0005", "p0006"]


def test_replacement_always_gets_all_practice():
    """★**練習ペアは常に全量再提示**（補充者は別人ゆえ読み返しテストの習得が必要）。

    練習は出力段で除外される（`is_practice=1`）ため**二重カウントの害はゼロ**。
    """
    repo, _, _ = _plan_repo(likert_targets=[], n_prod=6)
    repo.plan_bindings = {"sub": ("primary", 0)}
    repo.tokens["sub"] = Token(token="sub", status="unused", issued_at="2026-07-20T00:00:00Z")
    # 練習も本番もすべて回答済み、という極端な状態
    repo.slot_answered = {("primary", 0): {f"p{i:04d}" for i in range(0, 7)}}

    asyncio.run(start_or_resume(repo, "sub", _params()))
    got = repo.pairs["sub"]
    practice = [p for p in got if p.is_practice]
    prod = [p for p in got if not p.is_practice]
    assert len(practice) == 1, "練習が全量再提示されていない"
    assert prod == [], "回答済みの本番が配られている"


# ------------------------------------------------------------- 契約（型）
def test_plan_ingest_request_rejects_unknown_keys():
    """`PlanIngestRequest` は未知キーを拒否（`extra="forbid"`）。"""
    with pytest.raises(ValidationError):
        PlanIngestRequest.model_validate({"meta": {}, "rows": [], "extra": 1})


def test_plan_ingest_request_requires_rows():
    """空プランの投入は拒否（`rows` は 1 件以上）。"""
    meta = {"plan_set": "p", "seed": 1, "attempt": 0, "content_hash": "h",
            "n_items": 10, "n_slots": 2, "n_pairs": 20, "m_per_item": 4,
            "likert_targets": [], "generated_at": "2026-07-20T00:00:00Z"}
    with pytest.raises(ValidationError):
        PlanIngestRequest.model_validate({"meta": meta, "rows": []})
