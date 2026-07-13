"""schema/ — 全ユニット共有のデータ契約（U1 C-SCHEMA / LC-01）。

**狭い公開面**（DP-07）: 上位ユニット（backend / scripts）はモデル型と明示バリデート
関数のみを import する。Pydantic 実装は内部に隠蔽し、将来フォールバック（TSD-02）へ
差し替える場合も本モジュールの公開面を保てば上位に波及しない。
"""

from __future__ import annotations

from schema.models import (
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
from schema.tokens import (
    TOKEN_BYTES,
    TOKEN_MIN_LENGTH,
    generate_token,
    is_valid_token,
)
from schema.version import EXPORT_FORMAT_VERSION

__all__ = [
    # モデル型
    "Item", "Token", "Session", "Pair", "PairSequence", "Judgment",
    "LikertResponse", "SurveyResponse", "SessionState", "AssignmentParams",
    "ExposureCounts",
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
