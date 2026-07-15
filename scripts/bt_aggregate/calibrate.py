"""LC-U4b-05 — calibrate（純・Likert 較正, BR-U4b-05/06）。

ブリッジ Likert を較正アンカーとして BT 尺度を解釈可能尺度へ写像する（推定には
組み込まない）。`likert.target_ref = 評定対象の item_id` で θ と結合する。

アンカー = {推定対象 item ∩ Likert 平均あり ∩ target_ref ∈ items}。
`target_ref ∉ items` のアンカーは較正から除外 + 警告（自己完結保証は judgments のみで
likert には及ばない, BR-U4b-05）。

(平均 Likert, θ) を単回帰 θ ≈ slope·L + intercept（閉形式）で当てる。
⇒ calibrated_score = (θ − intercept) / slope（Likert 相当尺度への写像）。

スキップ条件（BR-U4b-06, いずれかで None + 警告）: アンカー 2 件未満 / θ 分散ゼロ
（全同点）/ Likert 分散ゼロ（slope 不定）/ slope≈0。誤った較正で解釈を歪めない。
"""

from __future__ import annotations

from schema import Calibration

_SLOPE_EPS = 1e-12


class CalibrationOutcome:
    """calibrate の結果（較正 or スキップ理由）と較正から除外したアンカーを保持する。"""

    __slots__ = ("calibration", "skip_reason", "excluded_targets")

    def __init__(self, calibration, skip_reason, excluded_targets):
        self.calibration = calibration                 # Calibration | None
        self.skip_reason = skip_reason                 # str | None（None=較正成立）
        self.excluded_targets = excluded_targets       # sorted list[str]（target_ref∉items）


def calibrate(theta: dict[str, float], likert, item_ids) -> CalibrationOutcome:
    """theta（推定対象）と likert からアンカー単回帰を求める。

    - theta: 推定対象 item の θ（成分内 Σθ=0）。
    - likert: `target_ref` / `rating` 属性を持つオブジェクト列（ExportLikert）。
    - item_ids: 全 item_id 集合（target_ref ∈ items の判定用）。
    """
    valid_ids = set(item_ids)
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    excluded: set[str] = set()
    for lk in likert:
        tref = lk.target_ref
        if tref not in valid_ids:
            excluded.add(tref)                         # target_ref ∉ items → 除外 + 警告
            continue
        sums[tref] = sums.get(tref, 0.0) + lk.rating
        counts[tref] = counts.get(tref, 0) + 1

    excluded_targets = sorted(excluded)

    # アンカー = 推定対象 ∩ Likert 平均あり（item_id 昇順で決定論）。
    anchors: list[tuple[str, float, float]] = []       # (item_id, mean_likert, theta)
    for item_id in sorted(theta):
        if counts.get(item_id, 0) > 0:
            mean_likert = sums[item_id] / counts[item_id]
            anchors.append((item_id, mean_likert, theta[item_id]))

    if len(anchors) < 2:
        return CalibrationOutcome(None, "anchors<2", excluded_targets)

    xs = [a[1] for a in anchors]                       # 平均 Likert
    ys = [a[2] for a in anchors]                       # θ
    n = len(anchors)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    if var_y == 0.0:                                   # θ 分散ゼロ（全同点）
        return CalibrationOutcome(None, "theta-variance-zero", excluded_targets)
    if var_x == 0.0:                                   # Likert 分散ゼロ（slope 不定）
        return CalibrationOutcome(None, "likert-variance-zero", excluded_targets)

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = cov / var_x
    if abs(slope) < _SLOPE_EPS:                        # slope≈0
        return CalibrationOutcome(None, "slope-near-zero", excluded_targets)
    intercept = mean_y - slope * mean_x

    calibration = Calibration(
        n_anchors=n,
        slope=slope,
        intercept=intercept,
        anchor_item_ids=[a[0] for a in anchors],
    )
    return CalibrationOutcome(calibration, None, excluded_targets)


def calibrated_score(theta_value: float, calibration) -> float:
    """θ を Likert 相当尺度へ写像する: (θ − intercept)/slope。"""
    return (theta_value - calibration.intercept) / calibration.slope
