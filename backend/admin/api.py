"""AdminApi — 管理エンドポイント（LC-U4a-01, DP-U4a-05/06/07）。

`/admin/items`（pool_ingest）・`/admin/tokens`（token_issue）。統一エラー封筒:
業務エラーは 200 + ok=false + 内訳、認証失敗のみ 401（AuthGuard）。
"""

from __future__ import annotations

import json
import time

from pydantic import ValidationError
from workers import Response

from backend.admin.auth import check_basic, unauthorized
from backend.admin.log import admin_log
from backend.domain import pool_sufficiency
from backend.repo import Repository
from schema import (
    AssignmentParams,
    IngestResult,
    RejectedItem,
    TokenIssueRequest,
    TokenIssueResult,
    generate_token,
    validate_item,
)


def _json(model, status: int = 200) -> Response:
    return Response(model.model_dump_json(), status=status,
                    headers={"content-type": "application/json"})


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def handle_admin(request, env, path: str) -> Response:
    """`/admin/*` の単一チョークポイント（認証 → ディスパッチ）。"""
    if not check_basic(request, env):  # DP-U4a-01
        admin_log("admin_auth_failed", "error", endpoint=path)
        return unauthorized()

    repo = Repository(env.DB)
    method = str(request.method)
    if path == "/admin/items" and method == "POST":
        return await _handle_items(request, repo)
    if path == "/admin/tokens" and method == "POST":
        return await _handle_tokens(request, repo)
    return Response(json.dumps({"error": "not found"}), status=404,
                    headers={"content-type": "application/json"})


async def _handle_items(request, repo: Repository) -> Response:
    raw = await request.text()
    payload = json.loads(str(raw))

    # 各 record を個別に検証（層ラベル/本文必須 BR-U4a-01/02。不正 item のみ拒否）。
    valid = []
    rejected: list[RejectedItem] = []
    for entry in payload.get("items", []):
        try:
            valid.append(validate_item(entry))
        except ValidationError:
            rejected.append(RejectedItem(
                item_id=str(entry.get("item_id", "?")),
                reason="検証エラー: 層ラベル/本文必須（BR-U4a-01/02）",
            ))

    # 凍結ガード + 原子投入（BR-U4a-03/09）。
    ins = (await repo.insert_items(valid)) if valid else {"inserted": 0, "updated": 0, "rejected": []}
    rejected = rejected + list(ins["rejected"])

    # 投入後、マージ後プールで充足判定（warn のみ, BR-U4a-05）。
    params = AssignmentParams()
    suff = pool_sufficiency(await repo.list_items(), params)

    ok = not rejected
    result = IngestResult(
        ok=ok, inserted=ins["inserted"], updated=ins["updated"],
        rejected=rejected, sufficiency_warnings=suff.shortfalls,
    )
    admin_log("pool_ingest", "info" if ok else "error", endpoint="/admin/items",
              inserted=ins["inserted"], updated=ins["updated"], rejected_count=len(rejected))
    if suff.shortfalls:
        admin_log("pool_sufficiency_warning", "warning", endpoint="/admin/items", result="under")
    return _json(result)


async def _handle_tokens(request, repo: Repository) -> Response:
    raw = await request.text()
    try:
        req = TokenIssueRequest.model_validate_json(str(raw))
    except ValidationError:
        return _json(TokenIssueResult(ok=False, gate_errors=["count は 1 以上の整数が必要"]))

    # 発行時充足ゲート（真のゲート, BR-U4a-12）。
    params = AssignmentParams()
    suff = pool_sufficiency(await repo.list_items(), params)
    if not suff.ok:
        admin_log("token_issue_blocked", "error", endpoint="/admin/tokens", result="pool_insufficient")
        return _json(TokenIssueResult(ok=False, gate_errors=suff.shortfalls))

    # 衝突事前排除 → 生成（BR-U4a-06）。
    existing = await repo.all_token_strings()
    tokens: list[str] = []
    guard = 0
    limit = req.count * 20 + 100
    while len(tokens) < req.count and guard < limit:
        candidate = generate_token()
        if candidate not in existing and candidate not in tokens:
            tokens.append(candidate)
        guard += 1

    now = _now_iso()
    await repo.insert_tokens(tokens, now)
    admin_log("token_issue", "info", endpoint="/admin/tokens", count=len(tokens))
    return _json(TokenIssueResult(ok=True, tokens=tokens, issued_at=now))
