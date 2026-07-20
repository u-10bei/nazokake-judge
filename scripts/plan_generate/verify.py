"""LC-U6-06 — プラン検証（投入前ゲート・純関数, BR-U6-10 / PU6-8）。

**投入前に失敗を検出できる**ことが事前生成の価値（実行時生成では原理的に不可能）。

検証項目:
  ① **露出 gap = 0**（全 item がちょうど m 回出場）
  ② **全体連結**（比較グラフの連結成分 = 1）
  ③ **k 制約**（評価者内の同一 item 出現 ≤ k）
  ④ **同一ペア 0**（同一評価者に同一ペアを出さない）
  ⑤ **層間比率 ≥ cross_target**
  ⑥ **★ブロック連結**（各ブロックの辺和集合だけで連結成分 = 1, BR-U6-20）
  **PU6-8** **禁止辺の不在**（ハード）
  + **Likert 固定リスト**（10 件想定・プール内・重複なし, BR-U6-06）

**忌避（ソフト）は違反してもエラーにせずレポートのみ**（BR-U6-21）。
"""

from __future__ import annotations

from schema import Item, PlanVerification

from scripts.plan_generate.constraints import Constraints
from scripts.plan_generate.graph_build import connected_components, degree_of


def verify_plan(pool: list[Item], rows: list[dict], cons: Constraints, *,
                m: int, k: int, n_slots: int, n_blocks: int = 2,
                cross_target: float = 0.65,
                likert_expected: int | None = None) -> PlanVerification:
    """プラン行（`sequencing.build_slot_rows` の出力）を検証する。"""
    ids = [it.item_id for it in pool]
    layers = {it.item_id: it.layer.value for it in pool}
    errors: list[str] = []

    prod = [r for r in rows if not r["is_practice"]]
    edges = [(r["item_left"], r["item_right"]) for r in prod]
    norm = [tuple(sorted(e)) for e in edges]

    # ① 露出 gap（構成で保証されるが検証は保険）
    deg = degree_of(norm, ids)
    gap = (max(deg.values()) - min(deg.values())) if deg else 0
    if gap != 0:
        errors.append(f"① 露出 gap={gap}（0 でなければ均衡が壊れている。期待 m={m}）")
    if deg and max(deg.values()) != m:
        errors.append(f"① 出場回数が m={m} と不一致（実 {min(deg.values())}〜{max(deg.values())}）")

    # ② 全体連結
    comps = connected_components(ids, norm)
    if len(comps) != 1:
        errors.append(f"② 全体の連結成分={len(comps)}（1 でなければ BT が全項目を推定できない）")

    # ③ k 制約（評価者内）/ ④ 同一ペア 0（評価者内）
    max_occ = 0
    dup = 0
    for slot in range(n_slots):
        srows = [r for r in prod if r["plan_index"] == slot]
        occ: dict[str, int] = {}
        seen: set[tuple[str, str]] = set()
        for r in srows:
            for x in (r["item_left"], r["item_right"]):
                occ[x] = occ.get(x, 0) + 1
            key = tuple(sorted((r["item_left"], r["item_right"])))
            if key in seen:
                dup += 1
            seen.add(key)
        if occ:
            max_occ = max(max_occ, max(occ.values()))
    if max_occ > k:
        errors.append(f"③ 評価者内の同一 item 出現 {max_occ} > k={k}")
    if dup:
        errors.append(f"④ 同一評価者に同一ペアが {dup} 件（ハード制約違反, BR-U6-18）")

    # ⑤ 層間比率
    uniq = set(norm)
    cross = sum(1 for a, b in uniq if layers.get(a) != layers.get(b)) / len(uniq) if uniq else 0.0
    if cross < cross_target:
        errors.append(f"⑤ 層間比率 {cross:.3f} < {cross_target}")

    # ⑥ ★ブロック連結（BR-U6-20・(b) 推定の逐次更新の前提）
    per = n_slots // n_blocks
    block_comps: list[int] = []
    for b in range(n_blocks):
        lo = b * per
        hi = n_slots if b == n_blocks - 1 else (b + 1) * per
        be = [tuple(sorted((r["item_left"], r["item_right"])))
              for r in prod if lo <= r["plan_index"] < hi]
        c = len(connected_components(ids, be))
        block_comps.append(c)
        if c != 1:
            errors.append(
                f"⑥ ブロック{b + 1} の連結成分={c}（1 でなければブロック単体の暫定 BT が"
                "全項目を推定できない, BR-U6-20）"
            )

    # PU6-8 禁止辺の不在（ハード）
    eset = set(norm)
    forb = [f"{a}×{b}" for (a, b) in sorted(cons.forbidden_pairs) if (a, b) in eset]
    if forb:
        errors.append(f"PU6-8 禁止辺が {len(forb)} 本残存: {', '.join(forb)}")

    # 忌避（ソフト）— **失敗させない**（BR-U6-21）
    disc = [f"{a}×{b}" for (a, b) in sorted(cons.discouraged_pairs) if (a, b) in eset]

    # 濃縮の達成状況（レポート）
    enrich: dict[str, int] = {}
    for e in cons.enrichment:
        a = e["anchor"]
        got = sum(1 for c in e["counterparts"] if tuple(sorted((a, c))) in eset)
        enrich[a] = got
        if got < int(e.get("target", 0)):
            # 濃縮は目標であって**ハードではない**（レポートに残すが失敗にしない）
            pass

    # Likert 固定リスト（BR-U6-06）
    lt = cons.likert_targets
    if likert_expected is not None and len(lt) != likert_expected:
        errors.append(f"likert_targets が {len(lt)} 件（期待 {likert_expected} 件）")
    if len(set(lt)) != len(lt):
        errors.append("likert_targets に重複")
    missing = sorted(set(lt) - set(ids))
    if missing:
        errors.append(f"likert_targets がプールに不在: {', '.join(missing)}")

    return PlanVerification(
        ok=not errors, exposure_gap=gap, n_components=len(comps), max_occurrence=max_occ,
        duplicate_pairs=dup, cross_layer_ratio=cross, block_components=block_comps,
        forbidden_violations=forb, discouraged_violations=disc,
        enrichment_achieved=enrich, errors=errors,
    )


