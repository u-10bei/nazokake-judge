"""ParticipantLog — 参加者操作の秘匿ログ強制点（DP-U2-03 / U2-NFR-03）。

U4a AdminLog と対をなす。**トークン生値・謎かけ本文を構造的に排除**（許可フィールドのみ
U1 `emit` に渡す）。相関が要る箇所は `token_hash()`（SHA-256 先頭 8 文字・単一規約）を使い、
生値は決してログに出さない。wrangler tail で特定参加者フローを生値なしで追える。
"""

from __future__ import annotations

import hashlib

from backend.log import emit

# 参加者ログに出してよいフィールド（token 生値 / body は含めない）。
_ALLOWED = frozenset({
    "endpoint", "result", "phase", "status",
    "token_h",          # token_hash の値のみ（生値ではない）
    "pair_id", "target_ref", "duplicate", "done", "total",
})


def token_hash(token: str) -> str:
    """トークンの非可逆な相関キー（SHA-256 先頭 8 文字, 単一ユーティリティ）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def participant_log(event: str, level: str = "info", **fields: object) -> None:
    """許可フィールドのみで構造化ログを発行する（token 生値/body は排除）。"""
    safe = {k: v for k, v in fields.items() if k in _ALLOWED}
    emit(event, level, unit="U2", **safe)
