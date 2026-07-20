"""LC-U6-05 — スロット内の順序付け（純関数, BR-U6-21 ④）。

**なぜ独立ステップなのか**: 内容制約④「**同一評価者内で指定グループを連続提示しない**」は
**辺集合ではなくペア列の順序**の制約であり、グラフ構成（LC-03）でも分割（LC-04）でも
表現できない。**分割後に 1 段必要**。

**練習ペアの扱い**（BR-U6-16）:
  - 練習素材は**開示セット**（本番プールと完全分離）＝**本番 38 件の初見性を保つ**。
  - **全評価者共通**で固定記載（`is_practice=1`）。
  - **★ペア列の先頭（`idx` の最小側）に置く**——既存 U2 の `derive_phase` が
    「練習 → 本番」の順で進むため。位置が未規定だと実装依存になる。

**出力順がそのまま `pair_index`** になり、実行時（`save_pair_sequence`）に再現される。
"""

from __future__ import annotations

import random


def _violations(seq: list[tuple[str, str]], groups: list[list[str]]) -> int:
    """隣接回避の違反数: 連続する 2 ペアが**同じ回避グループの item を跨いで**現れる回数。"""
    if not groups:
        return 0
    sets = [set(g) for g in groups]
    v = 0
    for i in range(len(seq) - 1):
        cur = set(seq[i])
        nxt = set(seq[i + 1])
        for g in sets:
            # 連続する 2 ペアが同一グループの item を（別々に）含むと「連続提示」とみなす
            if (cur & g) and (nxt & g):
                v += 1
                break
    return v


def order_slot(edges: list[tuple[str, str]], groups: list[list[str]], *, seed: int,
               max_steps: int = 4000) -> list[tuple[str, str]]:
    """1 スロット分の本番ペア列を並べ替える（隣接回避の違反を減らす）。

    **決定論**（`random.Random(seed)`）。**ソフト制約**ゆえ違反 0 に到達できなくても
    失敗させない（`verify` がレポートする）。
    """
    seq = list(edges)
    rng = random.Random(seed)
    rng.shuffle(seq)
    best = _violations(seq, groups)
    if best == 0 or not groups:
        return seq
    for _ in range(max_steps):
        i, j = rng.randrange(len(seq)), rng.randrange(len(seq))
        if i == j:
            continue
        seq[i], seq[j] = seq[j], seq[i]
        cur = _violations(seq, groups)
        if cur <= best:
            best = cur
            if best == 0:
                break
        else:
            seq[i], seq[j] = seq[j], seq[i]
    return seq


def build_slot_rows(slot_edges: list[list[tuple[str, str]]],
                    practice_pairs: list[tuple[str, str]],
                    groups: list[list[str]], *, seed: int) -> list[dict]:
    """全スロットのペア列を組み、プラン行（dict）にする。

    **練習ペアを先頭**に置き、続けて本番ペアを並べる。`idx` は 0 起点の通し番号
    （= 実行時の `pair_index`）。
    """
    rows: list[dict] = []
    for plan_index, edges in enumerate(slot_edges):
        ordered = order_slot(edges, groups, seed=seed + plan_index)
        idx = 0
        # ★練習が先頭（U2 の derive_phase が「練習 → 本番」の順で進むため）
        for a, b in practice_pairs:
            rows.append({"plan_index": plan_index, "idx": idx,
                         "item_left": a, "item_right": b, "is_practice": True})
            idx += 1
        for a, b in ordered:
            rows.append({"plan_index": plan_index, "idx": idx,
                         "item_left": a, "item_right": b, "is_practice": False})
            idx += 1
    return rows
