"""ParticipantApi — 参加者エンドポイント境界（`/api/*`, LC-U2-01）。

- **トークン検証チョークポイント**（入口で token 解決・存在検証, DP-U2-01）。状態別分岐は
  各ハンドラ（GET session は完了画面 / POST 系は completed 拒否, BR-U2-25/26）。
- **no-store 共通レスポンスヘルパ**（全 `/api/*` に Cache-Control: no-store, DP-U2-04）。
- **統一エラー封筒**（業務エラー = 200 + {ok:false,...}, DP-U2-07）。

Basic 認証は付けない（トークン=資格, U2-NFR-01）。raw workers API + on_fetch 手動ディスパッチ。
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from workers import Response

from backend.participant import response as resp
from backend.participant import session as sess
from backend.participant import survey as srv
from backend.participant.errors import ParticipantError
from backend.participant.log import participant_log, token_hash
from backend.repo import Repository
from schema import AssignmentParams, ApiError


def _json(model_or_dict, status: int = 200) -> Response:
    """no-store を必ず付ける JSON レスポンス（DP-U2-04）。"""
    if hasattr(model_or_dict, "model_dump_json"):
        body = model_or_dict.model_dump_json()
    else:
        body = json.dumps(model_or_dict, ensure_ascii=False)
    return Response(body, status=status, headers={
        "content-type": "application/json",
        "cache-control": "no-store",
    })


def _error(message: str, phase: str | None = None) -> Response:
    """業務エラー統一封筒（200 + ok=false, BR-U2-29）。"""
    return _json(ApiError(error=message, phase=phase))


async def handle_participant(request, env, path: str) -> Response:
    """`/api/*` の単一エントリ（トークン検証チョークポイント → ディスパッチ）。"""
    method = str(request.method)

    if path == "/api/ping" and method == "GET":
        # Step 1 beta 検証用（Static Assets × Python Workers の実行順確認）。
        return _json({"ok": True, "unit": "U2", "route": "api"})

    repo = Repository(env.DB)
    params = AssignmentParams()

    try:
        if path == "/api/session" and method == "GET":
            return await _handle_session(request, repo, params)
        if path == "/api/judgment" and method == "POST":
            return await _handle_judgment(request, repo, params)
        if path == "/api/likert" and method == "POST":
            return await _handle_likert(request, repo, params)
        if path == "/api/survey" and method == "POST":
            return await _handle_survey(request, repo, params)
    except ParticipantError as e:
        return _error(e.message, e.phase)

    return _json({"error": "not found"}, status=404)


# ------------------------------------------------------------ トークン解決（入口集約）

def _token_from_query(request) -> str | None:
    qs = parse_qs(urlparse(request.url).query)
    vals = qs.get("token")
    return vals[0] if vals else None


async def _body(request) -> dict:
    raw = await request.text()
    try:
        return json.loads(str(raw))
    except (ValueError, TypeError):
        raise ParticipantError("リクエスト本文が不正")


async def _require_token(repo, token: str | None):
    """トークン存在検証（DP-U2-01）。無効/存在なしは業務エラー。"""
    if not token:
        raise ParticipantError("トークンがありません（US-P01）")
    tok = await repo.get_token(token)
    if tok is None:
        raise ParticipantError("無効なトークンです（US-P01）")
    return tok


# ------------------------------------------------------------ ハンドラ（状態別分岐）

async def _handle_session(request, repo, params):
    token = _token_from_query(request)
    tok = await _require_token(repo, token)
    # completed は build_view が status=completed の SessionView を返す（完了画面, BR-U2-25）。
    view = await sess.start_or_resume(repo, token, params)
    participant_log("session_view", "info", endpoint="/api/session",
                    token_h=token_hash(token), phase=view.phase, status=view.status)
    return _json(view)


async def _handle_judgment(request, repo, params):
    data = await _body(request)
    token = data.get("token")
    tok = await _require_token(repo, token)
    if tok.status == "completed":
        raise ParticipantError("完了済みのトークンです（新規回答不可, BR-U2-25）", phase="done")
    result = await resp.submit_judgment(
        repo, token, str(data.get("pair_id", "")), str(data.get("choice", "")), params
    )
    participant_log("judgment", "info", endpoint="/api/judgment",
                    token_h=token_hash(token), pair_id=str(data.get("pair_id", "")),
                    duplicate=result.duplicate, phase=result.phase)
    return _json(result)


async def _handle_likert(request, repo, params):
    data = await _body(request)
    token = data.get("token")
    tok = await _require_token(repo, token)
    if tok.status == "completed":
        raise ParticipantError("完了済みのトークンです（BR-U2-25）", phase="done")
    rating = data.get("rating")
    if not isinstance(rating, int):
        raise ParticipantError("rating は 1〜7 の整数（BR-U2-18）")
    view = await srv.submit_likert(
        repo, token, str(data.get("target_ref", "")), rating, params
    )
    participant_log("likert", "info", endpoint="/api/likert",
                    token_h=token_hash(token), target_ref=str(data.get("target_ref", "")),
                    phase=view.phase)
    return _json(view)


async def _handle_survey(request, repo, params):
    data = await _body(request)
    token = data.get("token")
    tok = await _require_token(repo, token)
    if tok.status == "completed":
        raise ParticipantError("完了済みのトークンです（BR-U2-25）", phase="done")
    answers = data.get("answers", {})
    if not isinstance(answers, dict):
        raise ParticipantError("answers はオブジェクト（BR-U2-20）")
    view = await srv.submit_survey(repo, token, answers, params)
    participant_log("survey", "info", endpoint="/api/survey",
                    token_h=token_hash(token), phase=view.phase, status=view.status)
    return _json(view)
