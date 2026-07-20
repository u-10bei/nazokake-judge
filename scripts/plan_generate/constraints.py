"""LC-U6-01 — 研究側入力の読込・検証（純関数, BR-U6-21/22）。

**器と中身の分離**: **制約の中身は研究側（タスク5）の成果物、器は U6**。制約ファイルを
CLI 入力に取ることで、研究側の更新が**コード変更なしに反映**される。

**★入力は「三つ組」でセット単位**（BR-U6-21）: **（プール・期待組成・制約ファイル）**。
制約ファイルも成立版とフォールバック版で別物であり流用できない:
  (i)  pivot 衝突照合はフォールバック版では n=34 で独自に再走（46 音表は流用不可）
  (ii) N8 濃縮制約はフォールバック版に存在しない
  (iii) N 系の隣接回避制約も消滅
→ `plan_set` をファイルに内包させ、**期待組成の `plan_set` と一致しなければ明示失敗**
  （**成立版の制約ファイルをフォールバック版に誤適用する事故を防ぐ**）。
"""

from __future__ import annotations

import json

from schema import POOL_LAYERS, Item

# 制約ファイル / 期待組成ファイルで許可するキー（未知キーは拒否）。
# ★未知キーを拒否する理由: typo で制約が**黙って無効化**されるのを防ぐ
#   （例: "forbidden_pair" と書いても静かに無視されると禁止辺が効かないまま生成される）。
_CONSTRAINT_KEYS = {
    "plan_set", "likert_targets", "forbidden_pairs", "discouraged_pairs",
    "enrichment", "avoid_adjacent_groups",
}
_COMPOSITION_KEYS = {"plan_set", "n_items", "n_slots", "n_pairs", "m_per_item", "layers"}


class ConstraintError(ValueError):
    """研究側入力の不正（明示失敗させる）。"""


class Constraints:
    """検証済みの制約セット（`plan_set` 単位）。"""

    __slots__ = ("plan_set", "likert_targets", "forbidden_pairs",
                 "discouraged_pairs", "enrichment", "avoid_adjacent_groups")

    def __init__(self, *, plan_set, likert_targets, forbidden_pairs,
                 discouraged_pairs, enrichment, avoid_adjacent_groups):
        self.plan_set = plan_set
        self.likert_targets = likert_targets              # list[str]（★ちょうど 10 件想定）
        self.forbidden_pairs = forbidden_pairs            # set[tuple[str, str]]（ハード）
        self.discouraged_pairs = discouraged_pairs        # set[tuple[str, str]]（ソフト）
        self.enrichment = enrichment                      # list[{anchor, counterparts, target}]
        self.avoid_adjacent_groups = avoid_adjacent_groups  # list[list[str]]（提示順の制約）


class Composition:
    """期待組成（BR-U6-22）。`plan_generate` で実プールと突き合わせる。"""

    __slots__ = ("plan_set", "n_items", "n_slots", "n_pairs", "m_per_item", "layers")

    def __init__(self, *, plan_set, n_items, n_slots, n_pairs, m_per_item, layers):
        self.plan_set = plan_set
        self.n_items = n_items
        self.n_slots = n_slots            # E
        self.n_pairs = n_pairs            # J（本番のみ）
        self.m_per_item = m_per_item      # m
        self.layers = layers              # {layer_value: count}


def _norm_pair(a: str, b: str) -> tuple[str, str]:
    """無順序ペアを正準化（`sorted` の tuple）。禁止/忌避の照合を向き非依存にする。"""
    return (a, b) if a <= b else (b, a)


def _reject_unknown(d: dict, allowed: set[str], what: str) -> None:
    unknown = sorted(set(d) - allowed)
    if unknown:
        raise ConstraintError(
            f"{what} に未知のキー: {', '.join(unknown)}"
            f"（typo による制約の黙殺を防ぐため未知キーは拒否する。許可: {', '.join(sorted(allowed))}）"
        )


def load_constraints(path: str) -> Constraints:
    """制約ファイル（JSON）を読み検証する。未知キー・型不正は明示失敗。"""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ConstraintError("制約ファイルは JSON オブジェクトである必要があります")
    _reject_unknown(raw, _CONSTRAINT_KEYS, "制約ファイル")

    plan_set = raw.get("plan_set")
    if not isinstance(plan_set, str) or not plan_set:
        raise ConstraintError("制約ファイルに plan_set（非空文字列）が必要です")

    likert = raw.get("likert_targets") or []
    if not isinstance(likert, list) or not all(isinstance(x, str) for x in likert):
        raise ConstraintError("likert_targets は item_id の配列である必要があります")

    def _pairs(key: str) -> set[tuple[str, str]]:
        out: set[tuple[str, str]] = set()
        for p in raw.get(key) or []:
            if not (isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p)):
                raise ConstraintError(f"{key} の要素は [item_id, item_id] である必要があります")
            if p[0] == p[1]:
                raise ConstraintError(f"{key} に自己ペア: {p[0]}")
            out.add(_norm_pair(p[0], p[1]))
        return out

    enrichment = []
    for e in raw.get("enrichment") or []:
        if not isinstance(e, dict) or set(e) - {"anchor", "counterparts", "target"}:
            raise ConstraintError("enrichment の要素は {anchor, counterparts, target} です")
        enrichment.append({
            "anchor": e["anchor"],
            "counterparts": list(e.get("counterparts") or []),
            "target": int(e.get("target", 0)),
        })

    groups = []
    for g in raw.get("avoid_adjacent_groups") or []:
        if not (isinstance(g, list) and all(isinstance(x, str) for x in g)):
            raise ConstraintError("avoid_adjacent_groups の要素は item_id の配列です")
        groups.append(list(g))

    return Constraints(
        plan_set=plan_set, likert_targets=list(likert),
        forbidden_pairs=_pairs("forbidden_pairs"),
        discouraged_pairs=_pairs("discouraged_pairs"),
        enrichment=enrichment, avoid_adjacent_groups=groups,
    )


