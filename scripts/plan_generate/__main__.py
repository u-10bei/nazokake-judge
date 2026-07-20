"""LC-U6-07 — plan_generate CLI（構成 → 検証 → seed 再試行 → 明示失敗）。

    python -m scripts.plan_generate \
        --pool items_real.json --composition plans/primary/composition.json \
        --constraints plans/primary/constraints.json --out-dir plans/primary --seed 20260720

**生成と投入は分ける**（U6 Code Gen Q1=A）: 本 CLI は**ファイルを書くだけ**で D1 には
触れない。投入は `scripts/plan_ingest`（**生成と投入は別 CLI**: BR-U6-12 の「コミット」が間に挟まるため）。BR-U6-12 が「**両セットはリポジトリにコミットして
固定 → D1 には選択セットのみ投入**」を要求する以上、**生成と投入の間に「コミット」という
人間の行為が挟まる**ためである（U4b の「取得と推定の分離」と同型）。

**決定論**（BR-U6-11）: 同一 (プール, 期待組成, 制約, seed) → 同一プラン。再試行を挟むため
**初期 seed と成功試行番号の両方**をメタに記録する（初期 seed だけでは再現できない）。

**明示失敗**（U6-NFR-11）: 正則不能（`2J` が `n` で割り切れない・`m` 奇数）/ 分割定員の
総和 ≠ J / 期待組成の不一致 / `plan_set` の取り違え / 再試行上限。
"""

from __future__ import annotations

# src/ を import パスへ（F-8）。schema/兄弟モジュール import より前に実行する。
try:
    from scripts import _bootstrap  # noqa: F401  (python -m scripts.plan_generate)
except ImportError:  # pragma: no cover
    import _bootstrap  # noqa: F401

import argparse
import json
import os
import sys

from schema import POOL_LAYERS, Item

from scripts.plan_generate.constraints import (
    ConstraintError,
    load_composition,
    load_constraints,
    validate_inputs,
)
from scripts.plan_generate.graph_build import build_regular_edges
from scripts.plan_generate.partition import (
    PartitionError,
    check_block_feasibility,
    partition_edges,
    split_sizes,
)
from scripts.plan_generate.placement import search_placement
from scripts.plan_generate.sequencing import build_slot_rows
from scripts.plan_generate.verify import content_hash, render_report, verify_plan

EXIT_OK = 0
EXIT_FAIL = 1


