"""AdminLog — 管理操作の秘匿ログ強制点（DP-U4a-02 / U4a-NFR-03/09）。

**許可フィールドのみ**を U1 `emit` に渡す薄いラッパ。トークン生値・謎かけ本文（未公表
研究刺激）を**構造的に受け付けない**（許可外キーは黙って落とす）。呼び出し側の規律に
依存しない。
"""

from __future__ import annotations

from backend.log import emit

# 管理ログに出してよいフィールド（token / body は含めない）。
_ALLOWED = frozenset({
    "endpoint", "result", "count", "item_id",
    "inserted", "updated", "rejected_count",
})


def admin_log(event: str, level: str = "info", **fields: object) -> None:
    """許可フィールドのみで構造化ログを発行する（token/body は排除）。"""
    safe = {k: v for k, v in fields.items() if k in _ALLOWED}
    emit(event, level, unit="U4a", **safe)
