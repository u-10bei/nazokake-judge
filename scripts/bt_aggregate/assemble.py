"""LC-U4b-06 — assemble_result（純・BTResult 組立）。

全 item を出力に残し（除外分は bt_score=null+component で可視化, BR-U4b-07）、matches/wins は
U3 と同一定義の**生カウント**（BR-U4b-08）、layer 付与（BR-U4b-10）、source エコーバック
（BR-U4b-09）、rank・calibrated_score・warnings を組む。

**rank 同値処理（Code Gen Step 6 明文固定）**: rank はスコア（θ）降順、θ 同値は item_id 昇順で
安定順位付け（sorted(key=(-θ, item_id)) の enumerate）。対戦構造が対称な場合 θ が厳密一致
しうるため、順位付け規則自体を仕様で固定する（PU4b-2 の決定論は再実行一致しか保証しない）。
"""

from __future__ import annotations

from schema import BTItemScore, BTResult, BTSource

from scripts.bt_aggregate.aggregate import match_counts
from scripts.bt_aggregate.calibrate import calibrated_score


def _component_index(components: list[list[str]]) -> dict[str, int]:
    """item_id → 成分 ID。0 = 最大連結成分（推定対象）。graph.largest_component と同一順序。"""
    comps_sorted = sorted(components, key=lambda c: (-len(c), c))
    idx_of: dict[str, int] = {}
    for idx, comp in enumerate(comps_sorted):
        for item_id in comp:
            idx_of[item_id] = idx
    return idx_of


def assemble_result(
    *,
    source: BTSource,
    all_items,
    wins: dict[str, int],
    pair_counts: dict[tuple[str, str], int],
    theta: dict[str, float],
    components: list[list[str]],
    estimated_ids: set[str],
    calibration,
    alpha: float,
    converged: bool,
    iterations: int,
    warnings: list[str],
) -> BTResult:
    """純関数群の出力を BTResult に組み立てる。

    - all_items: `item_id` / `layer` を持つオブジェクト列（ExportItem）。
    - theta: 推定対象 item の θ。estimated_ids: 推定対象 item_id 集合。
    """
    matches = match_counts(pair_counts)
    comp_of = _component_index(components)

    # rank: 推定対象内でスコア降順・同値は item_id 昇順（安定順位付け）。
    ranked = sorted(estimated_ids, key=lambda i: (-theta[i], i))
    rank_of = {item_id: r for r, item_id in enumerate(ranked, start=1)}

    scores: list[BTItemScore] = []
    for item in sorted(all_items, key=lambda x: x.item_id):   # 出力順も item_id 昇順で決定論
        iid = item.item_id
        estimated = iid in estimated_ids
        th = theta.get(iid) if estimated else None
        calibrated = (
            calibrated_score(th, calibration)
            if (estimated and calibration is not None)
            else None
        )
        scores.append(BTItemScore(
            item_id=iid,
            layer=item.layer,
            bt_score=th,
            calibrated_score=calibrated,
            component=comp_of.get(iid),            # 孤立（観測ペアなし）は None
            rank=rank_of.get(iid),
            matches=matches.get(iid, 0),           # 生カウント（BR-U4b-08）
            wins=wins.get(iid, 0),                 # 生カウント（BR-U4b-08）
        ))

    return BTResult(
        source=source,
        n_items=len(scores),
        n_comparisons=sum(pair_counts.values()),
        n_components=len(components),
        estimated_component_size=len(estimated_ids),
        converged=converged,
        iterations=iterations,
        alpha=alpha,
        items=scores,
        calibration=calibration,
        warnings=warnings,
    )
