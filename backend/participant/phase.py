"""derive_phase — セッションの現在フェーズを DB カウントから導出する純粋述語（U2）。

サーバ状態は 5 状態（practice / judging / likert / survey / done）。`instruction` は
サーバ状態から除外し、UI が「phase=practice かつ練習判定 0 件」で教示を前置する
（BR-U2-01/02）。線形性（BR-U2-03）: 先に来るフェーズに未完があればそこを現行とする。

**純粋**（副作用なし・DB カウントは引数で受領, DP-U2-05）。PU2-3（単調性）を PBT で検証。
"""

from __future__ import annotations

from schema import Pair, SessionPhase


def derive_phase(
    pairs: list[Pair],
    answered_pair_ids: set[str],
    likert_targets: list[str],
    answered_likert_refs: set[str],
    survey_exists: bool,
    token_status: str,
) -> SessionPhase:
    """現在フェーズを導出する（BR-U2-01/03）。"""
    if token_status == "completed":
        return SessionPhase.DONE

    practice = [p for p in pairs if p.is_practice]
    production = [p for p in pairs if not p.is_practice]

    if any(p.pair_id not in answered_pair_ids for p in practice):
        return SessionPhase.PRACTICE
    if any(p.pair_id not in answered_pair_ids for p in production):
        return SessionPhase.JUDGING
    if any(ref not in answered_likert_refs for ref in likert_targets):
        return SessionPhase.LIKERT
    if not survey_exists:
        return SessionPhase.SURVEY
    return SessionPhase.DONE


def is_complete(
    pairs: list[Pair],
    answered_pair_ids: set[str],
    likert_targets: list[str],
    answered_likert_refs: set[str],
    survey_exists: bool,
) -> bool:
    """完了順序のサーバ確認（BR-U2-24）: 本番判定全件 ∧ Likert 全対象 ∧ survey 行あり。

    練習は完了条件に含めない（本番のみ, BR-U2-13）。token_status 非依存の純粋判定。
    """
    production = [p for p in pairs if not p.is_practice]
    all_prod = all(p.pair_id in answered_pair_ids for p in production)
    all_likert = all(ref in answered_likert_refs for ref in likert_targets)
    return all_prod and all_likert and survey_exists
