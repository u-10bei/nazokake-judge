"""ResponseService — submit_judgment（US-P03, LC-U2-03）。

サーバが `pair_id` の**トークン帰属**と **is_practice** を保存済み pairs 行から判定
（クライアント申告不使用, H-3 / BR-U2-11）。冪等は `insert_judgment`（初回不変, DP-02）。
"""

from __future__ import annotations

from backend.participant import session as sess
from backend.participant.errors import ParticipantError
from schema import AssignmentParams, SubmitResult


async def submit_judgment(
    repo, token: str, pair_id: str, choice: str, params: AssignmentParams
) -> SubmitResult:
    """判定を冪等保存し、更新後の再同期情報を載せた SubmitResult を返す。"""
    if choice not in ("A", "B"):
        raise ParticipantError("choice は A か B（BR-U2-12）")

    pairs = await repo.get_pairs(token)
    target = next((p for p in pairs if p.pair_id == pair_id), None)
    if target is None:
        # 他トークン/存在しない pair_id は拒否（BR-U2-11）。
        raise ParticipantError("不正な pair_id（帰属なし, BR-U2-11）")

    answered_before = await repo.answered_pair_ids(token)
    duplicate = pair_id in answered_before

    now = sess.now_iso()
    kept = await repo.insert_judgment(token, pair_id, choice, now)  # 冪等・既存 choice 返却
    await repo.touch_token(token, now)

    # 更新後の状態を単一経路（build_view）で再導出し、SubmitResult に写す（DP-U2-07）。
    view = await sess.build_view(repo, token, params)
    return SubmitResult(
        saved=(not duplicate),
        duplicate=duplicate,
        choice=kept,
        next_pair=view.next_pair,
        phase=view.phase,
        progress=view.progress,
    )
