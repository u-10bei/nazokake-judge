"""LC-U6-02 — ★制約付き円周配置探索（純関数, DP-U6-03）。

**なぜ配置が必須要件なのか（実測）**: 巡回グラフ `C38(1..6)`（同じ辺数・同じ正則次数）で
**item の並べ方だけ**を変えた結果:

    層ごとに固める（grouped）  → 層間比率 0.390  ❌ ゲート（0.65）不足
    層をインターリーブ         → 0.728  ✅
    シャッフル                 → 0.772  ✅

**同じ辺集合でも並べ方だけでゲートを割る**。「たまたま通る」に委ねられない。しかも
**grouped 配置では 0.390 が構造的な上限**なので、「ランダム生成 + 検証 + リトライ」だけの
方式は**永久に収束しない**。→ 配置を**目的関数つきの探索**にする。

**内容制約を巡回グラフの幾何に写す**（BR-U6-21）:
  - **禁止ペア（ハード）**: `C_n(1..d)` の隣接は円周距離 ≤ d ゆえ、**距離 >d に配置すれば
    構成的に排除**できる。
  - **忌避ペア（ソフト）**: 同上を目的関数の一項に。**達成できなくても失敗させない**。
  - **濃縮**: 対象を**近接配置**すると直接対戦が増える。目的関数の一項。

**目的関数は辞書式（lexicographic）**（DP-U6-02）:
  1. 禁止ペアの違反数を最小化（ハード。0 でなければ失敗）
  2. 層間比率を**閾値まで**上げる（**到達で頭打ち**＝過剰最適化しない）
  3. 濃縮目標の達成本数を最大化
  4. 忌避ペアの違反数を最小化（ソフト）

**②で頭打ちにする理由**: 層間比率を無制限に最大化すると**濃縮（③）と競合**する。
**ゲートは満たせば十分**。重み付き和（スカラー化）を採らないのは、重みのチューニングが
必要になるうえ**「禁止はハード」という質的差**を表現できないため。
"""

from __future__ import annotations

import random

from schema import Item

from scripts.plan_generate.constraints import Constraints


def _neighbors_within(n: int, d: int) -> list[tuple[int, int]]:
    """円周上で距離 ≤ d の位置ペア（= `C_n(1..d)` の辺の位置表現）。"""
    return sorted({tuple(sorted((i, (i + k) % n))) for k in range(1, d + 1) for i in range(n)})


class PlacementScore:
    """辞書式スコア（大きいほど良い）。"""

    __slots__ = ("forbidden_violations", "cross_ratio", "enrichment", "discouraged_violations")

    def __init__(self, forbidden_violations, cross_ratio, enrichment, discouraged_violations):
        self.forbidden_violations = forbidden_violations
        self.cross_ratio = cross_ratio
        self.enrichment = enrichment
        self.discouraged_violations = discouraged_violations

    def key(self, cross_target: float):
        # 辞書式: ①違反を減らす ②層間は閾値で頭打ち ③濃縮を増やす ④忌避を減らす
        return (
            -self.forbidden_violations,
            min(self.cross_ratio, cross_target),   # ★頭打ち（濃縮との競合を避ける）
            self.enrichment,
            -self.discouraged_violations,
        )


def score_placement(order: list[str], layers: dict[str, str], degree_half: int,
                    cons: Constraints) -> PlacementScore:
    """ある円周配置の評価（純粋）。`order[i]` が位置 i の item_id。"""
    n = len(order)
    pos_pairs = _neighbors_within(n, degree_half)
    edges = {tuple(sorted((order[i], order[j]))) for i, j in pos_pairs}

    forb = sum(1 for p in cons.forbidden_pairs if p in edges)
    disc = sum(1 for p in cons.discouraged_pairs if p in edges)
    cross = sum(1 for a, b in edges if layers[a] != layers[b]) / len(edges) if edges else 0.0
    enrich = 0
    for e in cons.enrichment:
        a = e["anchor"]
        enrich += sum(1 for c in e["counterparts"] if tuple(sorted((a, c))) in edges)
    return PlacementScore(forb, cross, enrich, disc)


def search_placement(pool: list[Item], cons: Constraints, *, m: int, seed: int,
                     cross_target: float = 0.65, max_steps: int = 30000
                     ) -> tuple[list[str], PlacementScore]:
    """制約付き近傍探索（2 点交換）で円周配置を決める。

    - **決定論**: `random.Random(seed)` のみを使う（同一 seed → 同一結果）。
    - **打ち切り**: `max_steps` に達したら現時点の最良を返す。**ハード制約を満たすかの
      判定は呼び出し側**（CLI が失敗と判断して seed を進める）。
    """
    order = [it.item_id for it in pool]
    layers = {it.item_id: it.layer.value for it in pool}
    n = len(order)
    d = m // 2
    rng = random.Random(seed)

    # 初期配置: 層インターリーブ（実測で 0.728 と良好・grouped の 0.390 を避ける）。
    buckets: dict[str, list[str]] = {}
    for it in pool:
        buckets.setdefault(it.layer.value, []).append(it.item_id)
    for k in buckets:
        rng.shuffle(buckets[k])
    keys = sorted(buckets, key=lambda k: (-len(buckets[k]), k))
    order = []
    while any(buckets[k] for k in keys):
        for k in keys:
            if buckets[k]:
                order.append(buckets[k].pop())

    best = score_placement(order, layers, d, cons)
    for _ in range(max_steps):
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        order[i], order[j] = order[j], order[i]
        cand = score_placement(order, layers, d, cons)
        if cand.key(cross_target) >= best.key(cross_target):
            best = cand
        else:
            order[i], order[j] = order[j], order[i]   # 巻き戻し
    return order, best
