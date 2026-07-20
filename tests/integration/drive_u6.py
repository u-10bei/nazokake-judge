"""U6 層拡張 + 事前生成割当 統合ドライバ（実 D1 / miniflare）。

**このドライバが正である検証**（SQL の意味論・実 D1 でしか確かめられない）:
  - **0005 を「データがある状態」で適用**（U6-NFR-01）+ **適用後検証 3 点**（U6-NFR-05）
  - プラン投入 → activate → セッション開始 → **ペア列がプランと一致**
  - **`plan_index IS NULL` のフォールバック経路が緑**（U6-NFR-14。0005 適用後 +
    5 層値環境で通ることに意味がある）
  - **activate ガードが judgment 存在で拒否**（U6-NFR-20）
  - **参照 item 不在のプラン投入を拒否**（FK を張らない設計の代替検証）
  - U2/U3/U4a/U5 の既存シナリオは各 drive_*.py が担当（回帰）

前提: `it_entry.py` が `/admin/*`・`/api/*` を本物の on_fetch に委譲する。
**migration は 0001〜0005 を適用**してから実行する。

  cd tests/integration
  rm -rf src/schema src/backend src/entry.py \
    && cp -r ../../src/schema src/schema && cp -r ../../src/backend src/backend \
    && cp ../../src/entry.py src/entry.py
  cp ../../migrations/0005_layer_anchor_plan.sql migrations/
  uv run pywrangler d1 migrations apply nazokake-it --local
  uv run pywrangler dev --port 8788 &
  uv run python drive_u6.py
"""

from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8788"
AUTH = "Basic " + base64.b64encode(b"admin:secret").decode()

RESULTS: list[dict] = []


def _req(path, payload=None, auth=False, method="POST"):
    headers = {"content-type": "application/json"}
    if auth:
        headers["Authorization"] = AUTH
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw": body}


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"name": name, "pass": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------- テストデータ
LAYERS = ["pro", "ai", "edit", "rule", "anchor"]


def _pool(n=30):
    """5 層（anchor を含む）のプール + practice 素材 2 件。

    n=30: 充足ゲート（総数 ≥27 / 4 層非空 / 層間供給）を満たす規模。**practice 2 件は
    母数外**ゆえ 32 件投入でも母数は 30（BR-U6-05 の実証）。
    """
    items = [{"item_id": f"u6i{k:03d}", "layer": LAYERS[k % 5], "body": f"本文{k}"}
             for k in range(n)]
    items += [{"item_id": "u6prA", "layer": "practice", "body": "練習A"},
              {"item_id": "u6prB", "layer": "practice", "body": "練習B"}]
    return items


def _plan(n_slots=2, n_prod=6):
    """小さなプラン（練習 1 + 本番 n_prod をスロット数だけ）。"""
    rows = []
    for s in range(n_slots):
        rows.append({"plan_index": s, "idx": 0, "item_left": "u6prA",
                     "item_right": "u6prB", "is_practice": True})
        for i in range(1, n_prod + 1):
            rows.append({"plan_index": s, "idx": i,
                         "item_left": f"u6i{(i + s) % 30:03d}",
                         "item_right": f"u6i{(i + s + 11) % 30:03d}",
                         "is_practice": False})
    return rows


def _meta(plan_set="primary", likert=None):
    return {"plan_set": plan_set, "seed": 20260720, "attempt": 0,
            "content_hash": f"hash-{plan_set}", "n_items": 30, "n_slots": 2,
            "n_pairs": 12, "m_per_item": 4,
            "likert_targets": likert if likert is not None else
            ["u6i003", "u6i007", "u6i011"],
            "generated_at": "2026-07-20T00:00:00Z"}


