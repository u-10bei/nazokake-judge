"""Worker エントリポイント。

U1 の最小ヘルスに加え、**U4a が `/admin/*`（管理 API）を配線**する。参加者/研究者の
実ルーティングは U2/U3 が別接頭辞で追加する。

実装規約（G-1 本番確定, F-4/F-5/F-6）:
  - **FastAPI 不可**。raw workers API + 手動ルーティング。
  - ハンドラは **モジュールレベル `async def on_fetch(request, env)`**。
  - トップレベル import は最小限（起動 CPU 制限 10021 回避）。重い import は関数内へ。
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from workers import Response


async def on_fetch(request, env):
    path = urlparse(request.url).path

    # /admin/* は AuthGuard（単一チョークポイント）→ AdminApi へ委譲（U4a, Q1=A）。
    if path.startswith("/admin/"):
        from backend.admin.api import handle_admin  # 関数内 import で起動を軽く保つ
        return await handle_admin(request, env, path)

    # ヘルスチェック（U1）。U2/U3 が参加者/管理ルートを別接頭辞で追加する。
    body = {"service": "nazokake-judge", "status": "ok", "unit": "U1+U4a"}
    return Response(json.dumps(body, ensure_ascii=False),
                    headers={"content-type": "application/json"})
