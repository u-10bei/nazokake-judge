"""α/S 較正ハーネス（DP-08 と共有実装）。

P-1（露出偏りの許容範囲）の検証と α/S 較正シミュレーションで**同一の累積ループ**を
共有し、較正ループと検証ループの乖離・二重実装を防ぐ（NFR Design 申し送り）。

述語の形は設計固定（`max−min ≤ max(2, α×mean)`, business-logic-model.md P-1）。
定数 α / S は暫定値で、Build & Test 段階の較正シミュレーションで確定する。
"""

from __future__ import annotations

from backend.domain import generate_pairs, updated_exposure
from schema import AssignmentParams, Item, Layer

# 暫定値（Negotiable）。Build & Test の較正シミュレーションで確定する。
ALPHA_PROVISIONAL = 0.5
S_PROVISIONAL = 30


def cumulative_exposure(
    pool: list[Item], params: AssignmentParams, s_sessions: int, base_seed: int = 0
) -> dict[str, int]:
    """S セッションを固定シードで逐次生成し、updated_exposure でフィードバックした
    最終露出カウントを返す（ステートフル累積ハーネス）。"""
    exposure: dict[str, int] = {}
    for s in range(s_sessions):
        pairs = generate_pairs(pool, exposure, seed=base_seed + s, params=params)
        exposure = updated_exposure(exposure, pairs)
    return exposure


def exposure_balance_ok(
    exposure: dict[str, int], pool: list[Item], alpha: float = ALPHA_PROVISIONAL
) -> bool:
    """P-1 述語: 適格項目の露出で `max−min ≤ max(2, α×mean)`。"""
    counts = [exposure.get(it.item_id, 0) for it in pool]
    if not counts:
        return True
    lo, hi = min(counts), max(counts)
    mean = sum(counts) / len(counts)
    return (hi - lo) <= max(2.0, alpha * mean)


def _fixed_pool(n: int = 16) -> list[Item]:
    """較正/検証用の固定プール（全 4 層均等）。"""
    layers = list(Layer)
    return [
        Item(item_id=f"it{i:03d}", layer=layers[i % len(layers)], body_ref=f"ref{i:03d}")
        for i in range(n)
    ]
