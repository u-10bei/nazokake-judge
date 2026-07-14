"""トークン契約（DP-05 / TSD-05 / U1-NFR-08）。

契約は U1 で規定し、発行実装（U4a token_issue）はこれに従う。
- エントロピー: 128-bit 以上（`secrets.token_urlsafe(16)` = 16 バイト）
- 文字集合: URL-safe base64（[A-Za-z0-9_-]）
- 長さ: 16 バイト → 22 文字前後
"""

from __future__ import annotations

import re
import secrets

TOKEN_BYTES = 16                       # 128-bit（256-bit は URL 長の不便のみ, 不採用）
TOKEN_MIN_LENGTH = 22                  # base64url(16 bytes) の最小長
_TOKEN_CHARSET = re.compile(r"^[A-Za-z0-9_-]+$")


def generate_token() -> str:
    """契約に適合するトークンを 1 つ生成する（U4a 発行が利用）。"""
    return secrets.token_urlsafe(TOKEN_BYTES)


def is_valid_token(token: str) -> bool:
    """トークンが契約（長さ・文字集合）に適合するか判定する。"""
    return (
        isinstance(token, str)
        and len(token) >= TOKEN_MIN_LENGTH
        and bool(_TOKEN_CHARSET.match(token))
    )
