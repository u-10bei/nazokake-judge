"""PU3-3 — ExportBundle 自己完結（BR-U3-07, U3-NFR-10）。

judgments に現れる item_id は必ず items セクションに存在する（U4b が層を自己完結取得可能）。
build_export_bundle が items を落とさない・judgments の参照が items に閉じることを、
生成データで反例探索する（PBT 強制セット中 U3 で適用する唯一の候補）。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from backend.admin import format as fmt

LAYERS = ["pro", "ai", "edit", "rule"]


@st.composite
def pool_and_judgments(draw):
    n = draw(st.integers(min_value=2, max_value=12))
    items = [{"item_id": f"i{k:02d}", "layer": LAYERS[k % 4]} for k in range(n)]
    ids = [it["item_id"] for it in items]
    m = draw(st.integers(min_value=0, max_value=20))
    judgments = []
    for j in range(m):
        a = draw(st.sampled_from(ids))
        b = draw(st.sampled_from([x for x in ids if x != a]))
        judgments.append({
            "token": f"t{draw(st.integers(0, 5))}", "pair_id": f"p{j}",
            "pair_index": j, "item_left": a, "item_right": b,
            "choice": draw(st.sampled_from(["A", "B"])),
            "created_at": "2026-07-15T00:00:00Z",
        })
    return items, judgments


@given(pool_and_judgments())
def test_export_bundle_selfcontained(data):
    items, judgments = data
    bundle = fmt.build_export_bundle(
        items=items, judgments=judgments, likert=[], surveys=[],
        exported_at="2026-07-15T00:00:00Z")
    item_ids = {it.item_id for it in bundle.items}
    # 自己完結: 全 judgment の 2 項目が items に含まれる。
    for j in bundle.judgments:
        assert j.item_left in item_ids
        assert j.item_right in item_ids
    # items を落とさない（入力の全 item を保持）。
    assert item_ids == {it["item_id"] for it in items}
