"""U4b BT 集計の出力契約（BTResult 正本, US-R04）。

`scripts/bt_aggregate` が生成する。入力は U3 の `ExportBundle`（admin_views.py・再定義
しない）。**DDL 変更なし**（U4b は D1 非依存・ファイル入出力のみ, BR-U4b-13）。

出力チャネル: JSON（機械可読・監査）と人間可読テーブル（stderr, CLI 側で整形）。
`source` は入力スナップショットのエコーバック（BR-U4b-09）で、結果ファイル単体から
どの時点のエクスポート由来かを追える（反復判定装置の取り違え防止）。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BTSource(BaseModel):
    """入力 ExportBundle のスナップショット識別子（BR-U4b-09）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    exported_at: str


class Calibration(BaseModel):
    """Likert 較正（BR-U4b-05）。(平均 Likert, θ) の単回帰 θ≈slope·L+intercept。

    calibrated_score = (θ − intercept) / slope（Likert 相当尺度への写像）。スキップ時は
    BTResult.calibration=null（BR-U4b-06）。
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    n_anchors: int = Field(ge=2)
    slope: float
    intercept: float
    anchor_item_ids: list[str] = Field(default_factory=list)


class BTItemScore(BaseModel):
    """item 1 件のスコア。除外 item は bt_score=null+component で可視化（BR-U4b-07）。

    matches/wins は **U3 winrate と同一定義・生の観測カウント**（BR-U4b-08・PU4b-6）。
    α 擬似データは fit_bt 内部でのみ適用され、ここには乗らない（Infra Design §11 不変条件）。
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    layer: str
    bt_score: float | None = None          # θ = log π（最大連結成分内で Σθ=0）
    calibrated_score: float | None = None  # (θ − intercept)/slope（アンカーありのとき）
    component: int | None = None           # 所属連結成分 ID（0=最大＝推定対象）。孤立は null
    rank: int | None = None                # 推定対象内の順位（スコア降順・同値は item_id 昇順）
    matches: int = Field(ge=0)             # 出場数（生カウント）
    wins: int = Field(ge=0)                # 勝ち数（生カウント）


class BTResult(BaseModel):
    """BT 集計結果の正本（US-R04）。"""
    model_config = ConfigDict(extra="forbid")

    source: BTSource
    n_items: int = Field(ge=0)
    n_comparisons: int = Field(ge=0)                 # 本番判定数（練習は U3 が除外済み）
    n_components: int = Field(ge=0)                  # 比較グラフの連結成分数
    estimated_component_size: int = Field(ge=0)      # 推定対象（最大連結成分）の item 数
    converged: bool
    iterations: int = Field(ge=0)
    alpha: float                                     # 使用した正則化（観測ペア限定, BR-U4b-03）
    items: list[BTItemScore] = Field(default_factory=list)  # 全 item（除外分も残す）
    calibration: Calibration | None = None
    warnings: list[str] = Field(default_factory=list)
