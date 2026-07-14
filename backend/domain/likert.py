"""LC-U2-07 LikertSelector — ブリッジ Likert 対象の選定（純関数, U2）。

`select_likert_targets(pool, seed, params) -> list[item_id]`。副作用なし・決定論（P-6）。
`generate_pairs` と同じ「seed 由来で監査再現可能」な純ロジック。

方針（BR-U2-14/15/16, FD Q3=X）:
  - `params.likert_fixed_targets`（プールに実在する item_id）を**優先採用**（順序保持・重複排除）。
  - 不足分を `Random(seed)` で**各層均等ラウンドロビン**に補充（層網羅を優先）。
  - 件数 = min(likert_items, |pool|)。fixed と重複しない。
  - 対象は保存せず、リクエスト時に (現行プール, seed, params) から都度導出（Q3-b, プール凍結前提）。
"""

from __future__ import annotations

import random

from schema import AssignmentParams, Item


def select_likert_targets(
    pool: list[Item],
    seed: int,
    params: AssignmentParams,
) -> list[str]:
    """ブリッジ Likert 対象の item_id 列を決定論的に選ぶ（純粋）。"""
    pool_ids = {it.item_id for it in pool}
    want = min(params.likert_items, len(pool))

    # 1. 固定アンカーを優先（プール実在のみ・順序保持・重複排除）。
    targets: list[str] = []
    seen: set[str] = set()
    for tid in (params.likert_fixed_targets or ()):
        if tid in pool_ids and tid not in seen:
            targets.append(tid)
            seen.add(tid)
            if len(targets) >= want:
                return targets[:want]

    # 2. 不足分を seed 由来で層均等ラウンドロビン補充。
    rng = random.Random(seed)
    by_layer: dict[str, list[str]] = {}
    for it in pool:
        if it.item_id in seen:
            continue
        by_layer.setdefault(it.layer.value, []).append(it.item_id)

    # 各層内をシャッフルし、層をキー順に固定（決定論）。層をまたいで 1 つずつ拾う。
    for layer in sorted(by_layer):
        rng.shuffle(by_layer[layer])
    layers = sorted(by_layer)

    idx = 0
    while len(targets) < want:
        progressed = False
        for layer in layers:
            bucket = by_layer[layer]
            if idx < len(bucket):
                targets.append(bucket[idx])
                progressed = True
                if len(targets) >= want:
                    break
        if not progressed:
            break  # 全層汲み尽くし（想定上 want <= |pool| で起きない）
        idx += 1

    return targets
