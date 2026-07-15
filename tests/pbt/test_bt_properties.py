"""U4b BT 集計の不変条件（PBT-03 が主, U4b-NFR-08）。

PU4b-1 単調性 / PU4b-2 決定論+置換不変性 / PU4b-3 成分内 Σθ=0 /
PU4b-4 識別可能性（非連結→最大成分・純関数合成）/ PU4b-5 較正係数復元。
PBT-02（ラウンドトリップ）は非該当（U4b は一方向変換, U4b-NFR-08）。
"""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from schema import ExportBundle, ExportLikert

from scripts.bt_aggregate.aggregate import aggregate
from scripts.bt_aggregate.calibrate import calibrate, calibrated_score
from scripts.bt_aggregate.graph import (
    connected_components,
    largest_component,
    restrict_to_component,
)
from scripts.bt_aggregate.mm import fit_bt
from scripts.bt_aggregate.__main__ import aggregate_bundle
from tests.pbt.bt_generators import (
    disconnected_scenario,
    flip_and_shuffle,
    free_scenario,
    ranked_scenario,
)

ALPHA = 1.0
MAX_ITER = 20000
TOL = 1e-12


def _bundle(items, judgments, likert=None):
    return ExportBundle(
        schema_version="1.0.0", exported_at="2026-07-15T00:00:00Z",
        items=items, judgments=judgments, likert=likert or [], surveys=[],
    )


# --------------------------------------------------------------- PU4b-1 単調性
@given(ranked_scenario())
def test_pu4b1_monotonicity(scenario):
    """真の全順序に忠実な判定 → 推定対象成分内で上位ランクほど θ が大きい。"""
    items, judgments, rank_index = scenario
    result = aggregate_bundle(_bundle(items, judgments), alpha=ALPHA, max_iter=MAX_ITER, tol=TOL)
    theta = {s.item_id: s.bt_score for s in result.items if s.bt_score is not None}
    # 推定対象内の観測ペアで、上位ランク（rank_index 小）ほど θ 大。
    wins, pair_counts = aggregate(judgments)
    estimated = set(largest_component(connected_components(pair_counts)))
    for (a, b) in pair_counts:
        if a in estimated and b in estimated:
            hi, lo = (a, b) if rank_index[a] < rank_index[b] else (b, a)
            assert theta[hi] > theta[lo], f"{hi} > {lo} を期待"


# ------------------------------------------------ PU4b-2 決定論 + 置換不変性
@given(free_scenario(), st.data())
def test_pu4b2_determinism_and_permutation_invariance(scenario, data):
    """同一入力→同一結果、かつ左右反転+シャッフルでも BTResult が一致。"""
    items, judgments = scenario
    r1 = aggregate_bundle(_bundle(items, judgments), alpha=ALPHA, max_iter=MAX_ITER, tol=TOL)
    # 決定論: 再実行一致。
    r2 = aggregate_bundle(_bundle(items, judgments), alpha=ALPHA, max_iter=MAX_ITER, tol=TOL)
    assert r1.model_dump() == r2.model_dump()
    # 置換不変性: 左右反転 + シャッフルでも一致。
    transformed = flip_and_shuffle(data.draw, judgments)
    r3 = aggregate_bundle(_bundle(items, list(transformed)), alpha=ALPHA, max_iter=MAX_ITER, tol=TOL)
    # θ は最下位桁で揺れうるため厳密一致でなく近接一致で検証（行順序不問決定論）。
    s1 = {s.item_id: s.bt_score for s in r1.items}
    s3 = {s.item_id: s.bt_score for s in r3.items}
    assert s1.keys() == s3.keys()
    for k in s1:
        if s1[k] is None:
            assert s3[k] is None
        else:
            assert math.isclose(s1[k], s3[k], abs_tol=1e-9)
    # matches/wins（生カウント）は厳密一致。
    m1 = {s.item_id: (s.matches, s.wins) for s in r1.items}
    m3 = {s.item_id: (s.matches, s.wins) for s in r3.items}
    assert m1 == m3


# --------------------------------------------------------- PU4b-3 成分内 Σθ=0
@given(free_scenario())
def test_pu4b3_sum_theta_zero(scenario):
    """推定対象（最大連結成分）内で Σθ ≈ 0（BR-U4b-04）。"""
    items, judgments = scenario
    result = aggregate_bundle(_bundle(items, judgments), alpha=ALPHA, max_iter=MAX_ITER, tol=TOL)
    thetas = [s.bt_score for s in result.items if s.bt_score is not None]
    if thetas:
        assert math.isclose(sum(thetas), 0.0, abs_tol=1e-6)


# ------------------------------------------ PU4b-4 識別可能性（純関数合成）
@given(disconnected_scenario())
def test_pu4b4_identifiability(scenario):
    """非連結→警告 + 最大成分のみ推定・除外 item は bt_score=null（純関数合成で検証）。"""
    items, judgments, group1, group2 = scenario
    wins, pair_counts = aggregate(judgments)

    # 純関数合成: connected_components → restrict_to_component → fit_bt。
    components = connected_components(pair_counts)
    assert len(components) == 2, "2 つの独立クリーク＝非連結"
    estimated = largest_component(components)
    r_wins, r_pairs = restrict_to_component(wins, pair_counts, estimated)
    theta, converged, iterations = fit_bt(r_wins, r_pairs, alpha=ALPHA, max_iter=MAX_ITER, tol=TOL)
    assert set(theta.keys()) == set(estimated)

    # BTResult 経由でも: 除外 item は bt_score=null、警告に非連結を記録。
    result = aggregate_bundle(_bundle(items, judgments), alpha=ALPHA, max_iter=MAX_ITER, tol=TOL)
    assert result.n_components == 2
    estimated_set = set(estimated)
    for s in result.items:
        if s.item_id in estimated_set:
            assert s.bt_score is not None
        else:
            assert s.bt_score is None and s.rank is None
    assert any("非連結" in w for w in result.warnings)


# ------------------------------------------------ PU4b-5 較正係数復元
@given(
    slope=st.floats(min_value=0.2, max_value=5.0),
    intercept=st.floats(min_value=-3.0, max_value=3.0),
    likerts=st.lists(st.integers(min_value=1, max_value=7), min_size=2, max_size=6, unique=True),
)
def test_pu4b5_calibration_recovery(slope, intercept, likerts):
    """既知の線形 θ=slope·L+intercept を単回帰で復元し calibrated≈L（BR-U4b-05）。"""
    # 各アンカー item に 1 件の Likert（rating=L）を与え、θ を厳密な線形で設定。
    theta = {}
    likert_rows = []
    item_ids = []
    for k, L in enumerate(likerts):
        iid = f"i{k:02d}"
        item_ids.append(iid)
        theta[iid] = slope * L + intercept
        likert_rows.append(ExportLikert(
            token="t0", target_ref=iid, rating=L, created_at="2026-07-15T00:00:00Z"))

    outcome = calibrate(theta, likert_rows, set(item_ids))
    assert outcome.skip_reason is None, "アンカー十分・分散ありゆえ較正成立"
    cal = outcome.calibration
    assert math.isclose(cal.slope, slope, rel_tol=1e-6, abs_tol=1e-9)
    assert math.isclose(cal.intercept, intercept, rel_tol=1e-6, abs_tol=1e-6)
    # calibrated_score = (θ − intercept)/slope ≈ L。
    for iid, L in zip(item_ids, likerts):
        assert math.isclose(calibrated_score(theta[iid], cal), L, rel_tol=1e-6, abs_tol=1e-6)
