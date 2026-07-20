"""LC-U6-04 — J 辺の E スロット分割（純関数）。

**スロット = 評価者枠**。分割は**構成では保証されない**制約を担う（DP-U6-02）:
  ③ **k 制約**: 評価者内の同一 item 出現 ≤ k
  ⑥ **ブロック連結**: 各ブロック（前半/後半の 4 スロット）の辺和集合だけで連結成分 1

**⑥ が要る理由（BR-U6-20）**: **BR-U6-13 (b) 推定の逐次更新の前提**。ブロック1 単体で
暫定 BT を出すには**ブロック1 の比較グラフが連結**でなければならない（非連結だと最大
成分しか推定されず**全項目の暫定位置が出ない**）。実測では貪欲配分 30 試行でブロック
1・2 とも成分 1 だったが**構成上の保証ではない**（116 辺 ≫ 連結に必要な 37 辺と密なだけ）。
→ E・分割・構成法を変えると静かに壊れるため**明示的な検証項目**とする。

**スロット定員（分割指定）は呼び出し側が与える**（例 `[29,29,29,29,28,28,28,28]`）。
**総和 ≠ J は明示失敗**（U6-NFR-11 の失敗系）。
"""

from __future__ import annotations

import random


class PartitionError(ValueError):
    """分割不能（明示失敗させる）。"""


def split_sizes(n_pairs: int, n_slots: int) -> list[int]:
    """既定の分割定員を作る（余りを先頭スロットへ 1 ずつ配る）。

    例: J=228, E=8 → [29,29,29,29,28,28,28,28] / J=204, E=8 → [26,26,26,26,25,25,25,25]
    """
    q, r = divmod(n_pairs, n_slots)
    return [q + 1] * r + [q] * (n_slots - r)


def partition_edges(edges: list[tuple[str, str]], sizes: list[int], *, k: int,
                    seed: int, max_restarts: int = 200) -> list[list[tuple[str, str]]]:
    """辺を各スロットへ配分する（k 制約を満たすまで貪欲 + リスタート）。

    - **決定論**: `random.Random(seed)` のみ（同一 seed → 同一結果）。
    - **明示失敗**: 定員の総和 ≠ 辺数 / リスタート上限到達（U6-NFR-11）。
    """
    if sum(sizes) != len(edges):
        raise PartitionError(
            f"分割定員の総和 {sum(sizes)} が辺数 {len(edges)} と不一致"
            "（分割指定を引数化する場合の入力検証）"
        )

    rng = random.Random(seed)
    for attempt in range(max_restarts):
        pool = list(edges)
        rng.shuffle(pool)
        slots: list[list[tuple[str, str]]] = []
        ok = True
        for cap in sizes:
            cur: list[tuple[str, str]] = []
            occ: dict[str, int] = {}
            # k 制約を満たす辺を貪欲に拾う（残りは次スロットへ回す）。
            remaining: list[tuple[str, str]] = []
            for e in pool:
                if len(cur) >= cap:
                    remaining.append(e)
                    continue
                a, b = e
                if occ.get(a, 0) < k and occ.get(b, 0) < k:
                    cur.append(e)
                    occ[a] = occ.get(a, 0) + 1
                    occ[b] = occ.get(b, 0) + 1
                else:
                    remaining.append(e)
            if len(cur) < cap:
                ok = False
                break
            slots.append(cur)
            pool = remaining
        if ok and not pool:
            return slots
    raise PartitionError(
        f"k={k} を満たす分割が {max_restarts} 回のリスタートで得られませんでした"
        "（seed を進めて再試行してください）"
    )


def check_block_feasibility(n_items: int, n_pairs: int, n_slots: int,
                            n_blocks: int = 2) -> None:
    """**ブロック連結性（BR-U6-20）が原理的に達成可能か**を事前検査する（U6-NFR-11）。

    **n 頂点を連結するには最低 n−1 辺が必要**。ブロックあたりの辺数がこれを下回ると
    **どんな seed でもブロック連結にできない**——リトライは無駄であり、**明示失敗**して
    パラメータの誤りを伝えるべき。

    （PBT `test_pu6_7_block_connectivity` の反例 `n=10, m=4, E=3` で発覚。ブロック1 が
    1 スロット 7 辺しか持たず 10 頂点を連結できなかった。事前検査がないと「seed 運が
    悪い」と誤認して max_attempts 回リトライし、曖昧なメッセージで失敗する。）
    """
    if n_blocks < 1:
        raise PartitionError(f"ブロック数 {n_blocks} が不正")
    sizes = split_sizes(n_pairs, n_slots)
    per = n_slots // n_blocks
    for b in range(n_blocks):
        lo = b * per
        hi = n_slots if b == n_blocks - 1 else (b + 1) * per
        edges_in_block = sum(sizes[lo:hi])
        if edges_in_block < n_items - 1:
            raise PartitionError(
                f"ブロック{b + 1} の辺数 {edges_in_block} < n−1 = {n_items - 1}"
                "（n 頂点の連結には最低 n−1 辺が必要。**どの seed でもブロック連結に"
                "できない**ためリトライせず明示失敗する。E を増やすか J/n を見直すこと, "
                "BR-U6-20）"
            )


def blocks_of(slots: list[list[tuple[str, str]]], n_blocks: int = 2
              ) -> list[list[tuple[str, str]]]:
    """スロットをブロックへまとめる（既定は前半/後半の 2 ブロック）。

    ブロック連結性（BR-U6-20）の検証単位。E=8・2 ブロックなら 4 スロットずつ。
    """
    if n_blocks < 1 or n_blocks > len(slots):
        raise PartitionError(f"ブロック数 {n_blocks} が不正（スロット数 {len(slots)}）")
    per = len(slots) // n_blocks
    out: list[list[tuple[str, str]]] = []
    for b in range(n_blocks):
        start = b * per
        end = len(slots) if b == n_blocks - 1 else (b + 1) * per
        out.append([e for s in slots[start:end] for e in s])
    return out
