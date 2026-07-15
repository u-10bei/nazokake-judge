"""LC-U4b-02/03 — connected_components / restrict_to_component（純）。

観測ペアを辺とする無向グラフの連結成分を検出し（BR-U4b-02）、最大連結成分への制限を
**独立純関数**に切り出す（DP-U4b-02）。これにより PU4b-4（非連結→最大成分のみ）を
純関数合成（connected_components → restrict_to_component → fit_bt）で直接検証できる。

正則化は観測ペア限定（BR-U4b-03）ゆえグラフを人工的に完全連結化せず、非連結という
研究上重要な事実（コンポーネント間スコアは比較不能）を保存する。
"""

from __future__ import annotations

PairKey = tuple[str, str]


def connected_components(pair_counts: dict[PairKey, int]) -> list[list[str]]:
    """観測ペアグラフの連結成分を返す（各成分は item_id 昇順・全体も決定論的順序）。

    孤立 item（観測ペアに一度も現れない）は辺を持たないため成分に含まれない
    （呼び出し側で除外 item として扱う）。
    """
    adj: dict[str, set[str]] = {}
    for (a, b) in pair_counts:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    seen: set[str] = set()
    components: list[list[str]] = []
    for start in sorted(adj):                    # 決定論的な探索開始順
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
        components.append(sorted(comp))
    return components


def largest_component(components: list[list[str]]) -> list[str]:
    """最大連結成分を決定論的に選ぶ（サイズ最大、同数は item_id 列辞書順で最小）。"""
    if not components:
        return []
    return sorted(components, key=lambda c: (-len(c), c))[0]


def restrict_to_component(
    wins: dict[str, int],
    pair_counts: dict[PairKey, int],
    component: list[str],
) -> tuple[dict[str, int], dict[PairKey, int]]:
    """集計を指定成分へ制限する（推定対象の切り出し, DP-U4b-02）。

    成分は連結ゆえ、成分内 item の全対戦相手は同成分内にある（wins は総勝ち数と一致）。
    """
    cset = set(component)
    r_wins = {i: wins.get(i, 0) for i in component}
    r_pairs = {k: n for k, n in pair_counts.items() if k[0] in cset and k[1] in cset}
    return r_wins, r_pairs