def render_report(v: PlanVerification, *, plan_set: str) -> str:
    """人間可読の検証レポート（`verification.md` としてコミットする）。"""
    lines = [f"# プラン検証レポート — `{plan_set}`", "",
             f"**結果**: {'✅ PASS' if v.ok else '❌ FAIL'}", "",
             "| 項目 | 値 | 判定 |", "|---|---|---|",
             f"| ① 露出 gap | {v.exposure_gap} | {'✅' if v.exposure_gap == 0 else '❌'} |",
             f"| ② 全体の連結成分 | {v.n_components} | {'✅' if v.n_components == 1 else '❌'} |",
             f"| ③ 評価者内の最大出現 | {v.max_occurrence} | — |",
             f"| ④ 同一ペア重複 | {v.duplicate_pairs} | {'✅' if v.duplicate_pairs == 0 else '❌'} |",
             f"| ⑤ 層間比率 | {v.cross_layer_ratio:.3f} | — |",
             f"| ⑥ ブロック連結成分 | {v.block_components} | "
             f"{'✅' if all(c == 1 for c in v.block_components) else '❌'} |",
             f"| PU6-8 禁止辺の残存 | {len(v.forbidden_violations)} | "
             f"{'✅' if not v.forbidden_violations else '❌'} |", ""]
    if v.enrichment_achieved:
        lines += ["## 濃縮の達成状況（目標・ハードではない）", ""]
        lines += [f"- `{a}`: {n} 本" for a, n in sorted(v.enrichment_achieved.items())] + [""]
    if v.discouraged_violations:
        lines += ["## 忌避ペアの残存（ソフト・失敗にはしない）", ""]
        lines += [f"- {x}" for x in v.discouraged_violations] + [""]
    if v.errors:
        lines += ["## エラー", ""] + [f"- {e}" for e in v.errors] + [""]
    return "\n".join(lines)
