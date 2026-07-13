"""プール充足判定（BR-U4a-05 三点セット）— 純粋・単一実装（DP-U4a-05 / U4a-NFR-10）。

**この関数だけが充足判定の実装**。pool_ingest（ingest 時の warn 判定）と token_issue
（issue 時のハードゲート）の両方が本関数を呼ぶことで、述語の乖離を構造的に防ぐ。

評価対象は呼び出し側が渡す `items`（マージ後プール＝既存 ∪ 入力 を想定, BR-U4a-05）。
"""

from __future__ import annotations

import math

from schema import AssignmentParams, Item, Layer, SufficiencyResult


def pool_sufficiency(items: list[Item], params: AssignmentParams) -> SufficiencyResult:
    """三点セットを評価し `SufficiencyResult{ok, shortfalls}` を返す（純粋）。

    ① 総数 ≥ ceil(2 × session_pairs / k)
    ② 4 層すべて非空
    ③ (総数 − 最大層件数) × k ≥ ceil(cross_layer_min_ratio × session_pairs)
    """
    shortfalls: list[str] = []
    total = len(items)

    # ① 総数
    min_total = math.ceil(2 * params.session_pairs / params.max_item_occurrence_k)
    if total < min_total:
        shortfalls.append(f"総数不足: {total} < 最小 {min_total}（ceil(2×session_pairs/k)）")

    # ② 4 層すべて非空
    by_layer: dict[Layer, int] = {}
    for it in items:
        by_layer[it.layer] = by_layer.get(it.layer, 0) + 1
    empty = [layer.value for layer in Layer if by_layer.get(layer, 0) == 0]
    if empty:
        shortfalls.append(f"空の層: {', '.join(empty)}")

    # ③ 層間ペアの供給可能性
    max_layer = max(by_layer.values()) if by_layer else 0
    supply = (total - max_layer) * params.max_item_occurrence_k
    need = math.ceil(params.cross_layer_min_ratio * params.session_pairs)
    if supply < need:
        shortfalls.append(
            f"層間供給不足: (総数−最大層){total - max_layer} × k{params.max_item_occurrence_k}"
            f" = {supply} < 必要 {need}（ceil(cross×session_pairs)）"
        )

    return SufficiencyResult(ok=not shortfalls, shortfalls=shortfalls)
