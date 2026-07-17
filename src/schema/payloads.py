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


# ---- pool_retire（U5: 出題停止） ----

class ItemRetireRequest(BaseModel):
    """POST /admin/items/retire | /admin/items/unretire のリクエスト（U5, BR-U5-06/07）。

    retire / unretire で共用（操作はルート名で明示＝ブール引数で意味を変えない, TSD-U5-04）。
    **retired_at は受け取らない**: 廃止時刻はサーバが決め、クライアントは対象しか指定できない。
    """
    model_config = ConfigDict(extra="forbid")

    item_ids: list[str] = Field(min_length=1)


class RetireResult(BaseModel):
    """retire / unretire のレスポンス（BR-U5-06/07）。

    冪等: 既に目的の状態なら no-op（retire では初回の retired_at を保持）。
    `not_found` はエラーにせず部分成功として報告する（U5-NFR-11: 「既に存在しない＝
    目的は達成」ゆえ CLI も exit 0。ただし警告は出す）。
    """
    model_config = ConfigDict(extra="forbid")

    ok: bool
    retired: int = Field(default=0, ge=0)                        # 今回状態を変えた件数
    already_retired: list[str] = Field(default_factory=list)     # no-op（unretire では既に現役）
    not_found: list[str] = Field(default_factory=list)           # items に存在しない item_id
