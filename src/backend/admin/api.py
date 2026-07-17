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
    ItemRetireRequest,
    RejectedItem,
    TokenIssueRequest,
    TokenIssueResult,
    generate_token,
    validate_item,
)


def _json(model, status: int = 200) -> Response:
    return Response(model.model_dump_json(), status=status,
                    headers={"content-type": "application/json"})


def _json_str(body: str, status: int = 200) -> Response:
    """no-store 付き JSON 応答（U3 管理 API・DP-U3-02）。"""
    return Response(body, status=status,
                    headers={"content-type": "application/json", "cache-control": "no-store"})


def _download(body: str, content_type: str, filename: str) -> Response:
    """エクスポートのダウンロード応答（no-store + attachment, DP-U3-02/05）。"""
    return Response(body, status=200, headers={
        "content-type": content_type,
        "cache-control": "no-store",
        "content-disposition": f'attachment; filename="{filename}"',
    })


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def handle_admin(request, env, path: str) -> Response:
    """`/admin/*` の単一チョークポイント（認証 → ディスパッチ）。"""
    if not check_basic(request, env):  # DP-U4a-01（GET/POST 共通の単一認証点）
        admin_log("admin_auth_failed", "error", endpoint=path)
        return unauthorized()

    repo = Repository(env.DB)
    method = str(request.method)

    # POST（U4a: pool_ingest / token_issue）
    if path == "/admin/items" and method == "POST":
        return await _handle_items(request, repo)
    if path == "/admin/tokens" and method == "POST":
        return await _handle_tokens(request, repo)

    # POST（U5: 出題停止 / 復活）。ルート名で操作を明示（ブール引数で意味を変えない,
    # TSD-U5-04）＝admin_log のイベントと 1:1 対応。凍結ガード（BR-U4a-03）は
    # `_handle_items` 側にあり、こちらは別経路ゆえ参照済み item でも廃止できる（BR-U5-05）。
    if path == "/admin/items/retire" and method == "POST":
        return await _handle_retire(request, repo, retire=True)
    if path == "/admin/items/unretire" and method == "POST":
        return await _handle_retire(request, repo, retire=False)

    # GET（U3: 管理 UI / 進捗 / 暫定勝率 / エクスポート）
    if method == "GET":
        if path == "/admin/" or path == "/admin":
            from backend.admin.ui import ADMIN_HTML
            return Response(ADMIN_HTML, headers={
                "content-type": "text/html; charset=utf-8", "cache-control": "no-store"})
        if path == "/admin/progress":
            return await _handle_progress(repo)
        if path == "/admin/winrates":
            return await _handle_winrates(repo)
        if path == "/admin/export":
            return await _handle_export(request, repo)

    return Response(json.dumps({"error": "not found"}), status=404,
                    headers={"content-type": "application/json"})


# ------------------------------------------------------------ U3 GET ハンドラ

async def _handle_progress(repo) -> Response:
    from backend.admin import service
    view = await service.get_progress(repo)
    admin_log("admin_progress", "info", endpoint="/admin/progress")
    return _json_str(view.model_dump_json())


async def _handle_winrates(repo) -> Response:
    from backend.admin import service
    rows = await service.get_winrates(repo)
    admin_log("admin_winrates", "info", endpoint="/admin/winrates", count=len(rows))
    body = "[" + ",".join(r.model_dump_json() for r in rows) + "]"
    return _json_str(body)


async def _handle_export(request, repo) -> Response:
    from urllib.parse import parse_qs, urlparse

    from backend.admin import service
    qs = parse_qs(urlparse(request.url).query)
    fmt_kind = (qs.get("format", ["json"]) or ["json"])[0]
    entity = (qs.get("entity", [None]) or [None])[0]
    exported_at = _now_iso()
    try:
        body, content_type, filename = await service.export(
            repo, fmt_kind, entity, exported_at)
    except service.ExportRequestError as e:
        admin_log("admin_export_bad_request", "error", endpoint="/admin/export")
        return _json_str(json.dumps({"ok": False, "error": str(e)}), status=400)
    admin_log("admin_export", "info", endpoint="/admin/export",
              result=f"{fmt_kind}:{entity or 'bundle'}")
    return _download(body, content_type, filename)


async def _handle_retire(request, repo: Repository, *, retire: bool) -> Response:
    """出題停止 / 復活（U5, BR-U5-06/07 / LC-U5-04）。

    冪等（既に目的の状態なら no-op・retire では初回の `retired_at` を保持）。`not_found` は
    エラーにせず部分成功として報告する（U5-NFR-11）。`admin_log` が**廃止履歴の正**
    （`retired_at` は現在状態のみ, BR-U5-13）。**本文（body）は出さない**（秘匿方針）。
    """
    event = "item_retire" if retire else "item_unretire"
    endpoint = "/admin/items/retire" if retire else "/admin/items/unretire"
    raw = await request.text()
    try:
        req = ItemRetireRequest.model_validate(json.loads(str(raw)))
    except (ValidationError, json.JSONDecodeError):
        admin_log(f"{event}_bad_request", "error", endpoint=endpoint)
        return _json_str(json.dumps(
            {"ok": False, "error": "item_ids（1 件以上）が必要です"}), status=400)

    result = (await repo.retire_items(req.item_ids, _now_iso())) if retire \
        else (await repo.unretire_items(req.item_ids))

    admin_log(event, "info", endpoint=endpoint,
              item_ids=result_item_ids(req.item_ids), count=result.retired,
              already=len(result.already_retired), not_found=len(result.not_found))
    return _json(result)


def result_item_ids(item_ids: list[str]) -> str:
    """監査ログ用に item_id を列挙する（本文は含めない, U5-NFR-09）。"""
    return ",".join(item_ids)


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
    # U5: 母数は **現役のみ**（BR-U5-09）。出題できない作品を数に入れると「発行はできるが
    # 割当が偏る/失敗する」状態を作る。入力は新規＝常に active ゆえ active ∪ 入力になる。
    params = AssignmentParams()
    suff = pool_sufficiency(await repo.list_active_items(), params)

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
    # U5: 母数は **現役のみ**（BR-U5-09）。廃止の結果ゲートを割ったら発行拒否が正しい挙動
    # ＝運用者に補充を促す。
    params = AssignmentParams()
    suff = pool_sufficiency(await repo.list_active_items(), params)
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
