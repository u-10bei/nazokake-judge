"""U4a 管理 API の HTTP ペイロードモデル（単一データ契約, App Design Q6=A）。

Worker（`backend/admin/`）と scripts が同一モデルを import する。`SufficiencyResult` は
`pool_sufficiency`（backend/domain）の戻り値かつ API レスポンスの内訳（U4a Q3=A）。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schema.models import Item


class SufficiencyResult(BaseModel):
    """プール充足判定（BR-U4a-05 三点セット）の結果。ingest（warn）/ issue（gate）共通。"""
    model_config = ConfigDict(extra="forbid")

    ok: bool
    shortfalls: list[str] = Field(default_factory=list)  # 不足条件の内訳


class RejectedItem(BaseModel):
    """投入拒否された item と理由（層欠落 / 本文欠落 / 凍結ガード等）。"""
    model_config = ConfigDict(extra="forbid")

    item_id: str
    reason: str


# ---- pool_ingest ----

class ItemIngestRequest(BaseModel):
    """POST /admin/items のリクエスト（全件 bulk）。"""
    model_config = ConfigDict(extra="forbid")

    items: list[Item]


class IngestResult(BaseModel):
    """POST /admin/items のレスポンス（統一封筒, DP-U4a-07）。"""
    model_config = ConfigDict(extra="forbid")

    ok: bool
    inserted: int = 0
    updated: int = 0
    rejected: list[RejectedItem] = Field(default_factory=list)
    # マージ後プールの充足判定（BR-U4a-05）。**warning 扱いで投入は成功**（段階投入を妨げない）。
    sufficiency_warnings: list[str] = Field(default_factory=list)


# ---- token_issue ----

class TokenIssueRequest(BaseModel):
    """POST /admin/tokens のリクエスト。URL テンプレートは CLI 側の責務。"""
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1)


class TokenIssueResult(BaseModel):
    """POST /admin/tokens のレスポンス（発行時充足ゲート BR-U4a-12 込み）。"""
    model_config = ConfigDict(extra="forbid")

    ok: bool
    tokens: list[str] = Field(default_factory=list)
    issued_at: str | None = None
    # 現行プールが三点セット未達なら ok=false・tokens=[]・gate_errors に不足内訳（発行拒否）。
    gate_errors: list[str] = Field(default_factory=list)
