"""SurveyService — submit_likert / submit_survey（US-P05/P06/P07, LC-U2-04）。

Likert は `(token,target_ref)` 初回不変（DP-U2-06 / BR-U2-17）。Survey は PK=token upsert
（BR-U2-21）+ **完了順序のサーバ確認**（本番判定全件 ∧ Likert 全対象 ∧ survey 行あり）で
`mark_token_completed`（BR-U2-24 / U2-NFR-11）。返り値は更新後 SessionView（単一再同期経路）。
"""

from __future__ import annotations

from backend.domain import select_likert_targets
from backend.participant import session as sess
from backend.participant.errors import ParticipantError
from schema import AssignmentParams, SessionView


async def submit_likert(
    repo, token: str, target_ref: str, rating: int, params: AssignmentParams
) -> SessionView:
    """Likert 評定を初回不変で保存し、更新後 SessionView を返す。"""
    if not (1 <= rating <= 7):
        raise ParticipantError("rating は 1〜7（BR-U2-18）")

    pool = await repo.list_items()
    targets = select_likert_targets(pool, sess.seed_from_token(token), params)
    if target_ref not in targets:
        raise ParticipantError("target_ref は当該セッションの Likert 対象外（BR-U2-18）")

    now = sess.now_iso()
    await repo.insert_likert(token, target_ref, rating, now)  # 初回不変
    await repo.touch_token(token, now)
    return await sess.build_view(repo, token, params)


async def submit_survey(
    repo, token: str, answers: dict, params: AssignmentParams
) -> SessionView:
    """事後アンケートを upsert し、全揃い確認後に完了遷移して SessionView を返す。"""
    if not isinstance(answers, dict):
        raise ParticipantError("answers はオブジェクト（BR-U2-20）")

    now = sess.now_iso()
    await repo.upsert_survey(token, answers, now)
    await repo.touch_token(token, now)

    # 完了順序のサーバ確認（BR-U2-24）: 揃っていれば in_progress→completed。
    if await sess.check_complete(repo, token, params):
        await repo.mark_token_completed(token, now)

    return await sess.build_view(repo, token, params)
