"""LC-U4b-01 — aggregate（純・正準集計の 3 点セットの起点, DP-U4b-01）。

正準集計を **1 箇所の純関数に集約**する（正準化の通過必須点）。呼び出し側の生 dict
集計を塞ぐ（Code Gen での劣化経路を構造で防ぐ）。

**α 適用位置の不変条件（Infra Design §11 / Code Gen Q2）**: 本関数が返す wins/pair_counts は
**生の観測カウント**。擬似データ α は fit_bt 内部でのみ適用する。BTResult.matches/wins は
この生カウントに基づく（BR-U4b-08・PU4b-6 の U3 winrate 突合の成立条件）。
"""

from __future__ import annotations

# 正準ペアキー: 無順序ペアの tuple（item_id 昇順）。
PairKey = tuple[str, str]


def aggregate(judgments) -> tuple[dict[str, int], dict[PairKey, int]]:
    """判定列を (wins, pair_counts) に正準集計する。

    - judgments: `item_left` / `item_right` / `choice`('A'|'B') 属性を持つオブジェクト列
      （ExportJudgment）。
    - wins[item_id]: その item が勝った回数（**向き非依存・item 単位**, choice=A→item_left 勝ち）。
    - pair_counts[(i,j)]: 無順序ペア (i,j)=`sorted((i,j))` の対戦回数 n_ij。

    ペアキーを `sorted((i,j))` に正規化してから数えることで `(i,j)`/`(j,i)` の n_ij 分裂と
    擬似データ α の二重配分を排除する（DP-U4b-01・BR-U4b-01/03）。
    """
    wins: dict[str, int] = {}
    pair_counts: dict[PairKey, int] = {}
    for j in judgments:
        left = j.item_left
        right = j.item_right
        # 参加 item は勝敗 0 でも wins に登録（fit_bt / matches の対象に含める）。
        wins.setdefault(left, 0)
        wins.setdefault(right, 0)
        key: PairKey = (left, right) if left <= right else (right, left)
        pair_counts[key] = pair_counts.get(key, 0) + 1
        winner = left if j.choice == "A" else right
        wins[winner] = wins.get(winner, 0) + 1
    return wins, pair_counts


def match_counts(pair_counts: dict[PairKey, int]) -> dict[str, int]:
    """各 item の出場数（matches）を pair_counts（生カウント）から求める（BR-U4b-08）。"""
    matches: dict[str, int] = {}
    for (a, b), n in pair_counts.items():
        matches[a] = matches.get(a, 0) + n
        matches[b] = matches.get(b, 0) + n
    return matches
