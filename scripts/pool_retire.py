"""pool_retire CLI（U5）— 作品の出題停止 / 復活を管理 API 経由で行う。

**用途**: 著作権上の配慮などで、投入済み作品を**今後出題しない**ようにする（論理削除）。
**物理削除ではない**: 行は残り、**それまでの判定結果は有効のまま**（BR-U5-01）。

反映範囲（BR-U5-03）:
  - **新規セッション**: 廃止 item はペア列・練習・Likert のいずれにも出なくなる。
  - **進行中セッション**: ペア列は開始時に確定済みゆえ **そのまま出題され続ける**
    （完了 or 非アクティブ 48h まで）。即時停止が必要な場合は別途対応が要る。
  - **エクスポート / BT 集計**: 廃止 item も `items` に残り続ける（自己完結性 BR-U3-07）。

冪等（BR-U5-06/07）: 既に目的の状態なら no-op。再廃止しても**初回の廃止時刻を保持**する。
**DB の `retired_at` は現在状態のみ**を表す（BR-U5-13）＝履歴ではない。履歴は
サーバの `admin_log`（`item_retire`/`item_unretire`）と**本 CLI の証跡ファイル**が担うが、
**`admin_log` は `wrangler tail` で追っている間しか流れず永続化されない**ため、
**後から示せる証跡は下記のファイルが正**。

使い方:
  ADMIN_BASIC_USER=... ADMIN_BASIC_PASSWORD=... \
  uv run python -m scripts.pool_retire i001 i002 --base-url https://<worker>.workers.dev

  # 復活（誤操作の回復）
  uv run python -m scripts.pool_retire i001 --unretire --base-url https://<worker>.workers.dev

**証跡**: 実行のたびに `retirement-log.jsonl` へ 1 行追記される（`--log` で変更・`--no-log` で
抑止）。**サーバの `admin_log` は `wrangler tail` で追っている間しか流れず永続化されない**ため、
著作権対応で「いつ・何を・なぜ」を示す責任はこのファイルが負う。**`item_id` のみで本文を
含まない**ので**コミットしてよい**（git 履歴が改竄検知と永続性を兼ねる）。
"""

from __future__ import annotations

# src/ を import パスへ（F-8）。schema/scripts import より前に実行する。
try:
    from scripts import _bootstrap  # noqa: F401  (python -m scripts.pool_retire)
except ImportError:  # pragma: no cover
    import _bootstrap  # noqa: F401  (python scripts/pool_retire.py)

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from scripts._client import base_url, post_json

_DEFAULT_LOG = "retirement-log.jsonl"


def _append_record(path: str, record: dict) -> None:
    """操作の証跡を**追記型**で残す（1 行 1 操作の JSONL）。

    **なぜ CLI 側で残すのか**: サーバの `admin_log` は `wrangler tail` で**追っている間だけ**
    流れ、**永続化されない**。著作権配慮での出題停止は「**いつ・何を・なぜ**止めたか」を
    後から示せる必要があるため、操作した側で確実に残す。

    **本文（body）は含まれない**（`item_id` のみ）ゆえ、このファイルは**コミットしてよい**——
    むしろ git 履歴に載せることが改竄検知と永続性の両方を担う。
    """
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="pool_retire",
        description="作品の出題停止 / 復活 (pool_retire・論理削除)",
    )
    ap.add_argument("item_ids", nargs="+", help="対象の item_id（複数指定可）")
    ap.add_argument("--base-url", default=None, help="管理 API のベース URL（省略時 ADMIN_API_BASE）")
    ap.add_argument("--unretire", action="store_true",
                    help="出題停止を解除して復活させる（既定は停止）")
    ap.add_argument("--reason", default=None,
                    help="停止/復活の理由（証跡に残る。例: 著作権配慮・許諾不成立）")
    ap.add_argument("--log", default=_DEFAULT_LOG,
                    help=f"証跡の追記先 JSONL（既定 {_DEFAULT_LOG}・コミット推奨）")
    ap.add_argument("--no-log", action="store_true", help="証跡を残さない（非推奨）")
    args = ap.parse_args(argv)

    route = "unretire" if args.unretire else "retire"
    verb = "復活" if args.unretire else "出題停止"
    result = post_json(f"{base_url(args.base_url)}/admin/items/{route}",
                       {"item_ids": args.item_ids})

    # 分類表示（U5-NFR-11）: retired / already_retired / not_found。
    changed = result.get("retired", 0)
    already = result.get("already_retired") or []
    not_found = result.get("not_found") or []

    # ★証跡を残す（サーバの admin_log は永続化されないため）。
    if not args.no_log:
        _append_record(args.log, {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": route,
            "item_ids": args.item_ids,
            "reason": args.reason,
            "changed": changed,
            "already": already,
            "not_found": not_found,
            "target": os.environ.get("ADMIN_API_BASE") if args.base_url is None
                      else args.base_url,
        })

    print(f"{verb}: {changed} 件")
    if already:
        state = "既に現役" if args.unretire else "既に停止済み"
        print(f"  変更なし（{state}）: {', '.join(already)}")
    if not_found:
        # 「既に存在しない＝目的は達成」ゆえ失敗にはしない。ただしタイポ検出のため警告を出す
        # （U5-NFR-11: 冪等な再実行を失敗扱いにすると運用が回らない）。
        print(f"[warn] items に存在しない item_id: {', '.join(not_found)}", file=sys.stderr)

    if not args.no_log:
        print(f"[info] 証跡を {args.log} に追記しました（**コミットしてください**——"
              f"サーバの admin_log は永続化されません）。", file=sys.stderr)
    if not args.reason:
        print("[warn] --reason が未指定です。著作権対応では「なぜ止めたか」も"
              "証跡に必要になります。", file=sys.stderr)

    if not args.unretire and changed:
        print("[info] 反映は**新規セッションのみ**。進行中セッションには出題され続けます"
              "（完了 or 非アクティブ 48h まで）。", file=sys.stderr)
        print("[info] 過去の判定結果・エクスポート・BT 集計は従来どおり有効です。",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
