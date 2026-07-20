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
    PlanActivateRequest,
    PlanIngestRequest,
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

    # POST（U6: 事前生成割当プランの投入 / 有効化）。ルート名で操作を明示。
    if path == "/admin/plan" and method == "POST":
        return await _handle_plan_ingest(request, repo)
    if path == "/admin/plan/activate" and method == "POST":
        return await _handle_plan_activate(request, repo)

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


async def _handle_plan_ingest(request, repo: Repository) -> Response:
    """プラン投入（U6, LC-U6-09）。

    **参照 item の実在をアプリ層で検証する**（`assignment_plan` に FK を張らない設計の
    代替, U6 Infra Q1=A′）。FK を張らない理由は (i) items 参照 FK を 2→4 本に増やすと
    **将来 items を再構築する migration の退避対象が増える** (ii) プラン投入をプール構成
    から独立させる、の 2 点。
    **`likert_targets` も同時に検証**する（プラン item 集合 ⊆ 実在・BR-U6-06 の運搬経路）。
    """
    raw = await request.text()
    try:
        req = PlanIngestRequest.model_validate(json.loads(str(raw)))
    except (ValidationError, json.JSONDecodeError) as e:
        admin_log("plan_ingest_bad_request", "error", endpoint="/admin/plan")
        return _json_str(json.dumps({"ok": False, "error": f"検証エラー: {e}"}), status=400)

    meta = req.meta
    referenced = set()
    for r in req.rows:
        referenced.add(r.item_left)
        referenced.add(r.item_right)
    referenced |= set(meta.likert_targets)

    existing = await repo.existing_item_ids(sorted(referenced))
    missing = sorted(referenced - existing)
    if missing:
        admin_log("plan_ingest_rejected", "error", endpoint="/admin/plan",
                  plan_set=meta.plan_set, missing=len(missing))
        return _json_str(json.dumps({
            "ok": False,
            "error": f"プランが参照する item がプールに不在（{len(missing)} 件）: "
                     f"{', '.join(missing[:10])}",
        }, ensure_ascii=False), status=400)

    await repo.insert_plan(meta.model_dump(), [r.model_dump() for r in req.rows])
    # ★証跡は「内容」に紐づける（DP-U6-07）: plan_set 名だけでは改竄・取り違えを検出できない。
    admin_log("plan_ingest", "info", endpoint="/admin/plan", plan_set=meta.plan_set,
              seed=meta.seed, attempt=meta.attempt, content_hash=meta.content_hash,
              rows=len(req.rows), likert=len(meta.likert_targets))
    return _json_str(json.dumps({"ok": True, "plan_set": meta.plan_set,
                                 "rows": len(req.rows),
                                 "content_hash": meta.content_hash}, ensure_ascii=False))


async def _handle_plan_activate(request, repo: Repository) -> Response:
    """プラン有効化（U6, BR-U6-12 / U6-NFR-19/20）。

    **★収集開始後の切替は拒否する（ハード）**: 有効化しようとするセット、または現在
    有効なセットに **judgment が 1 件でも存在したら 4xx**。切替が必要な事態は**実験の
    作り直し**であり、API で簡便にやれてはいけない操作。
    **DB 制約では表現できない**（`judgments` と `assignment_plan_meta` をまたぐ条件）ため
    **アプリ層の事前検証**で実装する。
    """
    raw = await request.text()
    try:
        req = PlanActivateRequest.model_validate(json.loads(str(raw)))
    except (ValidationError, json.JSONDecodeError) as e:
        admin_log("plan_activate_bad_request", "error", endpoint="/admin/plan/activate")
        return _json_str(json.dumps({"ok": False, "error": f"検証エラー: {e}"}), status=400)

    meta = await repo.get_plan_meta(req.plan_set)
    if meta is None:
        admin_log("plan_activate_rejected", "error", endpoint="/admin/plan/activate",
                  plan_set=req.plan_set, reason="not_found")
        return _json_str(json.dumps({
            "ok": False, "error": f"プランセットが未投入: {req.plan_set}"}, ensure_ascii=False),
            status=400)

    # 収集開始後のガード（現行有効セット・切替先の両方を見る）。
    current = await repo.get_active_plan_set()
    for ps in {x for x in (current, req.plan_set) if x}:
        n = await repo.count_judgments_for_plan_set(ps)
        if n > 0:
            admin_log("plan_activate_rejected", "error", endpoint="/admin/plan/activate",
                      plan_set=req.plan_set, reason="judgments_exist", blocking_set=ps, count=n)
            return _json_str(json.dumps({
                "ok": False,
                "error": f"収集開始後の切替は拒否されました（{ps} に judgment {n} 件）。"
                         "プランセットの切替は実験の作り直しに相当します（BR-U6-12/U6-NFR-20）",
            }, ensure_ascii=False), status=409)

    await repo.activate_plan(req.plan_set)
    admin_log("plan_activate", "info", endpoint="/admin/plan/activate",
              plan_set=req.plan_set, seed=meta["seed"], content_hash=meta["content_hash"])
    return _json_str(json.dumps({"ok": True, "plan_set": req.plan_set,
                                 "content_hash": meta["content_hash"]}, ensure_ascii=False))


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

    # ---- U6（Step 15 / DP-U6-06）: 発行時に (plan_set, plan_index) を「組」で束縛 ----
    # 有効プランが無ければ束縛しない（NULL＝オンライン生成へフォールバック, U6-NFR-14）。
    bindings: list[tuple[str, int]] | None = None
    active = await repo.get_active_plan_set()
    if active is not None:
        meta = await repo.get_plan_meta(active)
        n_slots = int((meta or {}).get("n_slots") or 0)
        if req.plan_index is not None:
            # 補充トークン（BR-U6-15）: 指定スロットに束縛する（脱落者の代替）。
            # 未回答の本番ペアだけが配られ、練習は全量再提示される（session.start_or_resume）。
            if req.plan_index >= n_slots:
                return _json(TokenIssueResult(
                    ok=False,
                    gate_errors=[f"plan_index={req.plan_index} が範囲外（スロット数 {n_slots}）"]))
            bindings = [(active, req.plan_index)] * len(tokens)
        else:
            # 初回発行: スロット 0..count-1 を順に束縛。★スロット数を超える発行は拒否
            #   （J はスロットへの完全分割ゆえ、余分なトークンは束縛先を持てない）。
            if len(tokens) > n_slots:
                return _json(TokenIssueResult(
                    ok=False,
                    gate_errors=[f"count={len(tokens)} が有効プランのスロット数 {n_slots} を超過"
                                 "（補充は --plan-index で対象スロットを指定してください）"]))
            bindings = [(active, i) for i in range(len(tokens))]

    await repo.insert_tokens(tokens, now, bindings)
    admin_log("token_issue", "info", endpoint="/admin/tokens", count=len(tokens),
              plan_set=active or "-",
              plan_index=req.plan_index if req.plan_index is not None else "-")
    return _json(TokenIssueResult(ok=True, tokens=tokens, issued_at=now))
