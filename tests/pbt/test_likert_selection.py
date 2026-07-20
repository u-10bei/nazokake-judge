"""PU2-6 — select_likert_targets のプロパティ（PBT-03 系, U2）。

検証（BR-U2-14/15/16）:
  - 決定論: 同一 (pool, seed, params) → 同一結果。
  - 件数: len == min(likert_items, |pool|)。
  - 一意: 重複なし・全て pool 内。
  - fixed 包含: likert_fixed_targets（プール実在分）を必ず含み、先頭に順序保持。
  - 層網羅: 補充分は層をまたいでラウンドロビン（可能な範囲で層を均す）。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from backend.domain import select_likert_targets
from schema import AssignmentParams
from tests.pbt.generators import pools


@given(pool=pools(), seed=st.integers(min_value=0, max_value=2**63 - 1),
       k=st.integers(min_value=0, max_value=15))
def test_deterministic_and_sized(pool, seed, k):
    """決定論・件数・一意・pool 内（PU2-6）。"""
    params = AssignmentParams(likert_items=k)
    a = select_likert_targets(pool, seed, params)
    b = select_likert_targets(pool, seed, params)
    assert a == b                                   # 決定論
    assert len(a) == min(k, len(pool))              # 件数
    assert len(set(a)) == len(a)                    # 一意
    pool_ids = {it.item_id for it in pool}
    assert all(t in pool_ids for t in a)            # pool 内


@given(pool=pools(), seed=st.integers(min_value=0, max_value=2**63 - 1))
def test_fixed_targets_included_first(pool, seed):
    """likert_fixed_targets（プール実在分）を先頭に順序保持で包含（PU2-6）。"""
    ids = [it.item_id for it in pool]
    fixed = tuple(ids[:3])                           # プール実在の 3 件を固定
    params = AssignmentParams(likert_items=8, likert_fixed_targets=fixed)
    res = select_likert_targets(pool, seed, params)
    # 先頭に fixed が順序どおり並ぶ（want=8 >= 3 のため全て含まれる）。
    assert res[:len(fixed)] == list(fixed)


@given(pool=pools(), seed=st.integers(min_value=0, max_value=2**63 - 1))
def test_fixed_targets_not_in_pool_ignored(pool, seed):
    """プールに存在しない固定 ID は無視される（BR-U2-15）。"""
    params = AssignmentParams(
        likert_items=5, likert_fixed_targets=("ghost-1", "ghost-2"),
    )
    res = select_likert_targets(pool, seed, params)
    assert "ghost-1" not in res and "ghost-2" not in res
    assert len(res) == min(5, len(pool))


@given(pool=pools(min_items=16, max_items=24),
       seed=st.integers(min_value=0, max_value=2**63 - 1))
def test_layer_coverage_when_enough(pool, seed):
    """補充のみ・件数 >= 層数 のとき**プール内の全層**から最低 1 件は選ばれる（層網羅, BR-U2-15）。

    U6: 層数を**ハードコードせずプールから導出**する。`list(Layer)` を前提に「4」と
    書いていたため、U6 で層値を 2 つ足した際に落ちた。**プール由来にすれば層構成が
    変わっても壊れない**（BR-U6-05 と同じ「暗黙走査を明示に置き換える」規律）。
    """
    params = AssignmentParams(likert_items=8)        # fixed なし・全補充
    res = select_likert_targets(pool, seed, params)
    by_id = {it.item_id: it.layer.value for it in pool}
    layers_hit = {by_id[t] for t in res}
    layers_in_pool = {it.layer.value for it in pool}
    # likert_items(8) >= 層数 ゆえラウンドロビンでプール内の全層に触れる。
    assert layers_hit == layers_in_pool
