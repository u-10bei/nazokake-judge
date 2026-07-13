"""割当・状態のプロパティテスト（P-1〜P-7）。各テストは対応する受入基準を docstring に明記（PBT-10）。

強制対象: PBT-02（ラウンドトリップ）/ PBT-03（不変条件）/ PBT-07（ドメインジェネレータ）/
PBT-08（縮小・シード出力, conftest ci profile）。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from backend.domain import (
    deserialize,
    derive_exposure,
    generate_pairs,
    serialize,
    updated_exposure,
    SessionExposure,
)
from schema import Pair, SessionState
from tests.pbt import generators
from tests.pbt.calibration import (
    ALPHA_PROVISIONAL,
    S_PROVISIONAL,
    _fixed_pool,
    cumulative_exposure,
    exposure_balance_ok,
)


# ---------------------------------------------------------------- P-3 (XC-01, PBT-03)

@given(pool=generators.pools(), params=generators.params(), seed=st.integers(0, 10_000))
def test_p3_within_session_constraints(pool, params, seed):
    """P-3 / XC-01: セッション内で a≠b・同一ペア重複なし・同一項目出現 ≤ k。"""
    pairs = generate_pairs(pool, {}, seed, params)
    seen_pairs = set()
    occ: dict[str, int] = {}
    for p in pairs:
        assert p.item_left != p.item_right                      # a ≠ b（BR-01）
        key = frozenset((p.item_left, p.item_right))
        assert key not in seen_pairs                            # 同一ペア重複なし（BR-01）
        seen_pairs.add(key)
        occ[p.item_left] = occ.get(p.item_left, 0) + 1
        occ[p.item_right] = occ.get(p.item_right, 0) + 1
    assert all(c <= params.max_item_occurrence_k for c in occ.values())  # BR-02


# ---------------------------------------------------------------- P-2 (XC-01/FR-03, PBT-03)

@given(pool=generators.pools(), params=generators.params(), seed=st.integers(0, 10_000))
def test_p2_cross_layer_ratio(pool, params, seed):
    """P-2 / FR-03: 本番ペアの層間比率 ≥ cross_layer_min_ratio（実行可能プール）。"""
    pairs = generate_pairs(pool, {}, seed, params)
    prod = [p for p in pairs if not p.is_practice]
    if not prod:
        return
    by_id = {it.item_id: it for it in pool}
    cross = sum(1 for p in prod if by_id[p.item_left].layer != by_id[p.item_right].layer)
    assert cross / len(prod) >= params.cross_layer_min_ratio - 1e-9


# ---------------------------------------------------------------- P-6 (監査・決定論, PBT-08)

@given(pool=generators.pools(), params=generators.params(), seed=st.integers(0, 10_000))
def test_p6_determinism(pool, params, seed):
    """P-6: 同一 (pool, exposure, seed, params) → 同一出力。"""
    a = generate_pairs(pool, {}, seed, params)
    b = generate_pairs(pool, {}, seed, params)
    assert [p.model_dump() for p in a] == [p.model_dump() for p in b]


# ---------------------------------------------------------------- P-4 (XC-02, PBT-02)

@given(
    pairs=st.lists(
        st.builds(
            Pair,
            pair_id=st.text(min_size=1, max_size=6).filter(lambda s: s.strip()),
            index=st.integers(0, 50),
            item_left=st.text(min_size=1, max_size=6).filter(lambda s: s.strip()),
            item_right=st.text(min_size=1, max_size=6).filter(lambda s: s.strip()),
            is_practice=st.booleans(),
        ),
        max_size=10,
    ),
    next_index=st.integers(0, 50),
)
def test_p4_serialize_roundtrip(pairs, next_index):
    """P-4 / XC-02: deserialize(serialize(state)) == 元の state（ラウンドトリップ）。"""
    state = SessionState(pairs=pairs, next_index=next_index)
    assert deserialize(serialize(state)) == state


# ---------------------------------------------------------------- P-5 (H-2 オラクル, PBT-03)

@given(pool=generators.pools(), params=generators.params(), seed=st.integers(0, 10_000))
def test_p5_updated_exposure_matches_derive(pool, params, seed):
    """P-5: updated_exposure（逐次オラクル）== derive_exposure（集計）。

    2 セッション分を生成し、両者が一致することを確認する（すべて completed=活性）。
    """
    exposure: dict[str, int] = {}
    sessions = []
    for s in range(2):
        pairs = generate_pairs(pool, exposure, seed + s, params)
        exposure = updated_exposure(exposure, pairs)
        sessions.append(SessionExposure(status="completed", pairs=pairs))
    derived = derive_exposure(sessions, now_iso="2026-07-13T00:00:00Z")
    # 露出 0 の項目は derive では現れないため、非ゼロのみ比較。
    nonzero = {k: v for k, v in exposure.items() if v > 0}
    assert derived == nonzero


# ---------------------------------------------------------------- P-1 (XC-01, PBT-03)

def test_p1_exposure_balance_cumulative():
    """P-1 / XC-01: S セッション累積後、適格項目で `max−min ≤ max(2, α×mean)`。

    ステートフル累積ハーネス（calibration.cumulative_exposure）で固定シード評価
    （統計的性質を決定論化, U1-NFR-13）。α/S は暫定値。
    """
    from schema import AssignmentParams

    pool = _fixed_pool(16)
    params = AssignmentParams(session_pairs=8, practice_pairs=2)
    exposure = cumulative_exposure(pool, params, S_PROVISIONAL)
    assert exposure_balance_ok(exposure, pool, ALPHA_PROVISIONAL)


# ---------------------------------------------------------------- P-7 (位置一様, 統計)

def test_p7_position_uniform():
    """P-7: A/B 提示位置（left/right）の割当が統計的に一様（BR-07）。

    多数シードで「item_id 昇順で小さい方が left か」の割合が 0.5 近傍に収まることを
    固定シード集計で確認する。
    """
    from schema import AssignmentParams

    pool = _fixed_pool(16)
    params = AssignmentParams(session_pairs=8, practice_pairs=0)
    left_smaller = 0
    total = 0
    for seed in range(400):
        for p in generate_pairs(pool, {}, seed, params):
            total += 1
            if p.item_left < p.item_right:
                left_smaller += 1
    ratio = left_smaller / total
    assert 0.42 <= ratio <= 0.58
