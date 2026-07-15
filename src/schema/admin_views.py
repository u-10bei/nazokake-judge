"""U3 管理 API のビュー/バンドル型（研究者向けレスポンス契約）。

`ExportBundle` は **US-R04（BT 集計 = U4b）の入力契約の正本**（BR-U3-07）。U4b はこれを
変換なしで読み込む。形式変更は `schema_version`（= EXPORT_FORMAT_VERSION）の版上げを伴う。

**出自秘匿の型排除（DP-U3-02(b)）**: `ExportItem` は `body` を持たない（未公表刺激を
エクスポート経路に出さない, BR-U3-07 / NFR-08）。参加者ビュー（views.py）とは責務が異なる
ため分離する。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------- 進捗 / 勝率

class ProgressView(BaseModel):
    """進捗モニタリング（US-R01, BR-U3-04）。judgments_total は本番のみ。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    tokens_issued: int = Field(ge=0)
    tokens_started: int = Field(ge=0)      # status ∈ {in_progress, completed}
    tokens_completed: int = Field(ge=0)    # status = completed
    judgments_total: int = Field(ge=0)     # 本番判定のみ
    likert_total: int = Field(ge=0)
    survey_total: int = Field(ge=0)


class WinrateRow(BaseModel):
    """暫定勝率（US-R03・非 BT・簡易, BR-U3-05）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    layer: str
    matches: int = Field(ge=0)
    wins: int = Field(ge=0)
    winrate: float = Field(ge=0.0, le=1.0)


# --------------------------------------------------------------- エクスポート

class ExportItem(BaseModel):
    """作品（**body なし**＝未公表刺激をエクスポートに出さない, BR-U3-07）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    layer: str


class ExportJudgment(BaseModel):
    """本番判定 1 件（pairs join・choice=A→item_left 勝ち。練習は含めない）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    token: str
    pair_id: str
    pair_index: int                        # pairs.idx（順序効果分析）
    item_left: str
    item_right: str
    choice: str                            # 'A' | 'B'
    created_at: str


class ExportLikert(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    token: str
    target_ref: str
    rating: int
    created_at: str


class ExportSurvey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    token: str
    answers: dict[str, object] = Field(default_factory=dict)
    created_at: str


class ExportBundle(BaseModel):
    """US-R04/U4b 入力契約の正本（BR-U3-07）。自己完結（judgments の item ⊆ items）。"""
    model_config = ConfigDict(extra="forbid")

    schema_version: str                    # = EXPORT_FORMAT_VERSION
    exported_at: str                       # ISO8601（スナップショット時点）
    items: list[ExportItem] = Field(default_factory=list)
    judgments: list[ExportJudgment] = Field(default_factory=list)
    likert: list[ExportLikert] = Field(default_factory=list)
    surveys: list[ExportSurvey] = Field(default_factory=list)
