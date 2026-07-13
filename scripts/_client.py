"""管理 API クライアント（TSD-U4a-05）。標準ライブラリ urllib のみ（追加依存なし）。

認証情報は環境変数（ADMIN_BASIC_USER / ADMIN_BASIC_PASSWORD）。ベース URL は
--base-url 引数または環境変数 ADMIN_API_BASE。
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request


def base_url(explicit: str | None = None) -> str:
    url = explicit or os.environ.get("ADMIN_API_BASE")
    if not url:
        raise SystemExit("ベース URL を --base-url または環境変数 ADMIN_API_BASE で指定してください")
    return url.rstrip("/")


def _auth_header() -> str:
    user = os.environ.get("ADMIN_BASIC_USER")
    password = os.environ.get("ADMIN_BASIC_PASSWORD")
    if not user or not password:
        raise SystemExit("ADMIN_BASIC_USER / ADMIN_BASIC_PASSWORD を環境変数で指定してください")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    """管理 API に JSON を POST し、レスポンス JSON を返す。"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"content-type": "application/json", "Authorization": _auth_header()},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))
