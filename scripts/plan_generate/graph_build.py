"""LC-U6-03 — m-正則巡回グラフの構成（純関数, DP-U6-02）。

**構成で保証されるもの**（検証は保険であって主たる根拠ではない）:
  ① **露出 gap = 0**: `C_n(1..m/2)` は**全頂点が次数 m**（距離 1..m/2 が各 2 本ずつ）。
     → 全 item がちょうど m 回出場する。
  ② **全体連結**: **距離 1 の辺が n 頂点の輪を成す**ため必ず連結（成分 1）。
  ④ **同一ペア 0**: 辺を**集合として**構成するため相異なる。

**なぜ構成で押さえるのか**（DP-U6-02）: 検証だけに頼ると「**反例は出たが直し方が
分からない**」状態になる。①②④は構成的に保証できるので、探索・検証の対象は
⑤層間比率・③k 制約・⑥ブロック連結・内容制約に絞れる。

**前提**: `m` が偶数で `m < n`（`constraints.validate_inputs` が事前に検証する）。
"""

from __future__ import annotations


def build_regular_edges(order: list[str], m: int) -> list[tuple[str, str]]:
    """円周配置 `order` から `C_n(1..m/2)` の辺集合を構成する。

    returns: `(item_left, item_right)` の正準タプル列（`sorted` 済み・重複なし・決定論順）。
    """
    n = len(order)
    if m % 2 != 0:
        raise ValueError(f"m={m} が奇数（巡回グラフでは構成できない）")
    if m >= n:
        raise ValueError(f"m={m} が n={n} 以上（構成不能）")

    d = m // 2
    edges: set[tuple[str, str]] = set()
    for k in range(1, d + 1):
        for i in range(n):
            a, b = order[i], order[(i + k) % n]
            edges.add((a, b) if a <= b else (b, a))
    # 決定論的な順序で返す（同一入力 → 同一出力, BR-U6-11）。
    return sorted(edges)


def degree_of(edges: list[tuple[str, str]], ids: list[str]) -> dict[str, int]:
    """各 item の次数（= 出場回数 m）。gap=0 の検証に使う。"""
    deg = {i: 0 for i in ids}
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    return deg


def connected_components(ids: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """辺集合の連結成分（item_id 昇順・決定論）。全体/ブロックの両方で使う。"""
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    seen: set[str] = set()
    out: list[list[str]] = []
    for start in sorted(adj):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp: list[str] = []
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in sorted(adj[u]):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        out.append(sorted(comp))
    return out
