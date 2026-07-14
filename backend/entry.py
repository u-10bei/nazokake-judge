"""Worker エントリポイント。

U1 の最小ヘルスに加え、**U4a が `/admin/*`（管理 API）**、**U2 が `/api/*`（参加者 API）**を
配線する。静的フロント（`frontend/`）は Workers Static Assets が同一オリジンで配信し、
アセット非一致のパス（`/api/*` 等）が本 `on_fetch` に到達する（Infra Q1=A）。

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

    # /api/* は参加者 API（トークン=資格・no-store・統一封筒）へ委譲（U2, DP-U2-01/04）。
    if path.startswith("/api/"):
        from backend.participant.api import handle_participant
        return await handle_participant(request, env, path)

    # ヘルスチェック（U1）。フロントは Static Assets が配信（`/`）、未知パスは 404（Infra Q2）。
    body = {"service": "nazokake-judge", "status": "ok", "unit": "U1+U4a+U2"}
    return Response(json.dumps(body, ensure_ascii=False),
                    headers={"content-type": "application/json"})
