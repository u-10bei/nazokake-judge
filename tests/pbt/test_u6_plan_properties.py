"""U6 プラン生成器の不変条件（PBT-03 が主, U6-NFR-09/10/11）。

PU6-1 露出 gap=0 / PU6-2 全体連結 / PU6-3 k≤3 / PU6-4 同一ペア0 / PU6-5 層間 ≥0.65 /
PU6-6 決定論 / **PU6-7 ブロック連結** / **PU6-8 禁止辺の不在**。

**ジェネレータは n・E・J を振る**（U6-NFR-10）。n=38/E=8/J=228 の 1 点だけでは
「**その組合せでたまたま通る**」ことしか示せない（U4b で単調性ジェネレータの適用範囲を
誤った教訓）。**失敗系**（正則不能・分割総和≠J）も検証する（U6-NFR-11）。
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from schema import POOL_LAYERS, Item

from scripts.plan_generate.constraints import Constraints
from scripts.plan_generate.graph_build import (
    build_regular_edges,
    connected_components,
    degree_of,
)
from scripts.plan_generate.partition import (
    PartitionError,
    blocks_of,
    check_block_feasibility,
    partition_edges,
    split_sizes,
)
from scripts.plan_generate.placement import search_placement

LAYER_VALUES = [l.value for l in POOL_LAYERS]


def _pool(n: int) -> list[Item]:
    """n 件のプール（POOL_LAYERS を巡回配分＝全層非空）。"""
    from schema import Layer
    layers = list(POOL_LAYERS)
    return [Item(item_id=f"i{k:03d}", layer=layers[k % len(layers)], body=f"b{k}", body_ref=None)
            for k in range(n)]


def _empty_constraints(plan_set: str = "t") -> Constraints:
    return Constraints(plan_set=plan_set, likert_targets=[], forbidden_pairs=set(),
                       discouraged_pairs=set(), enrichment=[], avoid_adjacent_groups=[])


@st.composite
def plan_params(draw):
    """★n・E・m を振る（U6-NFR-10）。`J = n·m/2` は従属して決まる。

    実データ点（n=38/m=12/E=8）だけでなく、**構成可能な範囲を広く**引く。
    """
    n = draw(st.integers(min_value=10, max_value=40))
    half = draw(st.integers(min_value=2, max_value=max(2, min(6, (n - 1) // 2))))
    m = half * 2                       # m は偶数（巡回グラフの構成条件）
    e = draw(st.integers(min_value=2, max_value=8))
    j = n * m // 2
    return n, m, e, j


def _build(n, m, e, j, seed=12345, k=3, cons=None):
    """構成 → 分割まで通す（テスト共通のヘルパ）。"""
    pool = _pool(n)
    cons = cons or _empty_constraints()
    order, _ = search_placement(pool, cons, m=m, seed=seed, max_steps=1500)
    edges = build_regular_edges(order, m)
    slots = partition_edges(edges, split_sizes(j, e), k=k, seed=seed)
    return pool, edges, slots


# ------------------------------------------------------- PU6-1 / PU6-2 / PU6-4
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(plan_params())
def test_pu6_1_2_4_construction_guarantees(p):
    """**構成で保証される**もの: 露出 gap=0 / 全体連結 / 同一ペア0（DP-U6-02）。"""
    n, m, e, j = p
    pool = _pool(n)
    order, _ = search_placement(pool, _empty_constraints(), m=m, seed=7, max_steps=500)
    edges = build_regular_edges(order, m)
    ids = [it.item_id for it in pool]

    # PU6-1: 全頂点が次数 m（＝全 item がちょうど m 回出場）
    deg = degree_of(edges, ids)
    assert min(deg.values()) == max(deg.values()) == m, f"露出 gap≠0: {min(deg.values())}〜{max(deg.values())}"
    # PU6-2: 距離 1 の輪があるため必ず連結
    assert len(connected_components(ids, edges)) == 1
    # PU6-4: 辺は集合として構成される＝相異なる
    assert len(edges) == len(set(edges)) == j


# ------------------------------------------------------------------ PU6-3
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(plan_params(), st.integers(min_value=2, max_value=4))
def test_pu6_3_k_constraint(p, k):
    """評価者内の同一 item 出現 ≤ k（分割が担う制約）。"""
    n, m, e, j = p
    try:
        _, _, slots = _build(n, m, e, j, k=k)
    except PartitionError:
        return          # k が厳しすぎる組合せは明示失敗する（それ自体が正しい挙動）
    for slot in slots:
        occ: dict[str, int] = {}
        for a, b in slot:
            occ[a] = occ.get(a, 0) + 1
            occ[b] = occ.get(b, 0) + 1
        assert not occ or max(occ.values()) <= k


# ------------------------------------------------------------------ PU6-7 ★
def _generate_verified(n, m, e, j, *, k=3, seed0=1000, max_attempts=12, cons=None):
    """CLI と同じ「構成 → 検証 → seed 再試行」ループ（成功なら (pool, rows, v) を返す）。"""
    from scripts.plan_generate.sequencing import build_slot_rows
    from scripts.plan_generate.verify import verify_plan
    pool = _pool(n)
    cons = cons or _empty_constraints()
    for a in range(max_attempts):
        seed = seed0 + a
        order, sc = search_placement(pool, cons, m=m, seed=seed, max_steps=1200)
        if sc.forbidden_violations:
            continue
        try:
            edges = build_regular_edges(order, m)
            slots = partition_edges(edges, split_sizes(j, e), k=k, seed=seed)
        except (PartitionError, ValueError):
            continue
        rows = build_slot_rows(slots, [], cons.avoid_adjacent_groups, seed=seed)
        v = verify_plan(pool, rows, cons, m=m, k=k, n_slots=e, n_blocks=2,
                        cross_target=0.0)      # 層間は本テストの対象外
        if v.ok:
            return pool, rows, v
    return None


@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(plan_params())
def test_pu6_7_block_connectivity(p):
    """**生成器が返したプランは必ずブロック連結**（BR-U6-20）。

    ★性質の定義域に注意（U4b の単調性で適用範囲を誤った教訓）: BR-U6-20 が要求するのは
    「**生成器の出力がブロック連結であること**」であって「**任意の (n,m,E) で生成器が必ず
    成功すること**」ではない。後者は**偽**——例えば `n=11, m=4, E=2`（ブロック 11 辺 /
    連結に必要 10 辺）は辺数こそ足りるが**貪欲分割ではまず連結にならない**。
    そのような組合せで生成器は**明示失敗**するのが正しい（＝返さない）。

    よって性質は「**返ったなら連結**」。返らなかった場合は対象外とする。
    """
    n, m, e, j = p
    if e < 2:
        return
    try:
        check_block_feasibility(n, j, e, 2)     # 原理的に不可能な組合せは対象外
    except PartitionError:
        return
    got = _generate_verified(n, m, e, j)
    if got is None:
        return                                  # 明示失敗＝正しい挙動（性質の対象外）
    pool, rows, v = got
    assert all(c == 1 for c in v.block_components), \
        f"生成器が返したのにブロック非連結: {v.block_components}"


def test_pu6_7_real_configs_succeed():
    """★実データ 2 構成では**実際に生成できる**（性質だけでなく実行可能性も担保）。

    成立版 n=38/m=12/E=8（ブロック 114 辺 ≫ 37）/ フォールバック n=34/m=12/E=8（102 ≫ 33）。
    余裕が大きいため貪欲分割でもブロック連結が安定して得られる。
    """
    for n, j in ((38, 228), (34, 204)):
        got = _generate_verified(n, 12, 8, j, seed0=20260720, max_attempts=5)
        assert got is not None, f"実データ構成 n={n} で生成できなかった"
        assert all(c == 1 for c in got[2].block_components)


# ------------------------------------------------------------------ PU6-6
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(plan_params(), st.integers(min_value=0, max_value=9999))
def test_pu6_6_determinism(p, seed):
    """同一 (プール, n, m, E, seed) → **同一プラン**（BR-U6-11）。"""
    n, m, e, j = p
    try:
        r1 = _build(n, m, e, j, seed=seed)[2]
        r2 = _build(n, m, e, j, seed=seed)[2]
    except PartitionError:
        return
    assert r1 == r2


# ------------------------------------------------------------------ PU6-8 ★
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.integers(min_value=20, max_value=38), st.integers(min_value=1, max_value=6),
       st.integers(min_value=0, max_value=999))
def test_pu6_8_forbidden_edges_absent(n, n_forbidden, seed):
    """**禁止ペアが辺集合に現れない**（ハード制約・BR-U6-21）。

    円周距離 >d に配置することで**構成的に排除**できる（`C_n(1..d)` の隣接は距離 ≤ d）。
    探索が排除しきれなかった場合は**呼び出し側が失敗と判断して seed を進める**ため、
    ここでは「排除できたなら辺に現れない」ことを確認する。
    """
    m = 12 if n > 13 else 4
    pool = _pool(n)
    ids = [it.item_id for it in pool]
    rnd = __import__("random").Random(seed)
    forb = set()
    while len(forb) < n_forbidden:
        a, b = rnd.sample(ids, 2)
        forb.add((a, b) if a <= b else (b, a))
    cons = Constraints(plan_set="t", likert_targets=[], forbidden_pairs=forb,
                       discouraged_pairs=set(), enrichment=[], avoid_adjacent_groups=[])

    order, score = search_placement(pool, cons, m=m, seed=seed, max_steps=4000)
    edges = set(build_regular_edges(order, m))
    residual = forb & edges
    # 探索が「違反 0」と報告したなら、実際の辺集合にも現れてはならない（整合性）
    assert (score.forbidden_violations == 0) == (len(residual) == 0)
    if score.forbidden_violations == 0:
        assert not residual


# ------------------------------------------------------- 失敗系（U6-NFR-11）
def test_failure_odd_m_is_explicit():
    """m が奇数 → 巡回グラフで構成できず**明示失敗**。"""
    with pytest.raises(ValueError, match="奇数"):
        build_regular_edges([f"i{k}" for k in range(10)], 5)


def test_failure_m_ge_n_is_explicit():
    """m ≥ n → **明示失敗**。"""
    with pytest.raises(ValueError, match="以上"):
        build_regular_edges([f"i{k}" for k in range(6)], 6)


def test_failure_split_sum_mismatch_is_explicit():
    """**分割定員の総和 ≠ 辺数** → 明示失敗（分割を引数化する場合の入力検証）。"""
    edges = [(f"a{i}", f"b{i}") for i in range(10)]
    with pytest.raises(PartitionError, match="総和"):
        partition_edges(edges, [3, 3, 3], k=3, seed=1)      # 9 ≠ 10


def test_split_sizes_matches_total():
    """`split_sizes` は常に総和 = J（実データ 2 点で確認）。"""
    assert split_sizes(228, 8) == [29, 29, 29, 29, 28, 28, 28, 28]
    assert sum(split_sizes(228, 8)) == 228
    assert split_sizes(204, 8) == [26, 26, 26, 26, 25, 25, 25, 25]
    assert sum(split_sizes(204, 8)) == 204


def test_block_feasibility_rejects_infeasible():
    """**ブロック連結が原理的に不可能な組合せ**は事前検査で明示失敗する（U6-NFR-11）。

    PBT `test_pu6_7_block_connectivity` が出した反例 `n=10, m=4, E=3`（J=20）:
    ブロック1 が 1 スロット 7 辺しか持たず **10 頂点を連結するのに必要な 9 辺**に届かない。
    事前検査がないと「seed 運が悪い」と誤認して max_attempts 回リトライしてしまう。
    """
    with pytest.raises(PartitionError, match="n−1"):
        check_block_feasibility(n_items=10, n_pairs=20, n_slots=3, n_blocks=2)


def test_block_feasibility_accepts_real_configs():
    """実データ 2 構成は実行可能（成立版 n=38/J=228/E=8・フォールバック n=34/J=204/E=8）。"""
    check_block_feasibility(n_items=38, n_pairs=228, n_slots=8, n_blocks=2)   # 114 >= 37
    check_block_feasibility(n_items=34, n_pairs=204, n_slots=8, n_blocks=2)   # 102 >= 33
