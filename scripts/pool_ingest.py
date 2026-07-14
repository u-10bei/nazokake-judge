"""pool_ingest CLI（US-R06）— 刺激プールを管理 API 経由で D1 に投入する。

入力: JSON 配列または JSONL（1 行 1 レコード）。各レコード = {item_id, layer, body, body_ref?}。
層ラベル必須（BR-U4a-01）・本文必須（BR-U4a-02）は schema.validate_item で検証。
段階投入可（プール未充足でも warning で投入は成功, BR-U4a-05）。

使い方:
  ADMIN_BASIC_USER=... ADMIN_BASIC_PASSWORD=... \
  uv run python -m scripts.pool_ingest items.json --base-url https://<worker>.workers.dev
"""

from __future__ import annotations

# src/ を import パスへ（F-8）。schema import より前に実行する。
try:
    from scripts import _bootstrap  # noqa: F401  (python -m scripts.pool_ingest)
except ImportError:
    import _bootstrap  # noqa: F401  (python scripts/pool_ingest.py)

import argparse
import json
import sys

from pydantic import ValidationError

from schema import Item, validate_item
from scripts._client import base_url, post_json


def _load_records(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text_stripped = text.lstrip()
    if text_stripped.startswith("["):
        return json.loads(text)
    # JSONL
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="刺激プール投入 (pool_ingest)")
    ap.add_argument("input", help="JSON 配列 または JSONL ファイル")
    ap.add_argument("--base-url", default=None, help="管理 API のベース URL（省略時 ADMIN_API_BASE）")
    args = ap.parse_args(argv)

    records = _load_records(args.input)
    # クライアント側でも検証（不正は早期に弾いて往復を減らす。最終検証は API 側）。
    items: list[Item] = []
    local_rejects = []
    for r in records:
        try:
            items.append(validate_item(r))
        except ValidationError:
            local_rejects.append(r.get("item_id", "?"))
    if local_rejects:
        print(f"[warn] クライアント検証で {len(local_rejects)} 件不正: {local_rejects}", file=sys.stderr)

    payload = {"items": [it.model_dump() for it in items]}
    result = post_json(f"{base_url(args.base_url)}/admin/items", payload)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("sufficiency_warnings"):
        print(f"[warn] プール未充足（段階投入継続可）: {result['sufficiency_warnings']}", file=sys.stderr)
    # 拒否 or クライアント不正があれば非ゼロ終了（BR-U4a-07 / FD 終了コード規約）。
    return 1 if (result.get("rejected") or local_rejects) else 0


if __name__ == "__main__":
    raise SystemExit(main())
