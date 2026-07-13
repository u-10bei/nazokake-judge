"""U4a 管理 API 統合ドライバ（実 D1 / miniflare）。

実 `/admin/*` エンドポイントを HTTP で叩き、PU4a-1/2/3a/3b/4/6 を検証する。
pure-Python（urllib）。`GET /run` ではなくクライアント側で全シナリオを実行し JSON 出力。
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


def _req(path, payload=None, auth=True, method="POST"):
    headers = {"content-type": "application/json"}
    if auth:
        headers["Authorization"] = AUTH
    data = json.dumps(payload).encode() if payload is not None else None
    # miniflare ローカルのコールドスタート由来の一過性エラーに対し軽くリトライ
    # （401 等の HTTPError はそのまま返す。5xx / 接続エラーのみ再試行）。
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
        except urllib.error.URLError as e:
            last = (None, None); time.sleep(1); continue
    return last if last else (None, None)


def _item(iid, layer, body="本文"):
    return {"item_id": iid, "layer": layer, "body": body}


def _realistic():
    layers = [("pro", 30), ("ai", 20), ("edit", 30), ("rule", 15)]
    out, i = [], 0
    for layer, n in layers:
        for _ in range(n):
            out.append(_item(f"r{i:03d}", layer)); i += 1
    return out


def run():
    results = []

    def check(name, ok, detail):
        results.append({"item": name, "pass": bool(ok), "detail": detail})

    _req("/it/reset", method="GET", auth=False)

    # PU4a-6: 認証なし → 401
    st, _ = _req("/admin/items", {"items": []}, auth=False)
    check("PU4a-6-auth-401", st == 401, {"status": st})

    # PU4a-3a: 段階投入（不足プールでも投入成功 + warning）
    small = [_item("s0", "pro"), _item("s1", "ai"), _item("s2", "edit"), _item("s3", "rule")]
    st, r = _req("/admin/items", {"items": small})
    check("PU4a-3a-staged-ingest-warns", st == 200 and r["ok"] and r["inserted"] == 4
          and len(r["sufficiency_warnings"]) > 0, r)

    # PU4a-1: 冪等（同一再投入 → inserted=0, updated=4）
    st, r = _req("/admin/items", {"items": small})
    check("PU4a-1-idempotent", r["ok"] and r["inserted"] == 0 and r["updated"] == 4, r)

    # PU4a-3b: 発行時ゲート（不足プール → 発行拒否）
    st, r = _req("/admin/tokens", {"count": 3})
    check("PU4a-3b-issue-gate-blocks", r["ok"] is False and len(r["gate_errors"]) > 0, r)

    # 充足プールへ（マージ後 sufficient）
    st, r = _req("/admin/items", {"items": _realistic()})
    check("ingest-realistic-sufficient", r["ok"] and len(r["sufficiency_warnings"]) == 0, r)

    # PU4a-4: トークン発行（充足 → 一意な count 個）
    st, r = _req("/admin/tokens", {"count": 5})
    toks = r.get("tokens", [])
    check("PU4a-4-token-issue", r["ok"] and len(toks) == 5 and len(set(toks)) == 5, r)

    # PU4a-2: 凍結ガード（参照済み item への更新は拒否・全体中断・DB 不変）
    _req("/it/seed-frozen", method="GET", auth=False)
    st, r = _req("/admin/items", {"items": [_item("frozen001", "pro", "CHANGED")]})
    rejected_ids = [x["item_id"] for x in r.get("rejected", [])]
    check("PU4a-2-freeze-guard", r["ok"] is False and "frozen001" in rejected_ids, r)

    return {"overall_pass": all(x["pass"] for x in results), "results": results}


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out["overall_pass"] else 1)
