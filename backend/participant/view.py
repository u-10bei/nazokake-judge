"""ViewSerializer — domain→view 写像の一点集約（DP-U2-02 / 出自秘匿）。

`Item`/`Session`/`Pair` を**参加者ビュー型**へ写像する唯一の場所。ここで `layer`/`body_ref`/
`seed`/`exposure_snapshot` を構造的に落とす（ビュー型がそもそも持たない, U2-NFR-06）。純粋。

`bodies` は `item_id -> body` の写像（`Repository.list_items` 由来）。参加者に渡すのは本文のみ。
"""

from __future__ import annotations

from schema import (
    ItemView,
    LikertTargetView,
    Pair,
    PairView,
    Progress,
    SessionView,
    SubmitResult,
)


def item_view(item_id: str, bodies: dict[str, str]) -> ItemView:
    return ItemView(item_id=item_id, body=bodies.get(item_id, ""))


def pair_view(pair: Pair, bodies: dict[str, str]) -> PairView:
    """Pair → PairView（本文込み・出自なし）。left=A, right=B（BR-07）。"""
    return PairView(
        pair_id=pair.pair_id,
        index=pair.index,
        left=item_view(pair.item_left, bodies),
        right=item_view(pair.item_right, bodies),
        is_practice=pair.is_practice,
    )


def likert_target_view(target_ref: str, bodies: dict[str, str]) -> LikertTargetView:
    return LikertTargetView(target_ref=target_ref, body=bodies.get(target_ref, ""))


def session_view(
    *,
    status: str,
    phase: str,
    next_pair: Pair | None,
    next_likert_ref: str | None,
    prod_done: int,
    prod_total: int,
    practice_done: int,
    practice_total: int,
    bodies: dict[str, str],
) -> SessionView:
    """SessionView を合成（サーバ権威・出自秘匿, U2-NFR-06/09）。"""
    return SessionView(
        status=status,
        phase=phase,
        next_pair=pair_view(next_pair, bodies) if next_pair is not None else None,
        next_likert=(
            likert_target_view(next_likert_ref, bodies)
            if next_likert_ref is not None else None
        ),
        progress=Progress(done=prod_done, total=prod_total),
        practice=Progress(done=practice_done, total=practice_total),
    )


def submit_result(
    *,
    saved: bool,
    duplicate: bool,
    choice: str,
    next_pair: Pair | None,
    phase: str,
    prod_done: int,
    prod_total: int,
    bodies: dict[str, str],
) -> SubmitResult:
    """SubmitResult を合成（冪等観測 + 再同期, Q6/DP-U2-07）。"""
    return SubmitResult(
        saved=saved,
        duplicate=duplicate,
        choice=choice,
        next_pair=pair_view(next_pair, bodies) if next_pair is not None else None,
        phase=phase,
        progress=Progress(done=prod_done, total=prod_total),
    )
