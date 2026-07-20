"""pool_sufficiency のプロパティ/境界テスト（BR-U4a-05, PBT-03 / U4a-NFR-10）。

充足判定は単一実装（ingest warn と issue gate が同一関数を呼ぶ）。ここでは述語の
正しさ・単調性・境界を検証する。
"""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from backend.domain import pool_sufficiency
from schema import POOL_LAYERS, REQUIRED_LAYERS, AssignmentParams, Item, Layer
from tests.pbt import generators


def _item(i: int, layer: Layer) -> Item:
    return Item(item_id=f"it{i:04d}", layer=layer, body=f"body{i}")


def _pool(counts: dict[Layer, int]) -> list[Item]:
    pool, i = [], 0
    for layer, n in counts.items():
        for _ in range(n):
            pool.append(_item(i, layer)); i += 1
    return pool


# ---------------------------------------------------------------- 述語の正しさ

@given(pool=generators.pools(), params=generators.params())
def test_ok_iff_three_conditions(pool, params):
    """ok は三点セットがすべて成立するとき、かつそのときに限る。

    U6: オラクルも**実装と同じ用途別リスト**を使う（`for L in Layer` の全走査だと
    層値を足した瞬間に「足した層も非空」を要求してしまい実装と乖離する, BR-U6-05）。
    母数 = `POOL_LAYERS` / 非空要求 = `REQUIRED_LAYERS`。
    """
    res = pool_sufficiency(pool, params)
    in_pool = [it for it in pool if it.layer in POOL_LAYERS]   # 母数（practice を除外）
    total = len(in_pool)
    by_layer = {L: sum(1 for it in in_pool if it.layer == L) for L in POOL_LAYERS}
    cond1 = total >= math.ceil(2 * params.session_pairs / params.max_item_occurrence_k)
    cond2 = all(by_layer[L] > 0 for L in REQUIRED_LAYERS)
    cond3 = (total - max(by_layer.values())) * params.max_item_occurrence_k \
        >= math.ceil(params.cross_layer_min_ratio * params.session_pairs)
    assert res.ok == (cond1 and cond2 and cond3)
    assert (not res.ok) == bool(res.shortfalls)


# ---------------------------------------------------------------- 単調性

@given(extra_layer=st.sampled_from(list(POOL_LAYERS)), n=st.integers(1, 5))
def test_monotonic_adding_items_keeps_sufficient(extra_layer, n):
    """充足プールに item を足しても充足のまま（total・層間供給は減らない）。"""
    params = AssignmentParams()
    base = _pool({Layer.PRO: 30, Layer.AI: 20, Layer.EDIT: 30, Layer.RULE: 15})
    assert pool_sufficiency(base, params).ok
    bigger = base + [_item(1000 + j, extra_layer) for j in range(n)]
    assert pool_sufficiency(bigger, params).ok


# ---------------------------------------------------------------- 境界・不足検出

def test_realistic_pool_sufficient():
    """本番規模（95 件, pro30/ai20/edit30/rule15）は充足。"""
    params = AssignmentParams()
    pool = _pool({Layer.PRO: 30, Layer.AI: 20, Layer.EDIT: 30, Layer.RULE: 15})
    assert pool_sufficiency(pool, params).ok


def test_missing_layer_rejected():
    """層欠け（rule=0）は③以前に②で不足。"""
    params = AssignmentParams()
    pool = _pool({Layer.PRO: 50, Layer.AI: 20, Layer.EDIT: 30, Layer.RULE: 0})
    res = pool_sufficiency(pool, params)
    assert not res.ok
    assert any("rule" in s for s in res.shortfalls)


def test_lopsided_pool_fails_cross_supply():
    """②を満たしても③（層間供給）で落ちる: 最大層に偏ると層間ペアを賄えない。"""
    params = AssignmentParams()  # session_pairs=40, k=3, cross=0.65 → need=26
    # 非最大層は各1件=3件、k=3 → 供給=(94-91)*3=9 < 26。総数94は①(=27)満たす。
    pool = _pool({Layer.PRO: 91, Layer.AI: 1, Layer.EDIT: 1, Layer.RULE: 1})
    res = pool_sufficiency(pool, params)
    assert not res.ok
    assert any("層間供給" in s for s in res.shortfalls)


def test_too_small_total_fails():
    """総数不足（①）を検出。"""
    params = AssignmentParams()  # min_total=ceil(80/3)=27
    pool = _pool({Layer.PRO: 3, Layer.AI: 3, Layer.EDIT: 3, Layer.RULE: 3})  # 12
    res = pool_sufficiency(pool, params)
    assert not res.ok
    assert any("総数不足" in s for s in res.shortfalls)