def load_composition(path: str) -> Composition:
    """期待組成（JSON）を読み検証する（BR-U6-22）。"""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ConstraintError("期待組成は JSON オブジェクトである必要があります")
    _reject_unknown(raw, _COMPOSITION_KEYS, "期待組成")
    for k in ("plan_set", "n_items", "n_slots", "n_pairs", "m_per_item", "layers"):
        if k not in raw:
            raise ConstraintError(f"期待組成に {k} が必要です")
    layers = raw["layers"]
    if not isinstance(layers, dict) or not all(isinstance(v, int) for v in layers.values()):
        raise ConstraintError("layers は {layer: 件数} の写像である必要があります")
    return Composition(
        plan_set=raw["plan_set"], n_items=int(raw["n_items"]), n_slots=int(raw["n_slots"]),
        n_pairs=int(raw["n_pairs"]), m_per_item=int(raw["m_per_item"]), layers=dict(layers),
    )


def validate_inputs(pool: list[Item], comp: Composition, cons: Constraints) -> None:
    """三つ組の整合を検証する（不一致は**明示失敗**, BR-U6-21/22）。

    検証項目:
      ① `plan_set` が制約ファイルと期待組成で一致（**セット取り違えの防止**）
      ② 実プールが期待組成（総数・層別件数）と一致（**anchor 投入忘れ等の検出**）
      ③ `J = n·m/2` の整合（正則グラフが構成可能）
      ④ 制約が参照する item_id がすべてプール内に実在
      ⑤ `likert_targets` がちょうど `n_pairs` 相当ではなく**指定件数**・重複なし・プール内
    """
    # ① セット取り違えの防止（成立版の制約をフォールバック版に誤適用する事故）
    if cons.plan_set != comp.plan_set:
        raise ConstraintError(
            f"plan_set 不一致: 制約ファイル={cons.plan_set} / 期待組成={comp.plan_set}"
            "（セット別の三つ組ゆえ流用不可。取り違えを防ぐため明示失敗する）"
        )

    # ② 期待組成の突合（★anchor を REQUIRED_LAYERS から外した裏返しの手当て, BR-U6-22）
    in_pool = [it for it in pool if it.layer in POOL_LAYERS]
    if len(in_pool) != comp.n_items:
        raise ConstraintError(
            f"プール総数不一致: 実 {len(in_pool)} / 期待 {comp.n_items}"
            "（POOL_LAYERS 該当分で比較。anchor の投入忘れ等はここで検出する）"
        )
    actual: dict[str, int] = {}
    for it in in_pool:
        actual[it.layer.value] = actual.get(it.layer.value, 0) + 1
    if actual != comp.layers:
        raise ConstraintError(f"層別件数不一致: 実 {actual} / 期待 {comp.layers}")

    # ③ 正則グラフの構成可能性
    if comp.n_items * comp.m_per_item != comp.n_pairs * 2:
        raise ConstraintError(
            f"J = n·m/2 が不整合: n={comp.n_items} m={comp.m_per_item} "
            f"→ 期待 J={comp.n_items * comp.m_per_item // 2} だが n_pairs={comp.n_pairs}"
        )
    if comp.m_per_item % 2 != 0:
        raise ConstraintError(
            f"m={comp.m_per_item} が奇数（巡回グラフ C_n(1..m/2) で構成できない）"
        )
    if comp.m_per_item >= comp.n_items:
        raise ConstraintError(f"m={comp.m_per_item} が n={comp.n_items} 以上（構成不能）")

    # ④ 制約が参照する item の実在
    ids = {it.item_id for it in in_pool}
    referenced: set[str] = set()
    for a, b in cons.forbidden_pairs | cons.discouraged_pairs:
        referenced |= {a, b}
    for e in cons.enrichment:
        referenced.add(e["anchor"]); referenced |= set(e["counterparts"])
    for g in cons.avoid_adjacent_groups:
        referenced |= set(g)
    missing = sorted(referenced - ids)
    if missing:
        raise ConstraintError(f"制約が参照する item がプールに不在: {', '.join(missing)}")

    # ⑤ Likert 固定リスト（BR-U6-06 全固定運用の前提）
    lt = cons.likert_targets
    if len(set(lt)) != len(lt):
        raise ConstraintError("likert_targets に重複があります")
    missing_lt = sorted(set(lt) - ids)
    if missing_lt:
        raise ConstraintError(f"likert_targets がプールに不在: {', '.join(missing_lt)}")
