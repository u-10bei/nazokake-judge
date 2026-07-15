"""U3 管理 API 統合ドライバ（実 D1 / miniflare）。

実 `/admin/*` の GET エンドポイントを叩き、PU3-1/2/4/5 を検証する。
pure-Python（urllib）。プール投入・トークン発行・参加者フローは /admin/* + /it/* で用意。

前提: it_entry.py が `/admin/*`・`/api/*` を本物の on_fetch に委譲し、補助ルート
（/it/reset, /it/seed-token）を提供する。
"""

from __future__ import annotations

import base64
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8788"
AUTH = "Basic " + base64.b64encode(b"admin:secret").decode()
PTOKEN = "ptok-u3-001"


def _req(path, payload=None, auth=False, method="POST", raw=False):
    headers = {"content-type": "application/json"}
    if auth:
        headers["Authorization"] = AUTH
    data = json.dumps(payload).encode() if payload is not None else None
    last = None
    for _ in range(4):
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode()
                return r.status, (body if raw else (json.loads(body) if body else None))
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                last = (e.code, None); time.sleep(1); continue
            return e.code, (e.read().decode() if raw else None)
        except urllib.error.URLError:
            last = (None, None); time.sleep(1); continue
    return last if last else (None, None)


def _get(path, auth=True, raw=False):
    return _req(path, method="GET", auth=auth, raw=raw)


def _realistic_pool():
    layers = [("pro", 30), ("ai", 20), ("edit", 30), ("rule", 15)]
    out, i = [], 0
    for layer, n in layers:
        for _ in range(n):
            out.append({"item_id": f"r{i:03d}", "layer": layer, "body": f"謎かけ {i:03d}"})
            i += 1
    return out


def _drive_participant():
    """1 参加者分のフローを完走させ、本番判定 + 練習判定を蓄積する。"""
    _get(f"/it/seed-token?token={PTOKEN}", auth=False)
    guard = 0
    while guard < 200:
        st, v = _req(f"/api/session?token={PTOKEN}", method="GET")
        if not v or v.get("ok") is False:
            break
        if v["phase"] in ("practice", "judging") and v["next_pair"]:
            _req("/api/judgment", {"token": PTOKEN, "pair_id": v["next_pair"]["pair_id"],
                                    "choice": "A"})
        elif v["phase"] == "likert" and v["next_likert"]:
            _req("/api/likert", {"token": PTOKEN, "target_ref": v["next_likert"]["target_ref"],
                                  "rating": 4})
        elif v["phase"] == "survey":
            _req("/api/survey", {"token": PTOKEN, "answers": {"experience": "some",
                 "proficiency": "3", "age_band": "30s"}})
        else:
            break
        guard += 1


def run():
    results = []

    def check(name, ok, detail):
        results.append({"item": name, "pass": bool(ok), "detail": detail})

    _get("/it/reset", auth=False)
    _req("/admin/items", {"items": _realistic_pool()}, auth=True)
    _drive_participant()

    # PU3-5: 認証（認証なしで各 GET が 401）
    st_p, _ = _req("/admin/progress", method="GET", auth=False)
    st_w, _ = _req("/admin/winrates", method="GET", auth=False)
    st_e, _ = _req("/admin/export?format=json", method="GET", auth=False)
    st_ui, _ = _req("/admin/", method="GET", auth=False)
    check("PU3-5-auth-401", st_p == 401 and st_w == 401 and st_e == 401 and st_ui == 401,
          {"progress": st_p, "winrates": st_w, "export": st_e, "ui": st_ui})

    # PU3-4: 進捗カウント整合（issued>=started>=completed, judgments_total は本番のみ>0）
    st, prog = _get("/admin/progress")
    ok_prog = (prog["tokens_issued"] >= prog["tokens_started"] >= prog["tokens_completed"] >= 1
               and prog["judgments_total"] > 0 and prog["survey_total"] >= 1)
    check("PU3-4-progress", ok_prog, prog)

    # エクスポート（JSON bundle）を取得
    st, bundle = _get("/admin/export?format=json")
    n_export_judg = len(bundle["judgments"])

    # PU3-1: 練習除外の出力段保証（export judgments 数 == 本番判定数 == progress.judgments_total）
    check("PU3-1-practice-excluded",
          n_export_judg == prog["judgments_total"] and n_export_judg > 0,
          {"export_judgments": n_export_judg, "progress_judgments": prog["judgments_total"]})

    # PU3-3(実データ): ExportBundle 自己完結（judgments の item ⊆ items）
    item_ids = {it["item_id"] for it in bundle["items"]}
    selfcontained = all(j["item_left"] in item_ids and j["item_right"] in item_ids
                        for j in bundle["judgments"])
    has_no_body = all("body" not in it for it in bundle["items"])
    check("PU3-3-selfcontained-nobody", selfcontained and has_no_body,
          {"items": len(item_ids), "selfcontained": selfcontained, "no_body": has_no_body})

    # PU3-2: winrate 定義整合（各行 winrate == wins/matches、matches=0→0）
    st, winrates = _get("/admin/winrates")
    ok_wr = True
    for r in winrates:
        m, w = r["matches"], r["wins"]
        expect = (w / m) if m > 0 else 0.0
        if abs(r["winrate"] - expect) > 1e-9 or w > m:
            ok_wr = False; break
    # 総試合数 = 本番判定数 × 2（各判定で 2 項目が 1 試合ずつ）
    total_matches = sum(r["matches"] for r in winrates)
    check("PU3-2-winrate-definition",
          ok_wr and total_matches == prog["judgments_total"] * 2,
          {"rows": len(winrates), "total_matches": total_matches,
           "expected": prog["judgments_total"] * 2})

    # エクスポート CSV（judgments）: attachment ヘッダ + 行数整合
    st, csv_text = _get("/admin/export?format=csv&entity=judgments", raw=True)
    csv_lines = [l for l in csv_text.splitlines() if l.strip()]
    check("PU3-csv-judgments", st == 200 and len(csv_lines) == n_export_judg + 1,
          {"status": st, "lines": len(csv_lines), "expected": n_export_judg + 1})

    # CSV entity 未指定 → 400
    st, _ = _get("/admin/export?format=csv")
    check("PU3-csv-entity-required", st == 400, {"status": st})

    # 管理 UI（/admin/）は 200 + HTML
    st, html = _get("/admin/", raw=True)
    check("PU3-ui-html", st == 200 and "研究者管理" in html and "winrate-table" in html,
          {"status": st})

    return {"overall_pass": all(x["pass"] for x in results), "results": results}


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out["overall_pass"] else 1)
