"""SessionService — start_or_resume / 現在状態の合成（US-P01/P08, LC-U2-02）。

サーバ権威（U2-NFR-09）: DB 実データから phase / next / progress を導出して SessionView を
合成する。新規開始は generate_pairs → save_pair_sequence → mark_token_in_progress（原子確定
DP-01 / BR-U2-04）。再開は DB 行から再構成（XC-02, blob 非永続, BR-U2-22）。

seed は**トークン由来の決定論シード**（U2 CG Q1=A, U1 FD Q4=B の生成方法改訂）:
`seed = int(SHA-256(token) 先頭 8 バイト)`。監査再現性が最大で RNG 状態不要。`sessions.seed`
への保存は継続（導出値と保存値の一致を監査で検証できる二重化）。
"""

from __future__ import annotations

import hashlib
import time

from backend.domain import generate_pairs, select_likert_targets
from backend.participant import view as vw
from backend.participant.phase import derive_phase, is_complete
from schema import AssignmentParams, Pair, Session, SessionView


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def seed_from_token(token: str) -> int:
    """トークン由来の決定論シード（Q1=A）。同一トークン → 同一ペア列・Likert 対象。

    **D1 bind 制約**: `sessions.seed` は D1(SQLite) に保存され、D1 の bind は JS の安全整数
    （2^53-1）を超える Python int を bigint として拒否する（D1_TYPE_ERROR）。よって SHA-256
    ダイジェストの**先頭 6 バイト（48bit）**を用いる（< 2^53、決定論性・監査再現性は不変。
    RNG 品質は 128-bit トークンのハッシュゆえ十分）。
    """
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:6], "big")


async def start_or_resume(repo, token: str, params: AssignmentParams) -> SessionView:
    """未使用ならセッションを確定して開始、進行中なら再開、完了なら完了 view。"""
    now = now_iso()
    session = await repo.get_session(token)
    if session is None:
        # 新規開始（unused）: ペア列を確定・原子保存し in_progress へ。
        exposure = await repo.read_exposure_counts(
            now_iso=now, inactive_threshold_hours=params.inactive_threshold_hours
        )
        # U5: 新規セッションは **現役のみ** から選ぶ（BR-U5-02a）。ペア列・練習ペア・Likert
        # ターゲットのすべてが廃止 item を含まなくなる（練習は generate_pairs の同一呼び出し
        # 由来ゆえ自動的に効く, BR-U5-02b）。
        pool = await repo.list_active_items()
        seed = seed_from_token(token)
        pairs = generate_pairs(pool, exposure, seed, params)
        # U5: Likert ターゲットも開始時に確定し、ペア列と**同じ batch で原子保存**する
        # （DP-U5-02。別経路にすると「ペア列は保存されたが Likert 未保存」の窓が生じる）。
        new_session = Session(
            token=token, phase="practice", seed=seed,
            exposure_snapshot=exposure, created_at=now,
            likert_targets=select_likert_targets(pool, seed, params),
        )
        await repo.save_pair_sequence(new_session, pairs)
        await repo.mark_token_in_progress(token, now)
    else:
        await repo.touch_token(token, now)

    return await build_view(repo, token, params)


async def get_likert_targets(repo, token: str, params: AssignmentParams) -> list[str]:
    """Likert ターゲットの**唯一の取得経路**（U5 / LC-U5-03 / BR-U5-04）。

    保存値があればそれを返し、なければ **`list_items()`（全件）から導出**する
    （＝U5 以前に開始した進行中セッションのフォールバック。従来挙動を完全再現し
    「新規のみ反映」を守る）。

    🔴 **3 箇所すべてが本関数を経由すること**（`build_view`=表示 / `check_complete`=完了判定 /
    `survey.submit_likert`=検証）。一部だけ保存値に切り替えると表示=保存値・検証=導出値の
    ずれが生じ、**参加者に表示されたターゲットを送信すると拒否される**。
    """
    session = await repo.get_session(token)
    if session is not None and session.likert_targets is not None:
        return session.likert_targets
    # 旧セッション（likert_targets IS NULL）: 全件から導出＝従来挙動を完全再現。
    return select_likert_targets(await repo.list_items(), seed_from_token(token), params)


async def build_view(repo, token: str, params: AssignmentParams) -> SessionView:
    """DB 実データから SessionView を合成する（サーバ権威・再同期の単一経路）。"""
    tok = await repo.get_token(token)
    status = tok.status if tok is not None else "unused"

    pairs = await repo.get_pairs(token)
    answered = await repo.answered_pair_ids(token)
    # U5: bodies は **全件**（`list_items()`）で解決する（BR-U5-02a）。進行中セッションの
    # 既存ペア列が廃止 item を含みうるため、ここを active に絞ると画面が壊れる。
    pool = await repo.list_items()
    bodies = {it.item_id: it.body for it in pool}
    seed = seed_from_token(token)
    likert_targets = await get_likert_targets(repo, token, params)
    answered_likert = await repo.answered_likert_refs(token)
    survey_exists = await repo.survey_exists(token)

    phase = derive_phase(pairs, answered, likert_targets, answered_likert,
                         survey_exists, status)

    practice = [p for p in pairs if p.is_practice]
    production = [p for p in pairs if not p.is_practice]

    next_pair = _next_pair_for_phase(phase.value, practice, production, answered)
    next_likert_ref = _next_likert(phase.value, likert_targets, answered_likert)

    return vw.session_view(
        status=status,
        phase=phase.value,
        next_pair=next_pair,
        next_likert_ref=next_likert_ref,
        prod_done=sum(1 for p in production if p.pair_id in answered),
        prod_total=len(production),
        practice_done=sum(1 for p in practice if p.pair_id in answered),
        practice_total=len(practice),
        bodies=bodies,
    )


def _next_pair_for_phase(phase, practice, production, answered) -> Pair | None:
    """現在フェーズで次に提示すべきペア（未回答の先頭 index）。"""
    if phase == "practice":
        pool = practice
    elif phase == "judging":
        pool = production
    else:
        return None
    for p in sorted(pool, key=lambda x: x.index):
        if p.pair_id not in answered:
            return p
    return None


def _next_likert(phase, likert_targets, answered_likert) -> str | None:
    if phase != "likert":
        return None
    for ref in likert_targets:
        if ref not in answered_likert:
            return ref
    return None


# 完了順序のサーバ確認（BR-U2-24）を survey サービスから使う。
async def check_complete(repo, token: str, params: AssignmentParams) -> bool:
    pairs = await repo.get_pairs(token)
    answered = await repo.answered_pair_ids(token)
    likert_targets = await get_likert_targets(repo, token, params)  # U5: 単一アクセサ経由
    answered_likert = await repo.answered_likert_refs(token)
    survey_exists = await repo.survey_exists(token)
    return is_complete(pairs, answered, likert_targets, answered_likert, survey_exists)