def _load_pool(path: str) -> list[Item]:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    raw = json.loads(text) if text.lstrip().startswith("[") else [
        json.loads(line) for line in text.splitlines() if line.strip()]
    return [Item.model_validate(r) for r in raw]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="plan_generate",
        description="事前生成割当プランの生成（U6・オフライン・D1 に触れない）")
    ap.add_argument("--pool", required=True, help="プール JSON（items_*.json）")
    ap.add_argument("--composition", required=True, help="期待組成 JSON（セット別）")
    ap.add_argument("--constraints", required=True, help="制約ファイル JSON（セット別）")
    ap.add_argument("--out-dir", required=True, help="出力先（plans/<plan_set>/）")
    ap.add_argument("--seed", type=int, default=20260720, help="初期 seed（決定論）")
    ap.add_argument("--k", type=int, default=3, help="評価者内の同一 item 出現上限")
    ap.add_argument("--cross-target", type=float, default=0.65, help="層間ペア比率の下限")
    ap.add_argument("--blocks", type=int, default=2, help="ブロック数（逐次推定の単位）")
    ap.add_argument("--max-attempts", type=int, default=50, help="seed 再試行の上限")
    ap.add_argument("--practice", default=None,
                    help="練習ペア JSON（[[a,b],...]・開示セット。省略時は練習なし）")
    args = ap.parse_args(argv)

    # ---- 入力読込・三つ組の整合検証（明示失敗） ----
    try:
        pool = _load_pool(args.pool)
        comp = load_composition(args.composition)
        cons = load_constraints(args.constraints)
        validate_inputs(pool, comp, cons)
    except (ConstraintError, ValueError, OSError) as e:
        print(f"[error] 入力検証に失敗: {e}", file=sys.stderr)
        return EXIT_FAIL

    practice: list[tuple[str, str]] = []
    if args.practice:
        with open(args.practice, encoding="utf-8") as f:
            practice = [tuple(p) for p in json.load(f)]

    in_pool = [it for it in pool if it.layer in POOL_LAYERS]
    sizes = split_sizes(comp.n_pairs, comp.n_slots)

    # ★実行可能性の事前検査（U6-NFR-11）: ブロック連結が原理的に不可能な組合せは
    #   **リトライせず即座に明示失敗**する（「seed 運が悪い」との誤認を防ぐ）。
    try:
        check_block_feasibility(comp.n_items, comp.n_pairs, comp.n_slots, args.blocks)
    except PartitionError as e:
        print(f"[error] パラメータが実行不能: {e}", file=sys.stderr)
        return EXIT_FAIL

    # ---- 構成 → 検証 → seed 再試行 ----
    last_report = None
    for attempt in range(args.max_attempts):
        seed = args.seed + attempt
        order, pscore = search_placement(
            in_pool, cons, m=comp.m_per_item, seed=seed, cross_target=args.cross_target)
        if pscore.forbidden_violations:
            last_report = f"禁止辺 {pscore.forbidden_violations} 本が排除できず（配置探索）"
            continue
        try:
            edges = build_regular_edges(order, comp.m_per_item)
            slots = partition_edges(edges, sizes, k=args.k, seed=seed)
        except (PartitionError, ValueError) as e:
            last_report = str(e)
            continue

        rows = build_slot_rows(slots, practice, cons.avoid_adjacent_groups, seed=seed)
        v = verify_plan(in_pool, rows, cons, m=comp.m_per_item, k=args.k,
                        n_slots=comp.n_slots, n_blocks=args.blocks,
                        cross_target=args.cross_target,
                        likert_expected=len(cons.likert_targets) or None)
        if not v.ok:
            last_report = "; ".join(v.errors)
            continue

        # ---- 成功: ファイル出力（D1 には触れない） ----
        os.makedirs(args.out_dir, exist_ok=True)
        chash = content_hash(rows, cons.likert_targets)
        meta = {
            "plan_set": comp.plan_set, "seed": args.seed, "attempt": attempt,
            "content_hash": chash, "n_items": comp.n_items, "n_slots": comp.n_slots,
            "n_pairs": comp.n_pairs, "m_per_item": comp.m_per_item,
            "likert_targets": list(cons.likert_targets),
            "generated_at": "GENERATED_AT_PLACEHOLDER",
        }
        with open(os.path.join(args.out_dir, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        with open(os.path.join(args.out_dir, "plan.meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        with open(os.path.join(args.out_dir, "verification.md"), "w", encoding="utf-8") as f:
            f.write(render_report(v, plan_set=comp.plan_set))

        print(f"[ok] plan_set={comp.plan_set} seed={args.seed} attempt={attempt} "
              f"hash={chash[:12]}…")
        print(f"     露出gap={v.exposure_gap} 連結成分={v.n_components} "
              f"ブロック連結={v.block_components} 層間={v.cross_layer_ratio:.3f} "
              f"最大出現={v.max_occurrence} 同一ペア={v.duplicate_pairs}")
        if v.discouraged_violations:
            print(f"[warn] 忌避ペアの残存 {len(v.discouraged_violations)} 件（ソフト・失敗ではない）",
                  file=sys.stderr)
        print(f"[info] 出力: {args.out_dir}/plan.json / plan.meta.json / verification.md")
        print("[info] ★このディレクトリを**コミット**してください"
              "（両セットの事前固定 = commit 履歴とハッシュが証跡, BR-U6-12）", file=sys.stderr)
        return EXIT_OK

    print(f"[error] {args.max_attempts} 回の試行で条件を満たすプランが得られませんでした。"
          f"最後の理由: {last_report}", file=sys.stderr)
    return EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
