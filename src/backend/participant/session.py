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
        seed = seed_from_token(token)
        # ---- U6（LC-U6-10・★置換点）: 割当を「実行時の抽選」から「設計時の固定プラン」へ ----
        # トークン自身に束縛された (plan_set, plan_index) を読む（DP-U6-06）。
        # 「その時点の有効セット」を参照しないので、発行 → セッション開始の間に activate が
        # 切り替わってもトークンの意味が変わらない。
        plan = await repo.get_token_plan(token)

        if plan is None:
            # フォールバック（U6-NFR-14）: U6 以前のトークン / ドライラン用の即席トークン。
            # ★dev 専用。n=38 プール + 5 層値環境での露出均衡・層間比率は**保証外**
            #   （較正 p=3/α=0.7/S=30 は n=95 由来）。本実験データには使わない。
            exposure = await repo.read_exposure_counts(
                now_iso=now, inactive_threshold_hours=params.inactive_threshold_hours
            )
            # U5: 新規セッションは **現役のみ** から選ぶ（BR-U5-02a）。
            pool = await repo.list_active_items()
            pairs = generate_pairs(pool, exposure, seed, params)
            likert_targets = select_likert_targets(pool, seed, params)
        else:
            # プラン経路: **実行時に抽選しない**。ペア列（練習含む・先頭が練習）を引くだけ。
            plan_set, plan_index = plan
            exposure = {}          # 事前生成では露出は設計時に確定済み（導出不要）
            pairs = await repo.get_plan_pairs(plan_set, plan_index)
            # ★補充トークンの引き継ぎ（BR-U6-15）を**一様な規則**で表現する:
            #   「そのスロットで**まだ回答されていない本番ペア**だけを配る」。
            #   - 初回トークン: 回答済みゼロ → 全量（特別扱い不要）
            #   - 補充トークン: 脱落者の未回答分のみ → **m=12 が保たれる**
            #     （スロット全体をやり直すと既回答分が二重判定され露出 gap≠0 になる）
            #   ★**練習ペアは常に全量再提示**する——補充者は**別人**であり、読み返しテストの
            #     習得なしに本番を判定させてはならない。練習は出力段で除外される（is_practice=1）
            #     ため**二重カウントの害はゼロ**。
            answered_on_slot = await repo.answered_pair_ids_for_slot(plan_set, plan_index)
            pairs = [p for p in pairs
                     if p.is_practice or p.pair_id not in answered_on_slot]
            # ★Likert 固定リストの配線（BR-U6-06 / FD Q2=D）。
            #   これが無いと `AssignmentParams()` の既定（likert_fixed_targets=None）のまま
            #   `select_likert_targets` が走り、**5 層ラウンドロビンにフォールバック**する
            #   ＝FD Q2 で否決した挙動が本番経路で復活してしまう。
            #   固定 10 件を渡せば `likert.py` の**固定アンカー優先ロジックが全件を採用して
            #   即 return** する（`likert.py` は無改修）。
            meta = await repo.get_plan_meta(plan_set)
            fixed = tuple((meta or {}).get("likert_targets") or ())
            pool = await repo.list_active_items()
            # ★件数も**プランを権威**にする（`likert_items` を固定リストの長さに合わせる）。
            #   これをしないと `want = min(likert_items, |pool|)` が既定 10 のままとなり、
            #   **固定リストが 10 件未満のとき不足分をラウンドロビンが補充**してしまう
            #   ＝FD Q2 で否決した挙動が部分的に復活する（integration で実測・検出）。
            #   長さを合わせれば `select_likert_targets` は固定分を採り切った時点で即 return し、
            #   **補充ループに入らない**（`likert.py` は無改修のまま）。
            likert_targets = select_likert_targets(
                pool, seed,
                params.model_copy(update={"likert_fixed_targets": fixed,
                                          "likert_items": len(fixed)}),
            ) if fixed else []

        # U5: Likert ターゲットはペア列と**同じ batch で原子保存**する（DP-U5-02。別経路に
        # すると「ペア列は保存されたが Likert 未保存」の窓が生じる）。★U6 でもここは不変。
        new_session = Session(
            token=token, phase="practice", seed=seed,
            exposure_snapshot=exposure, created_at=now,
            likert_targets=likert_targets,
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
