"""schema/ — 全ユニット共有のデータ契約（U1 C-SCHEMA / LC-01）。

**狭い公開面**（DP-07）: 上位ユニット（backend / scripts）はモデル型と明示バリデート
関数のみを import する。Pydantic 実装は内部に隠蔽し、将来フォールバック（TSD-02）へ
差し替える場合も本モジュールの公開面を保てば上位に波及しない。
"""

from __future__ import annotations

from schema.models import (
    POOL_LAYERS,
    REQUIRED_LAYERS,
    AssignmentParams,
    Choice,
    ExposureCounts,
    Item,
    Judgment,
    Layer,
    LikertResponse,
    Pair,
    PairSequence,
    Session,
    SessionPhase,
    SessionState,
    SurveyResponse,
    Token,
    TokenStatus,
)
from schema.payloads import (
    AssignmentPlanMeta,
    AssignmentPlanRow,
    IngestResult,
    ItemIngestRequest,
    ItemRetireRequest,
    PlanActivateRequest,
    PlanIngestRequest,
    PlanVerification,
    RejectedItem,
    RetireResult,
    SufficiencyResult,
    TokenIssueRequest,
    TokenIssueResult,
)
from schema.tokens import (
    TOKEN_BYTES,
    TOKEN_MIN_LENGTH,
    generate_token,
    is_valid_token,
)
from schema.version import EXPORT_FORMAT_VERSION
from schema.views import (
    ApiError,
    ItemView,
    LikertScale,
    LikertTargetView,
    PairView,
    Progress,
    SessionView,
    SubmitResult,
)
from schema.admin_views import (
    ExportBundle,
    ExportItem,
    ExportJudgment,
    ExportLikert,
    ExportSurvey,
    ProgressView,
    WinrateRow,
)
from schema.bt import (
    BTItemScore,
    BTResult,
    BTSource,
    Calibration,
)

__all__ = [
    # モデル型
    "Item", "Token", "Session", "Pair", "PairSequence", "Judgment",
    "LikertResponse", "SurveyResponse", "SessionState", "AssignmentParams",
    "ExposureCounts",
    # U4a ペイロードモデル
    "ItemIngestRequest", "IngestResult", "RejectedItem", "SufficiencyResult",
    "TokenIssueRequest", "TokenIssueResult",
    # U5 出題停止（retire/unretire）ペイロードモデル
    "ItemRetireRequest", "RetireResult",
    # U6 事前生成割当（プラン）
    "AssignmentPlanRow", "AssignmentPlanMeta", "PlanIngestRequest",
    "PlanActivateRequest", "PlanVerification",
    # U6 層の用途別リスト（BR-U6-05）
    "POOL_LAYERS", "REQUIRED_LAYERS",
    # U2 ビュー型（参加者 API レスポンス契約）
    "ItemView", "PairView", "LikertScale", "LikertTargetView", "Progress",
    "SessionView", "SubmitResult", "ApiError",
    # U3 管理/エクスポート型（ExportBundle は U4b 入力契約の正本）
    "ProgressView", "WinrateRow", "ExportBundle", "ExportItem",
    "ExportJudgment", "ExportLikert", "ExportSurvey",
    # U4b BT 集計の出力契約（BTResult 正本）
    "BTResult", "BTItemScore", "BTSource", "Calibration",
    # 列挙
    "Layer", "TokenStatus", "SessionPhase", "Choice",
    # 明示バリデート関数（トークン契約）
    "generate_token", "is_valid_token", "TOKEN_BYTES", "TOKEN_MIN_LENGTH",
    # バージョン
    "EXPORT_FORMAT_VERSION",
    # 明示バリデート関数（モデル）
    "validate_item", "validate_pair", "validate_judgment",
]


def validate_item(data: dict) -> Item:
    """dict を Item として検証（層ラベル必須, BR-11）。不正は ValidationError。"""
    return Item.model_validate(data)


def validate_pair(data: dict) -> Pair:
    """dict を Pair として検証。"""
    return Pair.model_validate(data)


def validate_judgment(data: dict) -> Judgment:
    """dict を Judgment として検証（choice ∈ {A,B}）。"""
    return Judgment.model_validate(data)
