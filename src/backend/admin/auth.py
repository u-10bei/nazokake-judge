"""AuthGuard — Basic 認証の単一チョークポイント（DP-U4a-01 / U4a-NFR-01/05）。

`/admin/*` の全リクエストが本チェックを通る。資格情報は `env.ADMIN_BASIC_*`
（wrangler secret / .dev.vars）と**定数時間比較**（タイミング攻撃回避）。
"""

from __future__ import annotations

import base64
import hmac

from workers import Response


def check_basic(request, env) -> bool:
    """Authorization: Basic を検証する。適合すれば True。"""
    header = request.headers.get("Authorization")
    if not header or not str(header).startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(str(header)[6:]).decode("utf-8")
    except Exception:  # noqa: BLE001
        return False
    user, sep, password = decoded.partition(":")
    if not sep:
        return False

    expected_user = _env_str(env, "ADMIN_BASIC_USER")
    expected_password = _env_str(env, "ADMIN_BASIC_PASSWORD")
    if expected_user is None or expected_password is None:
        return False
    # 定数時間比較（両方評価してから AND）。
    ok_user = hmac.compare_digest(user, expected_user)
    ok_password = hmac.compare_digest(password, expected_password)
    return ok_user and ok_password


def unauthorized() -> Response:
    """401 + WWW-Authenticate（Basic 認証プロンプト）。"""
    return Response(
        "Unauthorized",
        status=401,
        headers={"WWW-Authenticate": 'Basic realm="admin"'},
    )


def _env_str(env, name: str) -> str | None:
    try:
        value = getattr(env, name)
    except AttributeError:
        return None
    return None if value is None else str(value)
