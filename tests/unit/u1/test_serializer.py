"""LC-04 Serializer 単体テスト（XC-02 の example ベース。網羅は PBT P-4）。"""

from __future__ import annotations

from backend.domain import deserialize, serialize
from backend.domain.serializer import next_unanswered_index
from schema import Pair, SessionState


def _pairs():
    return [
        Pair(pair_id="p000", index=0, item_left="a", item_right="b", is_practice=True),
        Pair(pair_id="p001", index=1, item_left="c", item_right="d"),
        Pair(pair_id="p002", index=2, item_left="e", item_right="f"),
    ]


def test_roundtrip_equal():
    state = SessionState(pairs=_pairs(), next_index=1)
    assert deserialize(serialize(state)) == state


def test_next_unanswered_index():
    pairs = _pairs()
    assert next_unanswered_index(pairs, set()) == 0
    assert next_unanswered_index(pairs, {"p000"}) == 1
    assert next_unanswered_index(pairs, {"p000", "p001"}) == 2
    assert next_unanswered_index(pairs, {"p000", "p001", "p002"}) == 3  # 全回答済み
