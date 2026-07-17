"""U5 出題停止 統合ドライバ（実 D1 / miniflare）。

**このドライバが正である検証**（SQL の意味論ゆえ unit/PBT では検証できない）:
  - **PU5-3（冪等）**: retire/unretire を複数回適用しても状態が同一・**再廃止で初回の
    `retired_at` が保持**される（`AND retired_at IS NULL` が保証する, BR-U5-06）。
  - **PU5-4（export は縮まない）**: 廃止の前後で **export の `items` 集合が不変**・
    **judgments の item ⊆ items**（自己完結性 BR-U3-07）が保たれる。
    → **`list_items()` に active フィルタを足す劣化実装をしたら落ちる**（BR-U5-02 の検出網）。
  - **凍結ガード非適用（BR-U5-05）**: **参照済み**（pairs から参照）item でも廃止できる。
  - **再投入で `retired_at` 不変**（BR-U5-08）。
  - **充足割れで発行拒否**（BR-U5-09）。

前提: `it_entry.py` が `/admin/*` を本物の on_fetch に委譲し、補助ルート（/it/reset,
/it/seed-frozen）を提供する。**migration は 0001〜0004 を適用**してから実行する。

  cd tests/integration
  rm -rf src/schema src/backend src/entry.py \
    && cp -r ../../src/schema src/schema && cp -r ../../src/backend src/backend \
    && cp ../../src/entry.py src/entry.py
  uv run pywrangler d1 migrations apply nazokake-it --local
  uv run pywrangler dev --port 8788 &
  uv run python drive_u5.py
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


def _export_item_ids() -> set[str]:
    _, body = _req("/admin/export?format=json", auth=True, method="GET")
    return {i["item_id"] for i in body["items"]}


def _export_bundle() -> dict:
    _, body = _req("/admin/export?format=json", auth=True, method="GET")
    return body


def main() -> int:
    _req("/it/reset", method="GET")
    # frozen001（pairs から参照済み＝凍結対象）+ other001 を用意。
    _req("/it/seed-frozen", method="GET")

    # ---------------- 凍結ガード非適用（BR-U5-05）----------------
    # 参照済み item の body 更新は拒否される（BR-U4a-03 は無改修）。
    st, body = _req("/admin/items", {"items": [
        {"item_id": "frozen001", "layer": "pro", "body": "REWRITTEN"}]}, auth=True)
    check("凍結ガード維持: 参照済み item の body 更新は拒否",
          body.get("ok") is False and len(body.get("rejected", [])) == 1,
          f"rejected={body.get('rejected')}")

    # 一方で **廃止は成功する**（retired_at は body/layer を変えないため）。
    st, body = _req("/admin/items/retire", {"item_ids": ["frozen001"]}, auth=True)
    check("BR-U5-05: 参照済み item でも廃止できる（凍結ガード対象外）",
          st == 200 and body.get("retired") == 1, f"body={body}")

    # ---------------- PU5-4: export は縮まない（★BR-U5-02 の検出網）----------------
    ids_after = _export_item_ids()
    check("PU5-4: 廃止後も export の items に廃止 item が残る（自己完結性 BR-U3-07）",
          "frozen001" in ids_after, f"items={sorted(ids_after)}")

    bundle = _export_bundle()
    item_ids = {i["item_id"] for i in bundle["items"]}
    ref_ids = set()
    for j in bundle["judgments"]:
        ref_ids.add(j["item_left"])
        ref_ids.add(j["item_right"])
    check("PU5-4: judgments の item ⊆ items（自己完結性が保たれる）",
          ref_ids <= item_ids, f"未包含={sorted(ref_ids - item_ids)}")

    check("PU5-4: export の items に retired_at が現れない（形式凍結 U5-NFR-04）",
          all(set(i.keys()) == {"item_id", "layer"} for i in bundle["items"]),
          f"keys={[sorted(i.keys()) for i in bundle['items'][:2]]}")
    check("PU5-4: EXPORT_FORMAT_VERSION 据え置き（1.0.0）",
          bundle.get("schema_version") == "1.0.0", f"version={bundle.get('schema_version')}")

    # ---------------- PU5-3: 冪等（初回 retired_at 保持）----------------
    st, body2 = _req("/admin/items/retire", {"item_ids": ["frozen001"]}, auth=True)
    check("PU5-3: 再廃止は no-op（already_retired に分類・retired=0）",
          body2.get("retired") == 0 and body2.get("already_retired") == ["frozen001"],
          f"body={body2}")

    # ---------------- not_found（部分成功・エラーにしない, U5-NFR-11）----------------
    st, body3 = _req("/admin/items/retire",
                     {"item_ids": ["frozen001", "ghost999"]}, auth=True)
    check("U5-NFR-11: 存在しない item_id は not_found に分類（エラーにしない）",
          st == 200 and body3.get("not_found") == ["ghost999"], f"body={body3}")

    # ---------------- BR-U5-08: 再投入しても retired_at は不変 ----------------
    # other001（未参照）を廃止 → 再投入 → 廃止のまま。
    _req("/admin/items/retire", {"item_ids": ["other001"]}, auth=True)
    _req("/admin/items", {"items": [
        {"item_id": "other001", "layer": "ai", "body": "updated-body"}]}, auth=True)
    st, body4 = _req("/admin/items/retire", {"item_ids": ["other001"]}, auth=True)
    check("BR-U5-08: pool_ingest 再投入で retired_at は不変（廃止のまま）",
          body4.get("retired") == 0 and body4.get("already_retired") == ["other001"],
          f"body={body4}")

    # ---------------- BR-U5-07: 復活 ----------------
    st, body5 = _req("/admin/items/unretire", {"item_ids": ["other001"]}, auth=True)
    check("BR-U5-07: unretire で復活（retired_at=NULL）",
          st == 200 and body5.get("retired") == 1, f"body={body5}")
    st, body6 = _req("/admin/items/unretire", {"item_ids": ["other001"]}, auth=True)
    check("BR-U5-07: 復活も冪等（既に現役なら no-op）",
          body6.get("retired") == 0, f"body={body6}")

    # ---------------- BR-U5-09: 充足割れで発行拒否 ----------------
    # 現行プールは 2 件しかない（frozen001 廃止済 / other001 現役）→ 充足不可。
    st, body7 = _req("/admin/tokens", {"count": 1}, auth=True)
    check("BR-U5-09: 充足を割った状態では token_issue が拒否される",
          body7.get("ok") is False and body7.get("gate_errors"),
          f"gate_errors={body7.get('gate_errors')}")

    # ---------------- 認証 ----------------
    st, _ = _req("/admin/items/retire", {"item_ids": ["x"]}, auth=False)
    check("U5-NFR-12: 未認証の廃止は 401", st == 401, f"status={st}")

    passed = sum(1 for r in RESULTS if r["pass"])
    total = len(RESULTS)
    print(f"\n{passed}/{total} PASS")
    with open("result-u5-integration.json", "w", encoding="utf-8") as f:
        json.dump({"results": RESULTS, "passed": passed, "total": total}, f,
                  ensure_ascii=False, indent=2)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
