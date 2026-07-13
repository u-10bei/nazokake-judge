"""LC-05 LogEmitter — 構造化ログの単一発行点（DP-06 / U1-NFR-10 / TSD-06）。

JSON を標準出力へ。監視基盤・集約先は持たない（wrangler tail / ダッシュボードで運用）。
フィールド規約の強制点を本ヘルパ一箇所に集約する。相関キー: session_id / token。
"""

from __future__ import annotations

import json
import time

# 最低イベントの level 規約（TSD-06）:
#   info : seed/exposure_snapshot 参照など監査・リプレイ用
#   warning: BR-06 露出目標未達（ベストエフォート）
#   error: BR-05 構成不能 等
LEVELS = ("info", "warning", "error")


def emit(event: str, level: str = "info", *, unit: str = "U1", **fields: object) -> None:
    """構造化ログを 1 行の JSON として標準出力に発行する。

    標準フィールド: ts / level / unit / event。相関キー（session_id / token など）は
    fields で渡す。呼び出し側は本関数のみを使い、直接 print(json.dumps(...)) しない。
    """
    if level not in LEVELS:
        level = "info"
    record: dict[str, object] = {
        "ts": _now_iso(),
        "level": level,
        "unit": unit,
        "event": event,
    }
    # 相関キー・文脈フィールドを合流（標準フィールドは上書きさせない）。
    for key, value in fields.items():
        if key not in record:
            record[key] = value
    print(json.dumps(record, ensure_ascii=False))


def _now_iso() -> str:
    # time.gmtime は Worker(Pyodide)/CPython 双方で利用可。
    t = time.gmtime()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", t)
