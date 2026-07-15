"""LC-U4b-07 — bt_aggregate CLI（薄い I/O 境界, DP-U4b-02/03）。

`python -m scripts.bt_aggregate export.json [--out result.json ...]`

副作用（ファイル I/O・終了コード・出力）は本モジュールに集約し、統計ロジックは純関数
（aggregate/graph/mm/calibrate/assemble）に委ねる。オーケストレーション本体 aggregate_bundle は
副作用なし（BTResult を返すだけ）＝PU4b-6 の U3 突合テストが CLI 越し/直接の双方で書ける。

終了コード契約（U4b-NFR-11 / DP-U4b-03）:
  非0(=1, 失敗) : 入力ファイル不在・JSON パース不能・ExportBundle 検証失敗・版不一致（既定）
  0(成功)       : 正常 + warnings 系（非連結・較正スキップ・未収束・版不一致緩和・除外 item）

出力: JSON（機械可読）は --out（ファイル）指定時はファイルへ・stdout を人間可読テーブルに、
--out 省略時は JSON を stdout（パイプ可能）・人間可読テーブルを stderr に出す。warnings は
BTResult.warnings（機械可読）とテーブル冒頭（人間可読）に二重表示する（DP-U4b-03）。
"""

from __future__ import annotations

# src/ を import パスへ（F-8）。schema/兄弟モジュール import より前に実行する。
try:
    from scripts import _bootstrap  # noqa: F401  (python -m scripts.bt_aggregate)
except ImportError:  # pragma: no cover
    import _bootstrap  # noqa: F401

import argparse
import json
import sys

from pydantic import ValidationError

from schema import BTResult, BTSource, EXPORT_FORMAT_VERSION, ExportBundle

from scripts.bt_aggregate.aggregate import aggregate
from scripts.bt_aggregate.assemble import assemble_result
from scripts.bt_aggregate.calibrate import calibrate
from scripts.bt_aggregate.graph import (
    connected_components,
    largest_component,
    restrict_to_component,
)
from scripts.bt_aggregate.mm import fit_bt

EXIT_OK = 0
EXIT_FAIL = 1


def aggregate_bundle(
    bundle: ExportBundle,
    *,
    alpha: float,
    max_iter: int,
    tol: float,
    warnings: list[str] | None = None,
) -> BTResult:
    """ExportBundle → BTResult（純オーケストレーション・副作用なし）。

    版検証・ファイル I/O・終了コードは CLI(main) の責務。ここは純関数合成のみ。
    """
    warns = list(warnings) if warnings else []

    # 1) 正準集計（生カウント・α 非適用, DP-U4b-01 / Q2 不変条件）。
    wins, pair_counts = aggregate(bundle.judgments)

    # 2) 連結成分 → 最大成分へ制限（PU4b-4 の純合成, DP-U4b-02）。
    components = connected_components(pair_counts)
    estimated = largest_component(components)
    estimated_ids = set(estimated)

    if len(components) > 1:
        warns.append(
            f"比較グラフが非連結（{len(components)} 成分）: 最大連結成分"
            f"（{len(estimated)} item）のみ推定。他成分はスコア比較不能（BR-U4b-02）。"
        )
    if pair_counts and estimated:
        r_wins, r_pairs = restrict_to_component(wins, pair_counts, estimated)
        # 3) MM 推定（α は fit_bt 内部のみ, Q2 不変条件）。
        theta, converged, iterations = fit_bt(
            r_wins, r_pairs, alpha=alpha, max_iter=max_iter, tol=tol
        )
        if not converged:
            warns.append(
                f"MM が {iterations} 反復で収束せず（converged=false）。"
                "結果は出力（--tol/--max-iter を調整可, BR-U4b-01）。"
            )
    else:
        theta, converged, iterations = {}, True, 0
        warns.append("有効な本番判定がありません（推定対象なし）。生データのみ返却。")

    # 除外 item（推定対象外・孤立含む）の可視化を警告に残す（BR-U4b-07）。
    excluded = [it.item_id for it in bundle.items if it.item_id not in estimated_ids]
    if excluded and estimated_ids:
        warns.append(
            f"推定対象外の item {len(excluded)} 件は bt_score=null で残置（除外可視化, BR-U4b-07）。"
        )

    # 4) Likert 較正（target_ref=item_id, BR-U4b-05/06）。
    item_ids = {it.item_id for it in bundle.items}
    outcome = calibrate(theta, bundle.likert, item_ids)
    if outcome.skip_reason is not None:
        warns.append(f"Likert 較正をスキップ（{outcome.skip_reason}）: 生 θ のみ（BR-U4b-06）。")
    if outcome.excluded_targets:
        warns.append(
            f"target_ref ∉ items のアンカー {len(outcome.excluded_targets)} 件を較正から除外"
            f"（BR-U4b-05）: {', '.join(outcome.excluded_targets)}"
        )

    # 5) BTResult 組立（source エコーバック・rank・matches/wins 生, BR-U4b-08/09）。
    return assemble_result(
        source=BTSource(schema_version=bundle.schema_version, exported_at=bundle.exported_at),
        all_items=bundle.items,
        wins=wins,
        pair_counts=pair_counts,
        theta=theta,
        components=components,
        estimated_ids=estimated_ids,
        calibration=outcome.calibration,
        alpha=alpha,
        converged=converged,
        iterations=iterations,
        warnings=warns,
    )


