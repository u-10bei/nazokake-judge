"""plan_ingest CLI（U6）— 生成済みプランを管理 API 経由で D1 へ投入する。

**`plan_generate` と分離した理由**（Code Gen Q1=A）: 両者の間に **`git commit` が挟まる**
（BR-U6-12: 両セットをリポジトリにコミットして固定し、commit 履歴 + 内容ハッシュを証跡と
する）。生成と投入が 1 コマンドだと**コミット前のプランを投入できてしまい**、証跡が
「コミットされたものが投入された」を保証しなくなる。

**この CLI の主目的はハッシュ照合**（DP-U6-07）。`plan.json` の行と `plan.meta.json` の
`likert_targets` から **`content_hash` を再計算**し、メタに記録された値と一致することを
**投入前に**確認する。`content_hash` は `plan_generate` と**同一の実装を import** している
（再実装すると照合が自己満足になり、ハッシュのずれを検出できない）。

不一致が意味すること:
  - 生成後にファイルが編集された（手直し・マージ事故）
  - `plan.json` と `plan.meta.json` が**別々の生成実行に由来**する（取り違え）
いずれもカットオーバーで最も事故らせたくない箇所ゆえ、**照合失敗は投入せず exit 1**。

**運用順序**（README のカットオーバー手順）:
  ② プール投入 → ③ 生成 + **コミット** → ④ **本 CLI で投入 → activate** → ⑤ トークン発行

⑤ を ④ より先に行うと束縛先（`plan_set`, `plan_index`）が未定になる。activate は
**収集開始後は 409 で拒否**される（U6-NFR-20）＝切替は収集開始前に限られる。

使い方:
  ADMIN_BASIC_USER=... ADMIN_BASIC_PASSWORD=... \
  uv run python -m scripts.plan_ingest plans/primary \
      --base-url https://<worker>.workers.dev --activate

  # 投入のみ（有効化は後で別途）
  uv run python -m scripts.plan_ingest plans/primary --base-url https://<worker>.workers.dev

  # 投入済みセットを有効化するだけ
  uv run python -m scripts.plan_ingest plans/primary --activate-only --base-url ...
"""

from __future__ import annotations

# src/ を import パスへ（F-8）。schema/scripts import より前に実行する。
try:
    from scripts import _bootstrap  # noqa: F401  (python -m scripts.plan_ingest)
except ImportError:  # pragma: no cover
    import _bootstrap  # noqa: F401  (python scripts/plan_ingest.py)

import argparse
import json
import os
import sys
import urllib.error

from scripts._client import base_url, post_json
from scripts.plan_generate.verify import content_hash


def _load(path: str) -> object:
    if not os.path.exists(path):
        raise SystemExit(
            f"[error] {path} がありません。先に plan_generate で生成してください:\n"
            f"    uv run python -m scripts.plan_generate --pool ... --out-dir "
            f"{os.path.dirname(path) or '.'}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _post(url: str, payload: dict) -> dict:
    """POST し、HTTP エラーでもサーバの JSON 本文を読めるようにする。

    管理 API は 400（検証失敗）・409（activate ガード）で**理由を JSON で返す**——
    これを握りつぶすと運用者が「なぜ拒否されたか」を追えない。
    """
    try:
        return post_json(url, payload)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body[:300]}
        return {"ok": False, "status": e.code, **parsed}


def _activate(api: str, plan_set: str) -> int:
    """有効化と結果表示（`--activate` / `--activate-only` の**共通経路**）。

    分岐ごとに書くと 409 の案内が片方だけになる（実測で発覚）。運用上 409 に当たりやすい
    のはむしろ**後から有効化する `--activate-only`** ——収集が始まった後に「まだ有効化して
    いなかった」と気づく順序ゆえ。
    """
    result = _post(f"{api}/admin/plan/activate", {"plan_set": plan_set})
    if result.get("ok"):
        print(f"有効化: {plan_set}（hash={result.get('content_hash')}）")
        return 0

    if result.get("status") == 409:
        # 409 = 収集開始後（U6-NFR-20）。運用者が最も戸惑う拒否ゆえ意味を添える。
        print(f"[error] 有効化を拒否されました（収集開始後の切替は不可）: "
              f"{result.get('error')}", file=sys.stderr)
        print("  プランセットの切替は実験の作り直しに相当します。判定データをリセット"
              "する場合は scripts/reset-responses.sql を参照してください。", file=sys.stderr)
    else:
        print(f"[error] 有効化に失敗: {result.get('error') or result}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="plan_ingest",
        description="生成済みプランの投入 / 有効化（ハッシュ照合つき）",
    )
    ap.add_argument("plan_dir", help="plan.json / plan.meta.json のあるディレクトリ")
    ap.add_argument("--base-url", default=None, help="管理 API のベース URL（省略時 ADMIN_API_BASE）")
    ap.add_argument("--activate", action="store_true",
                    help="投入に続けて有効化する（省略時は投入のみ）")
    ap.add_argument("--activate-only", action="store_true",
                    help="投入は行わず、投入済みセットの有効化だけを行う")
    args = ap.parse_args(argv)

    meta = _load(os.path.join(args.plan_dir, "plan.meta.json"))
    plan_set = meta["plan_set"]
    api = base_url(args.base_url)

    if args.activate_only:
        return _activate(api, plan_set)

    rows = _load(os.path.join(args.plan_dir, "plan.json"))

    # ---- ★ハッシュ照合（DP-U6-07）: 投入前に必ず行う ----
    recomputed = content_hash(rows, meta.get("likert_targets") or [])
    if recomputed != meta.get("content_hash"):
        print("[error] ★内容ハッシュが一致しません。**投入を中止しました**。", file=sys.stderr)
        print(f"  plan.meta.json 記載 : {meta.get('content_hash')}", file=sys.stderr)
        print(f"  plan.json から再計算: {recomputed}", file=sys.stderr)
        print("  生成後にファイルが編集されたか、plan.json と plan.meta.json が"
              "別々の生成実行に由来します。", file=sys.stderr)
        print("  → plan_generate を同じ --seed で再実行して再生成してください"
              f"（seed={meta.get('seed')} attempt={meta.get('attempt')}）。", file=sys.stderr)
        return 1
    print(f"✅ ハッシュ照合 OK: {recomputed[:16]}…（{len(rows)} 行）")

    result = _post(f"{api}/admin/plan", {"meta": meta, "rows": rows})
    if not result.get("ok"):
        print(f"[error] 投入に失敗: {result.get('error') or result}", file=sys.stderr)
        return 1
    print(f"投入: {plan_set} — {result.get('rows')} 行 "
          f"（{meta.get('n_slots')} スロット・n_items={meta.get('n_items')}）")

    # サーバ側が記録したハッシュも突き合わせる（投入経路での取り違えを閉じる）。
    if result.get("content_hash") and result["content_hash"] != recomputed:
        print(f"[error] ★サーバ記録のハッシュが一致しません: {result['content_hash']}",
              file=sys.stderr)
        return 1

    if not args.activate:
        print(f"[info] 有効化はまだです。次: uv run python -m scripts.plan_ingest "
              f"{args.plan_dir} --activate-only", file=sys.stderr)
        return 0

    if (rc := _activate(api, plan_set)) != 0:
        return rc

    print(f"[info] 次はトークン発行です（★この順序が必要——先に発行すると束縛先が未定）:\n"
          f"    uv run python -m scripts.token_issue {meta.get('n_slots')} "
          f"--url-template 'https://<host>/?token={{token}}' --out tokens.dist.txt",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
