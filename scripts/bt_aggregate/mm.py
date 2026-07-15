"""LC-U4b-04 — fit_bt（純・成分非依存 MM・擬似データ正則化）。

MM アルゴリズム（Hunter 2004 の標準反復）を純 Python で最尤推定する（依存ゼロ, BR-U4b-01）。
渡された**連結な**集計を推定するだけ（成分非依存）＝成分制限は graph.restrict_to_component が担う。

**α 適用位置の不変条件（Infra Design §11 / Code Gen Q2）**: 擬似データ α は本関数の内部でのみ
適用する。呼び出し側が渡す wins/pair_counts は生カウントのまま。

擬似データ拡張（BR-U4b-03・観測ペア限定）:
  各観測ペア (i,j) に仮想引き分け α 件 → w̃_ij = w_ij + α/2, ñ_ij = n_ij + α
  ⇒ w̃_i = w_i + (α/2)·d_i（d_i = 観測対戦相手数）、ñ_ij は観測ペアのみで加算。
更新式は素の Hunter: π_i ← w̃_i / Σ_j ñ_ij/(π_i+π_j)（分母は観測ペアのみ和）。

**分子に一律 α を足すだけ（(w_i+α)/…）の別式は不採用**（いかなる拡張データの最尤にも
対応しない別の regularizer, BR-U4b-01 注記）。単調性（PU4b-1）は両式で通りテストで
区別できないため、定式化を仕様と実装コメントで固定する。

決定論（U4b-NFR-01/02）: 固定初期値 π=1・item_id 昇順で Σ 加算順を固定・毎反復で
幾何平均 1 に正規化（浮動小数の加算順依存とスケールドリフトを除去）。θ=log π を返し、
最終的に **成分内 Σθ=0** に正規化する（BR-U4b-04）。
"""

from __future__ import annotations

import math

PairKey = tuple[str, str]


def fit_bt(
    wins: dict[str, int],
    pair_counts: dict[PairKey, int],
    alpha: float,
    max_iter: int,
    tol: float,
) -> tuple[dict[str, float], bool, int]:
    """連結な集計から BT 強度 θ=log π を推定する。

    returns: (theta, converged, iterations)。theta は成分内で Σθ=0 に正規化済み。
    空入力は ({}, True, 0)。α>0 のとき w̃_i>0 が保証され log/除算は有限（BR-U4b-03）。
    """
    items = sorted(wins)                              # item_id 昇順（正準ソート, DP-U4b-01）
    if not items:
        return {}, True, 0

    # 観測近傍（決定論のため相手 item_id 昇順に固定）。d_i = 観測対戦相手数。
    neighbors: dict[str, list[tuple[str, int]]] = {i: [] for i in items}
    for (a, b), n in pair_counts.items():
        neighbors[a].append((b, n))
        neighbors[b].append((a, n))
    for i in items:
        neighbors[i].sort(key=lambda t: t[0])

    degree = {i: len(neighbors[i]) for i in items}
    # 擬似データ拡張は fit_bt 内部でのみ（α 適用位置の不変条件）。
    w_tilde = {i: wins[i] + (alpha / 2.0) * degree[i] for i in items}

    pi = {i: 1.0 for i in items}                      # 固定初期値
    converged = False
    iterations = 0
    for step in range(1, max_iter + 1):
        iterations = step
        new_pi: dict[str, float] = {}
        for i in items:
            denom = 0.0
            for (j, n) in neighbors[i]:               # Σ 加算順を固定
                denom += (n + alpha) / (pi[i] + pi[j])
            new_pi[i] = (w_tilde[i] / denom) if denom > 0.0 else pi[i]
        # 幾何平均 1 に正規化（Σ log π = 0）: スケールドリフト除去で収束判定を安定化。
        log_gm = sum(math.log(new_pi[i]) for i in items) / len(items)
        gm = math.exp(log_gm)
        new_pi = {i: new_pi[i] / gm for i in items}

        max_change = max(abs(new_pi[i] - pi[i]) for i in items)
        pi = new_pi
        if max_change < tol:
            converged = True
            break

    # θ = log π、成分内 Σθ = 0（BR-U4b-04）。正規化後は log_gm=0 だが明示的に中心化。
    theta_raw = {i: math.log(pi[i]) for i in items}
    mean = sum(theta_raw[i] for i in items) / len(items)
    theta = {i: theta_raw[i] - mean for i in items}
    return theta, converged, iterations