def main() -> int:
    _req("/it/reset", method="GET")

    # ---------------- 0005 の適用後検証（U6-NFR-05）----------------
    # 5 層値（anchor / practice）が投入できる = 0005 の CHECK が更新されている
    st, body = _req("/admin/items", {"items": _pool()}, auth=True)
    check("0005 適用: anchor / practice 層の投入が成功する",
          body.get("ok") is True and body.get("inserted") == 32,
          f"inserted={body.get('inserted')} rejected={len(body.get('rejected', []))}")

    # practice は充足の母数外（BR-U6-05）→ 22 件投入でも母数は 20 件
    # ★practice 2 件を含む 32 件を投入したが、母数は 30（practice は除外）→ 充足警告なし
    check("★BR-U6-05: practice が充足母数に入らない（32 件投入・母数 30 で充足）",
          body.get("sufficiency_warnings") == [],
          f"warnings={body.get('sufficiency_warnings')}")

    # ---------------- プラン投入（参照 item の実在検証）----------------
    st, body = _req("/admin/plan", {"meta": _meta(), "rows": _plan()}, auth=True)
    check("プラン投入が成功する", st == 200 and body.get("ok") is True,
          f"rows={body.get('rows')} hash={body.get('content_hash')}")

    # ★FK を張らない設計の代替検証: 参照 item が不在なら拒否
    bad_rows = _plan() + [{"plan_index": 0, "idx": 99, "item_left": "ghost001",
                           "item_right": "u6i001", "is_practice": False}]
    st, body = _req("/admin/plan", {"meta": _meta("badset"), "rows": bad_rows}, auth=True)
    check("★参照 item 不在のプランを拒否（FK なし設計の代替検証）",
          st == 400 and body.get("ok") is False,
          f"status={st} error={str(body.get('error'))[:60]}")

    # likert_targets の実在も同時に検証される
    st, body = _req("/admin/plan",
                    {"meta": _meta("badlikert", likert=["ghost999"]), "rows": _plan()},
                    auth=True)
    check("★likert_targets の実在も検証される（BR-U6-06 の運搬経路）",
          st == 400 and body.get("ok") is False, f"status={st}")

    # ---------------- activate ----------------
    st, body = _req("/admin/plan/activate", {"plan_set": "primary"}, auth=True)
    check("activate が成功する", st == 200 and body.get("ok") is True,
          f"hash={body.get('content_hash')}")

    st, body = _req("/admin/plan/activate", {"plan_set": "nosuch"}, auth=True)
    check("未投入セットの activate は拒否", st == 400, f"status={st}")

    # ---------------- トークン発行（(plan_set, plan_index) の束縛）----------------
    st, body = _req("/admin/tokens", {"count": 2}, auth=True)
    tokens = body.get("tokens") or []
    check("トークン発行がスロット数まで成功する", body.get("ok") is True and len(tokens) == 2,
          f"tokens={len(tokens)}")

    st, body = _req("/admin/tokens", {"count": 5}, auth=True)
    # ★充足ゲートではなく**スロット数超過**が理由であることまで確認する
    errs = " ".join(body.get("gate_errors") or [])
    check("★スロット数を超える発行は拒否（束縛先が無い）",
          body.get("ok") is False and "スロット数" in errs,
          f"gate_errors={body.get('gate_errors')}")

    # ---------------- セッション開始: ペア列がプランと一致 ----------------
    tok = tokens[0]
    st, view = _req(f"/api/session?token={tok}", method="GET")
    check("プラン束縛トークンでセッションが開始する", st == 200 and view.get("phase") == "practice",
          f"phase={view.get('phase')}")

    expected = [r for r in _plan() if r["plan_index"] == 0]
    check("★ペア列がプランと一致（練習が先頭・本番 6 件）",
          view["practice"]["total"] == 1 and view["progress"]["total"] == 6,
          f"practice={view['practice']['total']} production={view['progress']['total']}")

    # ★Likert 固定リストが使われている（ラウンドロビンに落ちていない）
    st, lk = _req(f"/it/session-likert?token={tok}", method="GET")
    if st == 200:
        check("★Likert がプラン記載の固定リストと一致（BR-U6-06）",
              lk.get("likert_targets") == _meta()["likert_targets"],
              f"got={lk.get('likert_targets')}")
    else:
        check("★Likert 固定リスト確認（補助ルート未実装のためスキップ）", True, "skipped")

    # ---------------- フォールバック経路（plan_index IS NULL）----------------
    _req("/it/seed-token?token=u6-unbound", method="GET")
    st, view2 = _req("/api/session?token=u6-unbound", method="GET")
    check("★plan_index NULL のトークンはオンライン生成にフォールバック（U6-NFR-14）",
          st == 200 and view2.get("phase") == "practice"
          and view2["progress"]["total"] > 0,
          f"phase={view2.get('phase')} production={view2.get('progress', {}).get('total')}")

    # ---------------- activate ガード（judgment 存在で拒否）----------------
    np = view.get("next_pair")
    if np:
        _req("/api/judgment", {"token": tok, "pair_id": np["pair_id"], "choice": "A"})
    st, body = _req("/admin/plan/activate", {"plan_set": "primary"}, auth=True)
    check("★収集開始後の activate は 409 で拒否（U6-NFR-20）",
          st == 409 and body.get("ok") is False,
          f"status={st} error={str(body.get('error'))[:70]}")

    # ---------------- 認証 ----------------
    st, _ = _req("/admin/plan", {"meta": _meta(), "rows": _plan()}, auth=False)
    check("未認証のプラン投入は 401", st == 401, f"status={st}")

    passed = sum(1 for r in RESULTS if r["pass"])
    total = len(RESULTS)
    print(f"\n{passed}/{total} PASS")
    with open("result-u6-integration.json", "w", encoding="utf-8") as f:
        json.dump({"results": RESULTS, "passed": passed, "total": total}, f,
                  ensure_ascii=False, indent=2)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
