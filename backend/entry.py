"""Worker エントリポイント（デプロイ成果物のスキャフォールド）。

U1（共有基盤）が提供するのは import 可能なモジュール（schema / domain / repo / log）まで。
参加者/管理の実ルーティングは **U2/U3** が本ファイルに配線する（API 層は U1 スコープ外）。

実装規約（G-1 本番確定, F-4/F-5/F-6）:
  - **FastAPI 不可**。raw workers API + 手動ルーティング。
  - ハンドラは **モジュールレベル `async def on_fetch(request, env)`**。
  - トップレベル import は最小限（起動 CPU 制限 10021 回避）。
"""

from __future__ import annotations

import json

from workers import Response


async def on_fetch(request, env):
    """最小ヘルスチェック。U2/U3 が `env.DB` を使う実ルートを本関数に追加する。"""
    body = {"service": "nazokake-judge", "status": "ok", "unit": "U1-foundation"}
    return Response(json.dumps(body, ensure_ascii=False),
                    headers={"content-type": "application/json"})
