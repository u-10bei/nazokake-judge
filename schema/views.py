"""U2 参加者 API のレスポンス契約（ビュー型）。

**出自秘匿の型による強制（DP-U2-02 / U2-NFR-06）**: 参加者へ返すのは本ビュー型のみ。
`Item`（layer/body_ref 込み）・`Session`（seed/exposure_snapshot 込み）を直接シリアライズ
しない。`ItemView` は `item_id` と `body` のみを持ち、`layer`/`body_ref`/`seed`/
`exposure_snapshot` は**型に存在しない**（＝事故で出せない）。

Worker（`backend/participant/`）が生成し、フロント（`frontend/`）が消費する単一データ契約。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ItemView(BaseModel):
    """参加者に見せる作品（本文のみ）。出自（layer/body_ref）は含めない。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    body: str


class PairView(BaseModel):
    """判定画面の 1 ペア。A=left(上/先)、B=right(下/後)（BR-07）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    pair_id: str
    index: int
    left: ItemView                     # A
    right: ItemView                    # B
    is_practice: bool = False          # 表示上の練習明示（集計判定はサーバ内部, H-3）


class LikertScale(BaseModel):
    """Likert 尺度範囲（rating ∈ [min, max], BR-U2-18）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    min: int = 1
    max: int = 7


class LikertTargetView(BaseModel):
    """Likert 画面の 1 対象。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_ref: str                    # 評定対象 item_id（送信キー）
    body: str
    scale: LikertScale = Field(default_factory=LikertScale)


class Progress(BaseModel):
    """進捗（done/total）。判定は本番のみ、練習は別カウント（BR-U2-13）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    done: int = Field(ge=0)
    total: int = Field(ge=0)


class SessionView(BaseModel):
    """`GET /api/session` の主レスポンス（サーバ権威, U2-NFR-09）。

    status/phase をサーバが導出し、次に提示すべき pair/likert・進捗も算出して載せる。
    クライアントは描画のみ（楽観更新なし）。
    """
    model_config = ConfigDict(extra="forbid")

    status: str                        # 'unused' | 'in_progress' | 'completed'
    phase: str                         # 'practice'|'judging'|'likert'|'survey'|'done'
    next_pair: PairView | None = None       # practice/judging で次に提示
    next_likert: LikertTargetView | None = None  # likert で次に評定
    progress: Progress                      # 本番判定 done/total
    practice: Progress                      # 練習 done/total


class SubmitResult(BaseModel):
    """`POST /api/judgment` のレスポンス（冪等観測 + 再同期, Q6）。"""
    model_config = ConfigDict(extra="forbid")

    saved: bool                        # 今回保存されたか（初回 true）
    duplicate: bool                    # 再送で既存と一致（冪等観測）
    choice: str                        # 保存されている（初回の）choice: 'A'|'B'
    next_pair: PairView | None = None
    phase: str
    progress: Progress


class ApiError(BaseModel):
    """業務エラー統一封筒（200 + ok=false, BR-U2-29 / DP-U2-07）。"""
    model_config = ConfigDict(extra="forbid")

    ok: bool = False
    error: str
    phase: str | None = None
