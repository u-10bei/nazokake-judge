"""U1 C-SCHEMA — 全ユニット共有のデータ契約（Pydantic v2）。

単一データ契約（App Design Q6=A）: Worker（backend）と scripts が本モジュールを
import して同一の型・検証を共有する。トップレベル import は pydantic のみ（F-4）。

公開面は狭く保つ（DP-07）: 実装（Pydantic v2 / 将来のフォールバック）は本モジュール
内に隠蔽し、上位は型と `schema/__init__.py` が公開する検証関数のみを使う。
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------- 列挙

class Layer(str, Enum):
    """刺激プールの層（Q10=B, BR-11）。層ラベルは必須・欠落は投入拒否。"""
    PRO = "pro"        # プロ作品層
    AI = "ai"          # AI 生成層
    EDIT = "edit"      # 編集・自作層
    RULE = "rule"      # ルールベース生成層


class TokenStatus(str, Enum):
    """トークン状態。遷移は一方向（BR-09）: unused → in_progress → completed。"""
    UNUSED = "unused"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class SessionPhase(str, Enum):
    """参加者フローの線形フェーズ（US-P 一連）。"""
    INSTRUCTION = "instruction"
    PRACTICE = "practice"
    JUDGING = "judging"
    LIKERT = "likert"
    SURVEY = "survey"
    DONE = "done"


class Choice(str, Enum):
    """A/B 判定。A=左(item_left)/上, B=右(item_right)/下（BR-07 と対応）。"""
    A = "A"
    B = "B"


# --------------------------------------------------------------------- モデル

class Item(BaseModel):
    """刺激（作品）。**本文 `body` は D1 に格納**（U4a Q5=X）。

    NFR-08 の「リポジトリ管理外」= git リポジトリを指し、DB は対象外（README「刺激は
    デプロイ時に別経路で投入する」＝投入先が D1）。投入用 JSON ファイル自体は gitignore。
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1)
    layer: Layer                          # NOT NULL（BR-11）
    body: str = Field(min_length=1)       # 謎かけ本文（D1 格納。U2 が表示に使う）
    body_ref: str | None = None           # 出自メモ（任意。コレクション番号・制作系列 ID 等）


class Token(BaseModel):
    """個別トークン。エントロピー契約は schema/tokens.py（DP-05, TSD-05）。"""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    status: TokenStatus = TokenStatus.UNUSED
    issued_at: str                         # ISO8601（生成時に付与）
    last_active_at: str | None = None      # 逐次更新（BR-04 の非アクティブ判定に使用）


class Pair(BaseModel):
    """1 比較ペア。位置（left/right）は一様ランダムに割当・記録（BR-07）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    pair_id: str = Field(min_length=1)
    index: int = Field(ge=0)               # セッション内の提示順
    item_left: str = Field(min_length=1)   # A（先/上）
    item_right: str = Field(min_length=1)  # B（後/下）
    is_practice: bool = False              # 練習/本番はサーバが構成から決定（BR-10）


class PairSequence(BaseModel):
    """あるトークンのために確定したペア列（原子保存の単位, DP-01）。"""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    pairs: list[Pair]


class Session(BaseModel):
    """セッション状態。seed / exposure_snapshot は監査リプレイ用（Q4=B）。"""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    phase: SessionPhase = SessionPhase.INSTRUCTION
    seed: int
    exposure_snapshot: dict[str, int] = Field(default_factory=dict)  # 割当時に参照した露出値
    created_at: str


class Judgment(BaseModel):
    """判定。(token, pair_id) で冪等（一意制約, DP-02/BR-08）。練習は集計対象外。"""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    choice: Choice
    created_at: str


class LikertResponse(BaseModel):
    """ブリッジ Likert 評定（BT 尺度の較正アンカー）。"""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    rating: int = Field(ge=1, le=7)
    created_at: str


class SurveyResponse(BaseModel):
    """事後アンケート（設問プールは確定後に拡張, 暫定）。"""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)
    answers: dict[str, object] = Field(default_factory=dict)
    created_at: str


class SessionState(BaseModel):
    """XC-02 ラウンドトリップ対象（H-3）: 確定 PairSequence + 再開位置。

    seed / exposure_snapshot は監査用でラウンドトリップ対象外（本モデルに含めない）。
    """
    model_config = ConfigDict(extra="forbid")

    pairs: list[Pair]
    next_index: int = Field(ge=0)          # 次の未回答ペアの index（再開位置）


class AssignmentParams(BaseModel):
    """割当パラメータ（暫定値=Negotiable, business-rules.md と一致）。"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_pairs: int = Field(default=40, ge=1)          # 本番ペア数
    practice_pairs: int = Field(default=3, ge=0)          # 練習ペア数
    likert_items: int = Field(default=10, ge=0)           # ブリッジ Likert 項目数
    cross_layer_min_ratio: float = Field(default=0.65, ge=0.0, le=1.0)  # 層間ペア比率下限（BR-03）
    max_item_occurrence_k: int = Field(default=3, ge=1)   # セッション内 同一項目出現上限（BR-02）
    inactive_threshold_hours: int = Field(default=48, ge=1)  # 非アクティブ除外閾値（BR-04）
    # Likert 固定アンカー（U2, BR-U2-15）。None/空なら全 seed ランダム、指定時は優先採用し
    # 不足分を seed 層均等補充。方針（全固定/混合/全ランダム）はプール凍結時に確定（Negotiable）。
    likert_fixed_targets: tuple[str, ...] | None = None


# ExposureCounts は item_id → 露出回数 の写像（導出値・非永続, H-2）。
ExposureCounts = dict[str, int]
