"""token_issue CLI（US-R05）— トークンを管理 API 経由で発行し配布用 URL 一覧を出力する。

発行時充足ゲート（BR-U4a-12）: 現行プールが未充足なら API が発行拒否（ok=false, gate_errors）。
出力: トークン付き URL 一覧を stdout + ファイル（配布用・gitignore, BR-U4a-07）。

使い方:
  ADMIN_BASIC_USER=... ADMIN_BASIC_PASSWORD=... \
  uv run python -m scripts.token_issue 30 \
      --base-url https://<worker>.workers.dev \
      --url-template 'https://<worker>.workers.dev/?token={token}' \
      --out tokens.dist.txt

**配布 URL は `/?token={token}` が正**: フロント（frontend/app.js）は `?token=` クエリを読む
（U2-NFR-04）。`/s/{token}` 等の未知パスは SPA フォールバック不使用ゆえ 404（Infra Q2）。
"""

from __future__ import annotations

# src/ を import パスへ（F-8）。schema/scripts import より前に実行する。
try:
    from scripts import _bootstrap  # noqa: F401  (python -m scripts.token_issue)
except ImportError:
    import _bootstrap  # noqa: F401  (python scripts/token_issue.py)

import argparse
import json
import sys

from scripts._client import base_url, post_json


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="トークン発行 (token_issue)")
    ap.add_argument("count", type=int, help="発行数")
    ap.add_argument("--base-url", default=None, help="管理 API のベース URL（省略時 ADMIN_API_BASE）")
    ap.add_argument("--url-template", required=True,
                    help="配布 URL テンプレート（{token} を含める。例: 'https://<host>/?token={token}'）")
    ap.add_argument("--out", default=None, help="URL 一覧の出力ファイル（配布用・gitignore 対象）")
    args = ap.parse_args(argv)

    if "{token}" not in args.url_template:
        raise SystemExit("--url-template は {token} を含めてください")

    result = post_json(f"{base_url(args.base_url)}/admin/tokens", {"count": args.count})

    if not result.get("ok"):
        print(f"[error] 発行拒否（プール未充足ゲート BR-U4a-12）: {result.get('gate_errors')}",
              file=sys.stderr)
        return 1

    urls = [args.url_template.format(token=t) for t in result["tokens"]]
    for u in urls:
        print(u)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(urls) + "\n")
        print(f"[info] {len(urls)} 件を {args.out} に出力（配布用・gitignore）", file=sys.stderr)
    print(f"[info] issued_at={result.get('issued_at')} count={len(urls)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