def format_table(result: BTResult) -> str:
    """人間可読テーブル（層別・スコア降順 + warnings 冒頭二重表示, DP-U4b-03）。"""
    lines: list[str] = []
    if result.warnings:
        lines.append("=== warnings ===")
        for w in result.warnings:
            lines.append(f"  - {w}")
        lines.append("")

    lines.append(
        f"n_items={result.n_items} n_comparisons={result.n_comparisons} "
        f"n_components={result.n_components} estimated={result.estimated_component_size} "
        f"converged={result.converged} iterations={result.iterations} alpha={result.alpha}"
    )
    if result.calibration is not None:
        c = result.calibration
        lines.append(
            f"calibration: n_anchors={c.n_anchors} slope={c.slope:.6g} "
            f"intercept={c.intercept:.6g}"
        )
    else:
        lines.append("calibration: なし（スキップ）")
    lines.append("")

    header = f"{'item_id':<12}{'layer':<8}{'θ':>12}{'calibrated':>14}{'rank':>6}{'matches':>9}{'wins':>7}"
    lines.append(header)
    lines.append("-" * len(header))

    # 層別・各層内スコア降順（除外 item=θ null は末尾）。
    def sort_key(s):
        return (s.layer, -(s.bt_score if s.bt_score is not None else float("-inf")), s.item_id)

    for s in sorted(result.items, key=sort_key):
        theta_s = f"{s.bt_score:.4f}" if s.bt_score is not None else "—"
        cal_s = f"{s.calibrated_score:.4f}" if s.calibrated_score is not None else "—"
        rank_s = str(s.rank) if s.rank is not None else "—"
        lines.append(
            f"{s.item_id:<12}{s.layer:<8}{theta_s:>12}{cal_s:>14}{rank_s:>6}"
            f"{s.matches:>9}{s.wins:>7}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bt_aggregate",
        description="BT 集計スクリプト（U4b・オフライン pure-Python）",
    )
    ap.add_argument("input", help="ExportBundle JSON のパス（U3 /admin/export?format=json）")
    ap.add_argument("--out", default=None, help="BTResult JSON の出力ファイル（省略時 stdout）")
    ap.add_argument("--alpha", type=float, default=1.0,
                    help="観測ペア限定の擬似データ正則化（既定 1.0＝各観測ペアに仮想引き分け 1 件）")
    ap.add_argument("--max-iter", type=int, default=10000, help="MM 最大反復（既定 10000）")
    ap.add_argument("--tol", type=float, default=1e-10, help="収束閾値（π 最大変化量, 既定 1e-10）")
    ap.add_argument("--allow-version-mismatch", action="store_true",
                    help="schema_version 不一致を警告で続行（既定はエラー終了, BR-U4b-11）")
    args = ap.parse_args(argv)

    # --- パラメータ検証（純関数の前提条件を CLI 境界で強制, DP-U4b-03） ---
    # mm.fit_bt は α>0 のとき w̃_i>0＝log/除算が有限（BR-U4b-03）。α≤0 は math domain error や
    # 無意味な結果（θ 全 0）を招くため、正規運用経路（README の α 感度チェック）で到達しうる
    # 不正値を「パラメータ不正」として非0終了に写す（U4b-NFR-11 の非0リストに含める）。
    if not (args.alpha > 0.0):
        print(f"[error] --alpha は正の値が必要です（観測ペア限定正則化, BR-U4b-03）: {args.alpha}",
              file=sys.stderr)
        return EXIT_FAIL
    if args.max_iter < 1:
        print(f"[error] --max-iter は 1 以上が必要です: {args.max_iter}", file=sys.stderr)
        return EXIT_FAIL
    if not (args.tol > 0.0):
        print(f"[error] --tol は正の値が必要です: {args.tol}", file=sys.stderr)
        return EXIT_FAIL

    # --- 入力読込（失敗は非0） ---
    try:
        with open(args.input, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        print(f"[error] 入力ファイルが見つかりません: {args.input}", file=sys.stderr)
        return EXIT_FAIL
    except json.JSONDecodeError as e:
        print(f"[error] JSON パースに失敗: {e}", file=sys.stderr)
        return EXIT_FAIL

    try:
        bundle = ExportBundle.model_validate(raw)
    except ValidationError as e:
        print(f"[error] ExportBundle 検証に失敗: {e}", file=sys.stderr)
        return EXIT_FAIL

    # --- 版検証（不一致は既定エラー, BR-U4b-11） ---
    warnings: list[str] = []
    if bundle.schema_version != EXPORT_FORMAT_VERSION:
        msg = (f"schema_version 不一致: 入力={bundle.schema_version} "
               f"期待={EXPORT_FORMAT_VERSION}")
        if not args.allow_version_mismatch:
            print(f"[error] {msg}（--allow-version-mismatch で続行可）", file=sys.stderr)
            return EXIT_FAIL
        warnings.append(f"版不一致を緩和して続行: {msg}（BR-U4b-11）")

    # --- 集計（純オーケストレーション） ---
    result = aggregate_bundle(
        bundle, alpha=args.alpha, max_iter=args.max_iter, tol=args.tol, warnings=warnings
    )

    # --- 出力（JSON=機械可読 / テーブル=人間可読の二重表示, DP-U4b-03） ---
    payload = result.model_dump_json(indent=2)
    table = format_table(result)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload + "\n")
        print(table)                                   # 人間可読テーブルは stdout
        print(f"[info] BTResult を {args.out} に出力", file=sys.stderr)
    else:
        print(payload)                                 # JSON は stdout（パイプ可能）
        print(table, file=sys.stderr)                  # テーブルは stderr（stdout を汚さない）
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
