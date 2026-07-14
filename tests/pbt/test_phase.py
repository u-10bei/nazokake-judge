"""PU2-3 — derive_phase の単調性・整合（U2）。

検証（BR-U2-01/03）:
  - 単調性: 判定・Likert・survey を進める（回答集合を単調増加させる）ほど、
    フェーズは practice → judging → likert → survey → done を**後戻りしない**。
  - completed 状態は常に done。
  - is_complete と done フェーズの整合。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from backend.participant.phase import derive_phase, is_complete
from schema import Pair, SessionPhase

# フェーズの線形順序（後戻りしないことの検証用）。
ORDER = {
    SessionPhase.PRACTICE: 0,
    SessionPhase.JUDGING: 1,
    SessionPhase.LIKERT: 2,
    SessionPhase.SURVEY: 3,
    SessionPhase.DONE: 4,
}


def _pairs(n_practice: int, n_prod: int) -> list[Pair]:
    pairs = []
    for i in range(n_practice):
        pairs.append(Pair(pair_id=f"pr{i}", index=i, item_left="a", item_right="b",
                          is_practice=True))
    for i in range(n_prod):
        pairs.append(Pair(pair_id=f"pd{i}", index=n_practice + i,
                          item_left="a", item_right="b", is_practice=False))
    return pairs


@given(
    n_practice=st.integers(min_value=0, max_value=3),
    n_prod=st.integers(min_value=1, max_value=6),
    n_likert=st.integers(min_value=0, max_value=4),
)
def test_phase_monotonic_as_answers_accumulate(n_practice, n_prod, n_likert):
    """回答を順に積むほどフェーズは後戻りしない（PU2-3）。"""
    pairs = _pairs(n_practice, n_prod)
    practice_ids = [p.pair_id for p in pairs if p.is_practice]
    prod_ids = [p.pair_id for p in pairs if not p.is_practice]
    likert_targets = [f"lk{i}" for i in range(n_likert)]

    # 進行イベント列: 練習 → 本番 → Likert → survey を 1 つずつ積む。
    answered_pairs: set[str] = set()
    answered_likert: set[str] = set()
    survey = False

    prev = -1

    def rank() -> int:
        ph = derive_phase(pairs, answered_pairs, likert_targets, answered_likert,
                          survey, "in_progress")
        return ORDER[ph]

    prev = rank()
    for pid in practice_ids:
        answered_pairs.add(pid)
        r = rank(); assert r >= prev; prev = r
    for pid in prod_ids:
        answered_pairs.add(pid)
        r = rank(); assert r >= prev; prev = r
    for ref in likert_targets:
        answered_likert.add(ref)
        r = rank(); assert r >= prev; prev = r
    survey = True
    r = rank(); assert r >= prev

    # 全部揃えば done、かつ is_complete と整合。
    assert derive_phase(pairs, answered_pairs, likert_targets, answered_likert,
                        True, "in_progress") == SessionPhase.DONE
    assert is_complete(pairs, answered_pairs, likert_targets, answered_likert, True)


@given(n_prod=st.integers(min_value=1, max_value=5))
def test_completed_status_is_always_done(n_prod):
    """token_status=completed は常に done（BR-U2-01）。"""
    pairs = _pairs(0, n_prod)
    assert derive_phase(pairs, set(), [], set(), False, "completed") == SessionPhase.DONE
