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

    # ヘルスチェック（U1）は専用パス `/health` のみ（catch-all にしない）。
    #
    # ★`unit: "U1+U4a+U2"` という**手で保守するユニット一覧を出していたが、U3 以降
    #   更新されず 4 ユニット分ずれていた**（実データのドライラン中に「サーバが古い」と
    #   誤診させた）。手書きの版表示は必ず腐るので、**DB から取れる事実**に置き換える。
    #
    # `schema` = 適用済み migration の先頭（例 `0005_layer_anchor_plan.sql`）。
    # 「このサーバが話している D1 のスキーマ世代」が分かる＝**デプロイとマイグレーションの
    # ずれ**（今日 2 回踏んだ事故）をこの 1 本で検出できる。
    # **取得に失敗しても status は "ok" のまま**——ヘルスチェックを DB 依存にはしない。
    if path == "/health":
        schema = None
        try:
            from backend.repo._d1 import to_py   # 関数内 import（起動 CPU 制限 10021）
            row = await env.DB.prepare(
                "SELECT name FROM d1_migrations ORDER BY id DESC LIMIT 1").first()
            if row is not None:
                schema = to_py(row).get("name")
        except Exception:            # noqa: BLE001 — 健全性の報告を DB 障害で落とさない
            schema = None
        body = {"service": "nazokake-judge", "status": "ok", "schema": schema}
        return Response(json.dumps(body, ensure_ascii=False),
                        headers={"content-type": "application/json"})

    # それ以外は未知パス。フロントは Static Assets が `/` を配信し、アセット非一致の
    # 未知パスがここへ到達する → 404 + 統一封筒（Infra Q2: SPA フォールバック不使用）。
    return Response(json.dumps({"ok": False, "error": "not found"}, ensure_ascii=False),
                    status=404,
                    headers={"content-type": "application/json", "cache-control": "no-store"})
