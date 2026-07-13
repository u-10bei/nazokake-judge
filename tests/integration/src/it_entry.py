"""U4a 統合テストハーネスの Worker エントリ。

実 `backend.entry.on_fetch`（/admin/* を本物の AdminApi に委譲）をそのまま使い、
テスト用の補助ルート（/it/reset, /it/seed-frozen）を足すだけ。凍結ガード（BR-U4a-03）
検証のため、参照済み item（pairs から参照される item）を直接 seed する。
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from workers import Response

from backend.entry import on_fetch as base_on_fetch

_TABLES = ("judgments", "pairs", "sessions", "likert_responses",
           "survey_responses", "tokens", "items")


def _j(obj):
    return Response(json.dumps(obj, ensure_ascii=False),
                   headers={"content-type": "application/json"})


async def on_fetch(request, env):
    path = urlparse(request.url).path

    if path == "/it/reset":
        for t in _TABLES:
            await env.DB.prepare(f"DELETE FROM {t}").run()
        return _j({"reset": True})

    if path == "/it/seed-frozen":
        # frozen001 を pairs から参照させる（= 凍結対象）。other001 は相方。
        await env.DB.prepare(
            "INSERT OR REPLACE INTO items (item_id, layer, body, body_ref) "
            "VALUES ('frozen001', 'pro', 'orig-body', NULL)").run()
        await env.DB.prepare(
            "INSERT OR REPLACE INTO items (item_id, layer, body, body_ref) "
            "VALUES ('other001', 'ai', 'other-body', NULL)").run()
        await env.DB.prepare(
            "INSERT OR IGNORE INTO tokens (token, status, issued_at, last_active_at) "
            "VALUES ('itok', 'completed', '2026-07-13T00:00:00Z', NULL)").run()
        await env.DB.prepare(
            "INSERT OR REPLACE INTO pairs (token, pair_id, idx, item_left, item_right, is_practice) "
            "VALUES ('itok', 'p0', 0, 'frozen001', 'other001', 0)").run()
        return _j({"seeded": True})

    # それ以外は本物のエントリ（/admin/* + health）に委譲。
    return await base_on_fetch(request, env)
