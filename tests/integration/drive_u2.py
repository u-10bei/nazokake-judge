"""U2 参加者フロー統合ドライバ（実 D1 / miniflare）。

実 `/api/*` エンドポイントを HTTP で叩き、参加者フロー一巡と PU2-2/4/5/7/8 を検証する。
pure-Python（urllib）。プール投入・トークン発行は /admin/* + /it/* を利用。

前提: it_entry.py が `/api/*` を本物の on_fetch に委譲し、補助ルート
（/it/reset, /it/seed-token, /it/likert-rating, /it/exposure）を提供する。
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
PTOKEN = "ptok-u2-001"


def _req(path, payload=None, auth=False, method="POST"):
    headers = {"content-type": "application/json"}
    if auth:
        headers["Authorization"] = AUTH
    data = json.dumps(payload).encode() if payload is not None else None
    last = None
    for _ in range(4):
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                last = (e.code, None); time.sleep(1); continue
            return e.code, None
        except urllib.error.URLError:
            last = (None, None); time.sleep(1); continue
    return last if last else (None, None)


def _get(path):
    return _req(path, method="GET")


def _realistic_pool():
    layers = [("pro", 30), ("ai", 20), ("edit", 30), ("rule", 15)]
    out, i = [], 0
    for layer, n in layers:
        for _ in range(n):
            out.append({"item_id": f"r{i:03d}", "layer": layer, "body": f"謎かけ本文 {i:03d}"})
            i += 1
    return out


def run():
    results = []

    def check(name, ok, detail):
        results.append({"item": name, "pass": bool(ok), "detail": detail})

    _get("/it/reset")
    _req("/admin/items", {"items": _realistic_pool()}, auth=True)
    _get(f"/it/seed-token?token={PTOKEN}")

    # セッション開始（unused → in_progress, practice）。出自秘匿の確認も。
    st, view = _get(f"/api/session?token={PTOKEN}")
    ok_start = st == 200 and view["status"] == "in_progress" and view["next_pair"] is not None
    np = view["next_pair"]
    leaked = np is not None and ("layer" in np.get("left", {}) or "body_ref" in np.get("left", {}))
    check("PU2-start-session", ok_start and not leaked,
          {"status": view.get("status"), "phase": view.get("phase"), "leaked": leaked})

    # PU2-4: 判定冪等（同一 pair を 2 回 → 2 回目 duplicate=true, choice 不変）。
    pid = np["pair_id"]
    st, r1 = _req("/api/judgment", {"token": PTOKEN, "pair_id": pid, "choice": "A"})
    st, r2 = _req("/api/judgment", {"token": PTOKEN, "pair_id": pid, "choice": "B"})
    check("PU2-4-judgment-idempotent",
          r1["saved"] and (r1["duplicate"] is False)
          and (r2["duplicate"] is True) and r2["choice"] == "A",
          {"r1": r1["choice"], "r2": r2["choice"], "dup2": r2["duplicate"]})

    # PU2-2: 再開の非重複（GET session の next_pair は回答済み pid と異なる）。
    st, view2 = _get(f"/api/session?token={PTOKEN}")
    next2 = view2["next_pair"]
    check("PU2-2-resume-no-dup", next2 is not None and next2["pair_id"] != pid,
          {"answered": pid, "next": next2 and next2["pair_id"]})

    # 判定フェーズを最後まで進める（practice + judging）。
    guard = 0
    while guard < 200:
        st, v = _get(f"/api/session?token={PTOKEN}")
        if v.get("ok") is False:
            break
        if v["phase"] in ("practice", "judging") and v["next_pair"]:
            _req("/api/judgment", {"token": PTOKEN, "pair_id": v["next_pair"]["pair_id"],
                                    "choice": "A"})
            guard += 1
        else:
            break
    st, vlik = _get(f"/api/session?token={PTOKEN}")
    check("PU2-reach-likert", vlik["phase"] == "likert" and vlik["next_likert"] is not None,
          {"phase": vlik.get("phase")})

    # PU2-8: 完了順序（likert 未完で survey 送信 → completed にならない）。
    _req("/api/survey", {"token": PTOKEN, "answers": {"experience": "some",
         "proficiency": "3", "age_band": "30s"}})
    st, vmid = _get(f"/api/session?token={PTOKEN}")
    check("PU2-8-completion-ordering", vmid["status"] == "in_progress" and vmid["phase"] != "done",
          {"status": vmid.get("status"), "phase": vmid.get("phase")})

    # PU2-7: Likert 初回不変（同一 target に 3→7 → 保存は 3）。
    ref = vlik["next_likert"]["target_ref"]
    _req("/api/likert", {"token": PTOKEN, "target_ref": ref, "rating": 3})
    _req("/api/likert", {"token": PTOKEN, "target_ref": ref, "rating": 7})
    st, lr = _get(f"/it/likert-rating?token={PTOKEN}&ref={ref}")
    check("PU2-7-likert-initial-value", lr["rating"] == 3, {"stored": lr.get("rating")})

    # Likert を最後まで。
    guard = 0
    while guard < 50:
        st, v = _get(f"/api/session?token={PTOKEN}")
        if v["phase"] == "likert" and v["next_likert"]:
            _req("/api/likert", {"token": PTOKEN, "target_ref": v["next_likert"]["target_ref"],
                                  "rating": 4})
            guard += 1
        else:
            break

    # 完了（survey 再送 → 全揃いで completed）。
    _req("/api/survey", {"token": PTOKEN, "answers": {"experience": "some",
         "proficiency": "3", "age_band": "30s"}})
    st, vend = _get(f"/api/session?token={PTOKEN}")
    check("PU2-complete", vend["status"] == "completed" and vend["phase"] == "done",
          {"status": vend.get("status"), "phase": vend.get("phase")})

    # PU2-5: 練習の集計除外（露出総数 == 本番判定に用いた項目の露出 = 本番ペア数×2）。
    #   完了セッションの導出露出は practice を除外する（is_practice サーバ判定）。
    st, exp = _get("/it/exposure")
    # 本番ペア数は完了 view の progress.total。露出総数 = production_total * 2（各ペア 2 項目）。
    prod_total = vend["progress"]["total"]
    check("PU2-5-practice-excluded",
          exp["total_exposure"] == prod_total * 2,
          {"total_exposure": exp["total_exposure"], "expected": prod_total * 2})

    # 完了後の再アクセスは completed（US-P01/P07 整合）。
    st, again = _get(f"/api/session?token={PTOKEN}")
    check("PU2-reaccess-completed", again["status"] == "completed", {"status": again.get("status")})

    return {"overall_pass": all(x["pass"] for x in results), "results": results}


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out["overall_pass"] else 1)
