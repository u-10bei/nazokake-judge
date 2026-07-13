"""LC-02 AssignmentEngine — 割当の純粋関数群（XC-01）。

- generate_pairs: 重み付きランダム抽選 + シード決定論化（Q1=A, P-6）。
- updated_exposure: 生成ペアで露出を更新する純関数。**本番未使用**、PBT のオラクル（P-5）。
- derive_exposure: 確定 PairSequence から露出を集計（H-2）。非アクティブ除外（BR-04）。

すべて副作用なし。同一 (pool, exposure, seed, params) → 同一出力（P-6）。
"""

from __future__ import annotations

import calendar
import math
import random
import time
from dataclasses import dataclass, field

from schema import AssignmentParams, ExposureCounts, Item, Pair


# ---------------------------------------------------------------- generate_pairs

def generate_pairs(
    pool: list[Item],
    exposure: ExposureCounts,
    seed: int,
    params: AssignmentParams,
) -> list[Pair]:
    """あるセッションのペア列を決定論的に生成する。

    重み付きランダム: 露出の少ない項目を優先（weight = 1/(effective_exposure+1)）。
    制約: a≠b・同一ペア重複禁止（BR-01）、同一項目のセッション内出現 ≤ k（BR-02）、
    層間ペア比率 ≥ cross_layer_min_ratio（BR-03）、位置一様割当（BR-07）、
    先頭 practice_pairs 件は練習（BR-10）。制約が満たせない場合はベストエフォート（BR-06）
    で構成できたところまで返す（構成不能の事前排除は BR-05=設定検証の責務）。
    """
    rng = random.Random(seed)
    if len(pool) < 2:
        return []

    total = params.practice_pairs + params.session_pairs
    n_prod = params.session_pairs
    cross_target = math.ceil(params.cross_layer_min_ratio * n_prod)

    occ: dict[str, int] = {it.item_id: 0 for it in pool}
    used: set[frozenset[str]] = set()
    by_id = {it.item_id: it for it in pool}
    pairs: list[Pair] = []

    prod_idx = 0
    cross_made = 0
    for i in range(total):
        is_practice = i < params.practice_pairs
        # 残り本番ペアで層間目標を満たすため、この本番ペアを層間にする必要があるか。
        need_cross = (not is_practice) and (cross_target - cross_made) >= (n_prod - prod_idx)
        prefer_cross = (not is_practice) and (need_cross or cross_made < cross_target)

        picked = _pick_pair(rng, pool, exposure, occ, used, params, prefer_cross, relax=False)
        if picked is None:  # ベストエフォート: 制約を緩めて再試行（BR-06）
            picked = _pick_pair(rng, pool, exposure, occ, used, params, prefer_cross=False, relax=True)
        if picked is None:
            break  # これ以上は構成不能。ここまでで打ち切り。

        a_id, b_id = picked
        # 位置カウンターバランス（BR-07）: どちらを left(=A/上) にするか一様ランダム。
        if rng.random() < 0.5:
            left, right = a_id, b_id
        else:
            left, right = b_id, a_id

        pairs.append(Pair(
            pair_id=f"p{i:03d}", index=i,
            item_left=left, item_right=right, is_practice=is_practice,
        ))
        occ[a_id] += 1
        occ[b_id] += 1
        used.add(frozenset((a_id, b_id)))
        if not is_practice:
            prod_idx += 1
            if by_id[a_id].layer != by_id[b_id].layer:
                cross_made += 1

    return pairs


def _pick_pair(rng, pool, exposure, occ, used, params, prefer_cross, relax):
    """制約下で 2 項目を重み付き抽選する。選べない場合 None。"""
    k = params.max_item_occurrence_k

    def eligible(it: Item) -> bool:
        return relax or occ[it.item_id] < k

    cands = [it for it in pool if eligible(it)]
    if len(cands) < 2:
        return None

    def weight(it: Item) -> float:
        eff = exposure.get(it.item_id, 0) + occ[it.item_id]
        return 1.0 / (eff + 1.0)

    a = _weighted_choice(rng, cands, weight)

    def partners(require_cross: bool) -> list[Item]:
        out = []
        for it in cands:
            if it.item_id == a.item_id:
                continue
            if (not relax) and frozenset((a.item_id, it.item_id)) in used:
                continue
            if require_cross and it.layer == a.layer:
                continue
            out.append(it)
        return out

    cand_partners = partners(require_cross=prefer_cross)
    if not cand_partners and prefer_cross:
        cand_partners = partners(require_cross=False)  # 層間が無ければ同層許容
    if not cand_partners:
        return None

    b = _weighted_choice(rng, cand_partners, weight)
    return (a.item_id, b.item_id)


def _weighted_choice(rng: random.Random, items: list[Item], weight) -> Item:
    """重みに比例した決定論的抽選（rng のみが乱数源）。"""
    weights = [max(weight(it), 1e-12) for it in items]
    total = sum(weights)
    threshold = rng.random() * total
    upto = 0.0
    for it, w in zip(items, weights):
        upto += w
        if threshold <= upto:
            return it
    return items[-1]


# ---------------------------------------------------------------- updated_exposure

def updated_exposure(exposure: ExposureCounts, pairs: list[Pair]) -> ExposureCounts:
    """生成ペア（本番のみ）で露出カウントを更新した新カウントを返す（純粋）。

    本番未使用。PBT のオラクル（モデル）として derive_exposure と整合検証（P-5）。
    練習ペアは集計対象外（BR-08）。
    """
    new: ExposureCounts = dict(exposure)
    for pair in pairs:
        if pair.is_practice:
            continue
        new[pair.item_left] = new.get(pair.item_left, 0) + 1
        new[pair.item_right] = new.get(pair.item_right, 0) + 1
    return new


# ---------------------------------------------------------------- derive_exposure

@dataclass
class SessionExposure:
    """derive_exposure の入力（確定 PairSequence + セッション活性）。"""
    status: str                       # 'unused' | 'in_progress' | 'completed'
    pairs: list[Pair] = field(default_factory=list)
    last_active_at: str | None = None  # ISO8601（in_progress の非アクティブ判定用）


def derive_exposure(
    sessions: list[SessionExposure],
    *,
    now_iso: str,
    inactive_threshold_hours: int = 48,
) -> ExposureCounts:
    """確定 PairSequence から露出を集計する（H-2, 保持テーブルなし）。

    対象: status == 'completed'、または status == 'in_progress' かつアクティブ
    （last_active_at が閾値内, BR-04）。練習ペアは除外（BR-08）。
    """
    now = _iso_to_epoch(now_iso)
    threshold = inactive_threshold_hours * 3600
    counts: ExposureCounts = {}
    for s in sessions:
        if not _is_active(s, now, threshold):
            continue
        for pair in s.pairs:
            if pair.is_practice:
                continue
            counts[pair.item_left] = counts.get(pair.item_left, 0) + 1
            counts[pair.item_right] = counts.get(pair.item_right, 0) + 1
    return counts


def _is_active(s: SessionExposure, now: float, threshold: float) -> bool:
    if s.status == "completed":
        return True
    if s.status == "in_progress":
        if s.last_active_at is None:
            return False
        return (now - _iso_to_epoch(s.last_active_at)) <= threshold
    return False


def _iso_to_epoch(iso: str) -> float:
    """ISO8601(UTC, 'YYYY-MM-DDTHH:MM:SSZ') → epoch 秒。"""
    return calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))
