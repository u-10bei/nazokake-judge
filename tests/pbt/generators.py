"""ドメインジェネレータ（PBT-07）: プリミティブを直接使わず、契約に沿う値を生成する。

生成する刺激プールは層間ペアが実行可能になるよう全 4 層を含める（cross-layer 実行可能性）。
"""

from __future__ import annotations

from hypothesis import strategies as st

from schema import AssignmentParams, Item, Layer

LAYERS = list(Layer)


@st.composite
def pools(draw, min_items: int = 12, max_items: int = 24) -> list[Item]:
    """全 4 層を含む刺激プールを生成する（層を round-robin で割当）。"""
    n = draw(st.integers(min_value=min_items, max_value=max_items))
    return [
        Item(item_id=f"it{i:03d}", layer=LAYERS[i % len(LAYERS)],
             body=f"body{i:03d}", body_ref=f"ref{i:03d}")
        for i in range(n)
    ]


@st.composite
def params(draw) -> AssignmentParams:
    """割当が実行可能な範囲のパラメータ（プールに対し十分小さいペア数）。"""
    return AssignmentParams(
        session_pairs=draw(st.integers(min_value=4, max_value=8)),
        practice_pairs=draw(st.integers(min_value=0, max_value=2)),
        cross_layer_min_ratio=0.65,
        max_item_occurrence_k=3,
    )


@st.composite
def exposures(draw, pool: list[Item]) -> dict[str, int]:
    """プール項目に対する小さな露出カウント（一部の項目のみ）。"""
    ids = [it.item_id for it in pool]
    chosen = draw(st.lists(st.sampled_from(ids), max_size=len(ids), unique=True))
    return {i: draw(st.integers(min_value=0, max_value=5)) for i in chosen}
