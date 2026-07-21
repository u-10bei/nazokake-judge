"""AdminLog — 管理操作の秘匿ログ強制点（DP-U4a-02 / U4a-NFR-03/09）。

**許可フィールドのみ**を U1 `emit` に渡す薄いラッパ。トークン生値・謎かけ本文（未公表
研究刺激）を**構造的に受け付けない**（許可外キーは黙って落とす）。呼び出し側の規律に
依存しない。
"""

from __future__ import annotations

from backend.log import emit

# 管理ログに出してよいフィールド（token / body は含めない）。
#
# ⚠️ **フィールドを増やすときは必ずここに追加する**——許可外キーは**黙って落ちる**ため、
#    追加を忘れると「ログには出ているつもりで実は記録されていない」状態になる。
#    `tests/unit/u4a/test_admin_log_allowlist.py` が src 内の全 `admin_log` 呼び出しを
#    走査して漏れを検出する（U5/U6 で実際に 13 フィールドが落ちていた）。
_ALLOWED = frozenset({
    # U4a: 投入・発行
    "endpoint", "result", "count", "item_id", "item_ids",
    "inserted", "updated", "rejected_count",
    # U5: 出題停止（★どの作品を止めたかが著作権対応の証跡そのもの）
    "already", "not_found",
    # U6: プラン投入・有効化（★content_hash が「コミットされたものが投入された」の証跡）
    "plan_set", "plan_index", "content_hash", "seed", "attempt",
    "rows", "likert", "missing", "reason", "blocking_set",
})


def admin_log(event: str, level: str = "info", **fields: object) -> None:
    """許可フィールドのみで構造化ログを発行する（token/body は排除）。"""
    safe = {k: v for k, v in fields.items() if k in _ALLOWED}
    emit(event, level, unit="U4a", **safe)
