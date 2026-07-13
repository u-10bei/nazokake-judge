"""α/S 較正ハーネス（DP-08 と共有実装）。

P-1（露出偏りの許容範囲）の検証と α/S 較正シミュレーションで**同一の累積ループ**を
共有し、較正ループと検証ループの乖離・二重実装を防ぐ（NFR Design 申し送り）。

述語の形は設計固定（`max−min ≤ max(2, α×mean)`, business-logic-model.md P-1）。
**定数は 2026-07-13 の較正シミュレーションで確定**（本番規模 95 件・40 ペア/セッションで
20 試行の最悪 gap を評価）: 重み指数 p=3・α=0.7・S=30。
"""

from __future__ import annotations

from backend.domain import generate_pairs, updated_exposure
from schema import AssignmentParams, Item, Layer

# 較正確定（2026-07-13）。p=3 の S=30 最悪 α≈0.475 に対し約 1.5 倍のマージンで α=0.7。
# 述語は「S=30 累積後に評価」であり全 S に対する主張ではない（設計どおり）。
ALPHA = 0.7
S = 30

# 本番規模プールの層構成（実験計画 Q10=B, 計 95 件）。
_REALISTIC_LAYER_COUNTS = {Layer.PRO: 30, Layer.AI: 20, Layer.EDIT: 30, Layer.RULE: 15}


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
    exposure: dict[str, int], pool: list[Item], alpha: float = ALPHA
) -> bool:
    """P-1 述語: 適格項目の露出で `max−min ≤ max(2, α×mean)`。"""
    counts = [exposure.get(it.item_id, 0) for it in pool]
    if not counts:
        return True
    lo, hi = min(counts), max(counts)
    mean = sum(counts) / len(counts)
    return (hi - lo) <= max(2.0, alpha * mean)


def _realistic_pool() -> list[Item]:
    """本番規模プール（95 件, pro30/ai20/edit30/rule15）。P-1 は本レジームで評価する。"""
    pool: list[Item] = []
    i = 0
    for layer, count in _REALISTIC_LAYER_COUNTS.items():
        for _ in range(count):
            pool.append(Item(item_id=f"it{i:03d}", layer=layer,
                             body=f"body{i:03d}", body_ref=f"ref{i:03d}"))
            i += 1
    return pool


def _fixed_pool(n: int = 16) -> list[Item]:
    """小規模プール（全 4 層均等）。smoke / 位置一様性（P-7）用。"""
    layers = list(Layer)
    return [
        Item(item_id=f"it{i:03d}", layer=layers[i % len(layers)],
             body=f"body{i:03d}", body_ref=f"ref{i:03d}")
        for i in range(n)
    ]
