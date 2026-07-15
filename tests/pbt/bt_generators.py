"""U4b BT 集計の PBT ジェネレータ（U4b-NFR-07）。

連結/非連結グラフを両方生成する（「非連結を意図的に含む」が PU4b-4 の反例探索の要）。
左右反転（item_left/item_right 交換時 choice も A↔B 反転）+ シャッフルの同値変換も提供し、
PU4b-2 の決定論+置換不変性を 3 点まとめて反例探索する（DP-U4b-01）。
"""

from __future__ import annotations

from hypothesis import strategies as st

from schema import ExportItem, ExportJudgment

LAYERS = ["pro", "ai", "edit", "rule"]


def _item(k: int) -> ExportItem:
    return ExportItem(item_id=f"i{k:02d}", layer=LAYERS[k % 4])


def _judgment(idx: int, left: str, right: str, choice: str) -> ExportJudgment:
    return ExportJudgment(
        token=f"t{idx % 7}",
        pair_id=f"p{idx:04d}",
        pair_index=idx,
        item_left=left,
        item_right=right,
        choice=choice,
        created_at="2026-07-15T00:00:00Z",
    )


@st.composite
def ranked_scenario(draw):
    """完全総当たり（各ペア 1 回）で上位ランクが常に勝つ判定列（PU4b-1 単調性の検証用）。

    **完全総当たり＝全 item の次数が n−1 で均一**ゆえ観測ペア限定正則化 α が item 間で
    対称に効き、raw wins が rank に厳密単調（rank r の勝ち数 = n−1−r）。よって正則化 ON でも
    θ は rank に単調（BR-U4b-01「正則化 ON でも保存」の堅牢な検証条件）。

    注意: 不規則グラフ（次数バラバラ）では α が疎 item を非対称に縮め隣接ペアの順位が
    入れ替わりうる（BR-U4b-01「疎な新作ほど相対的に強く縮む」）＝任意ネットワークでの
    厳密ペア単調性は正則化 ON では保証されないため、ここでは次数対称な完全総当たりに限定する。

    returns: (items, judgments, rank_index) — rank_index[item_id] は 0 が最上位。
    """
    n = draw(st.integers(min_value=3, max_value=7))
    items = [_item(k) for k in range(n)]
    ids = [it.item_id for it in items]
    order = draw(st.permutations(ids))                  # 上位（index 小）が強い
    rank_index = {item_id: r for r, item_id in enumerate(order)}

    judgments: list[ExportJudgment] = []
    idx = 0
    for a in range(n):
        for b in range(a + 1, n):
            x, y = ids[a], ids[b]
            hi = x if rank_index[x] < rank_index[y] else y
            lo = y if hi == x else x
            # 左右の向きはランダム（choice を勝者に合わせる＝左右反転耐性も兼ねる）。
            if draw(st.booleans()):
                judgments.append(_judgment(idx, hi, lo, "A"))
            else:
                judgments.append(_judgment(idx, lo, hi, "B"))
            idx += 1
    return items, judgments, rank_index


@st.composite
def free_scenario(draw):
    """勝敗が自由な判定列（連結性は不問）。決定論・置換不変性・Σθ=0 の検証用。"""
    n = draw(st.integers(min_value=2, max_value=7))
    items = [_item(k) for k in range(n)]
    ids = [it.item_id for it in items]
    m = draw(st.integers(min_value=1, max_value=20))
    judgments: list[ExportJudgment] = []
    for idx in range(m):
        a = draw(st.sampled_from(ids))
        b = draw(st.sampled_from([x for x in ids if x != a]))
        choice = draw(st.sampled_from(["A", "B"]))
        judgments.append(_judgment(idx, a, b, choice))
    return items, judgments


@st.composite
def disconnected_scenario(draw):
    """2 つの独立クリークを持つ非連結シナリオ（PU4b-4 の識別可能性検証用）。"""
    n1 = draw(st.integers(min_value=2, max_value=4))
    n2 = draw(st.integers(min_value=2, max_value=4))
    items = [_item(k) for k in range(n1 + n2)]
    group1 = [it.item_id for it in items[:n1]]
    group2 = [it.item_id for it in items[n1:]]

    judgments: list[ExportJudgment] = []
    idx = 0
    for group in (group1, group2):
        # 各グループ内で連結になるよう総当たり 1 本ずつ。
        for a in range(len(group)):
            for b in range(a + 1, len(group)):
                choice = draw(st.sampled_from(["A", "B"]))
                judgments.append(_judgment(idx, group[a], group[b], choice))
                idx += 1
    return items, judgments, group1, group2


def flip_and_shuffle(draw, judgments):
    """同値変換: 各判定を確率的に左右反転（choice も A↔B 反転）し、順序をシャッフルする。

    BT の集計は無順序ペア・item 単位勝敗ゆえ、この変換で BTResult は不変であるべき。
    """
    transformed = []
    for j in judgments:
        if draw(st.booleans()):
            new_choice = "B" if j.choice == "A" else "A"
            transformed.append(ExportJudgment(
                token=j.token, pair_id=j.pair_id, pair_index=j.pair_index,
                item_left=j.item_right, item_right=j.item_left,
                choice=new_choice, created_at=j.created_at,
            ))
        else:
            transformed.append(j)
    return draw(st.permutations(transformed))
