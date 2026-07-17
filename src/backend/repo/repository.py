"""LC-03 Repository — D1 への唯一の I/O 境界（C-REPO）。

Worker(Pyodide) 内で D1 バインディング（env.DB）を受け取り動作する。全メソッドは
パラメータ化クエリのみ（BR-12 / DP-04）。ローカル/CI の pure-Python テストではなく
miniflare/ローカル D1 上でテストする（Build & Test）。

主メソッド:
  - save_pair_sequence: Session + PairSequence を単一 D1 batch で原子確定（DP-01）。
  - insert_judgment: ON CONFLICT DO NOTHING + 既存 choice 返却で冪等（DP-02/TSD-04）。
  - read_exposure_counts: 確定 PairSequence から露出を導出（H-2, derive_exposure に委譲）。
"""

from __future__ import annotations

import json

from backend.domain import SessionExposure, derive_exposure
from backend.repo._d1 import to_js_maybe, to_py
from schema import (
    ExposureCounts,
    Item,
    Pair,
    RejectedItem,
    RetireResult,
    Session,
    Token,
)


class Repository:
    """D1 バインディング（env.DB）を受け取る I/O 境界。"""

    def __init__(self, db):
        self._db = db

    # ---------------------------------------------------------- トークン

    async def get_token(self, token: str) -> Token | None:
        row = await (
            self._db.prepare(
                "SELECT token, status, issued_at, last_active_at FROM tokens WHERE token = ?"
            ).bind(token).first()
        )
        if row is None:
            return None
        return Token.model_validate(to_py(row))

    async def mark_token_in_progress(self, token: str, now_iso: str) -> None:
        # 一方向遷移（BR-09）: unused のときのみ in_progress へ。
        await (
            self._db.prepare(
                "UPDATE tokens SET status = 'in_progress', last_active_at = ? "
                "WHERE token = ? AND status = 'unused'"
            ).bind(now_iso, token).run()
        )

    async def mark_token_completed(self, token: str, now_iso: str) -> None:
        await (
            self._db.prepare(
                "UPDATE tokens SET status = 'completed', last_active_at = ? "
                "WHERE token = ? AND status = 'in_progress'"
            ).bind(now_iso, token).run()
        )

    async def touch_token(self, token: str, now_iso: str) -> None:
        """last_active_at を更新（BR-04 非アクティブ判定の鮮度維持）。"""
        await (
            self._db.prepare("UPDATE tokens SET last_active_at = ? WHERE token = ?")
            .bind(now_iso, token).run()
        )

    # ---------------------------------------------------------- 刺激プール

    async def list_items(self) -> list[Item]:
        """**全件**を返す（廃止済みを含む）。

        🔒 **凍結（BR-U5-02 / DP-U5-01）**: 本関数に active フィルタを足してはならない
        （`active_only` 引数の新設も禁止）。踏むと要件の両輪が**同時に**壊れる:
          (1) export の items が縮む → 自己完結性（judgments の item ⊆ items）が破れる
              → PU3-3 違反 → U4b 破壊（＝「それまでの結果は有効」が壊れる）
          (2) 旧セッションの Likert 導出フォールバックが変わる
              → 進行中セッションのターゲットが変わる（＝「新規のみ反映」が破れる）
        **出題対象を選ぶ用途には `list_active_items()` を使うこと。**

        呼び出し先（全件が正しい用途）: `build_view` の bodies 写像（進行中セッションの
        既存ペア列を解決するため必須）／`get_likert_targets` の旧セッション導出。
        """
        res = await self._db.prepare(
            "SELECT item_id, layer, body, body_ref FROM items"
        ).all()
        rows = to_py(res)["results"]
        return [Item.model_validate(r) for r in rows]

    async def list_active_items(self) -> list[Item]:
        """**現役のみ**を返す（`retired_at IS NULL`, U5 / LC-U5-01）。

        **「これから出題するものを選ぶ」用途はすべてこちら**（BR-U5-02a）:
        新規セッションのペア生成・Likert ターゲット選定・充足判定（ingest の warn /
        issue のゲート）。練習ペアは `generate_pairs` の同一呼び出し由来ゆえ自動的に効く
        （BR-U5-02b）。
        """
        res = await self._db.prepare(
            "SELECT item_id, layer, body, body_ref FROM items WHERE retired_at IS NULL"
        ).all()
        rows = to_py(res)["results"]
        return [Item.model_validate(r) for r in rows]

    async def retire_items(self, item_ids: list[str], now_iso: str) -> RetireResult:
        """出題停止（論理削除, BR-U5-06 / LC-U5-02 / DP-U5-03）。

        **冪等性は SQL の WHERE 句が保証する**: `AND retired_at IS NULL` により既に廃止済みは
        no-op ＝ **初回の廃止時刻が保持される**（証跡が後から書き換わらない）。
        分類（retired / already_retired / not_found）は UPDATE 直前の SELECT で判定する
        （batch 直前・ロックなし＝U4a 凍結ガードと同じ窓最小化方針）。**窓は報告用にしか
        影響しない**——冪等性は WHERE 句が持つ。

        **凍結ガード（BR-U4a-03）は通らない**: 本関数は `insert_items` とは別経路。
        `retired_at` は body/layer を変えず過去判定の解釈を壊さないため、参照済み item でも
        廃止できる（BR-U5-05）。
        """
        return await self._set_retired(item_ids, now_iso, retire=True)

    async def unretire_items(self, item_ids: list[str]) -> RetireResult:
        """出題停止の解除（復活, BR-U5-07）。誤操作の回復用。冪等（現役なら no-op）。"""
        return await self._set_retired(item_ids, None, retire=False)

    async def _set_retired(
        self, item_ids: list[str], now_iso: str | None, *, retire: bool
    ) -> RetireResult:
        ids = list(dict.fromkeys(item_ids))  # 重複除去（順序保持）
        if not ids:
            return RetireResult(ok=True)

        placeholders = ", ".join("?" for _ in ids)  # 全パラメータ化（U5-NFR-12）

        # 現状取得（分類用・UPDATE 直前）。
        res = await self._db.prepare(
            f"SELECT item_id, retired_at FROM items WHERE item_id IN ({placeholders})"
        ).bind(*ids).all()
        current = {r["item_id"]: r["retired_at"] for r in to_py(res)["results"]}

        not_found = [i for i in ids if i not in current]
        if retire:
            targets = [i for i in ids if i in current and current[i] is None]
            noop = [i for i in ids if i in current and current[i] is not None]
        else:
            targets = [i for i in ids if i in current and current[i] is not None]
            noop = [i for i in ids if i in current and current[i] is None]

        if targets:
            tph = ", ".join("?" for _ in targets)
            if retire:
                await self._db.prepare(
                    f"UPDATE items SET retired_at = ? WHERE item_id IN ({tph}) "
                    "AND retired_at IS NULL"
                ).bind(now_iso, *targets).run()
            else:
                await self._db.prepare(
                    f"UPDATE items SET retired_at = NULL WHERE item_id IN ({tph}) "
                    "AND retired_at IS NOT NULL"
                ).bind(*targets).run()

        return RetireResult(
            ok=True, retired=len(targets), already_retired=noop, not_found=not_found
        )

    async def referenced_item_ids(self) -> set[str]:
        """pairs から参照済みの item_id 集合（凍結ガード用, BR-U4a-03）。

        pairs に現れる item は保存済みペア列の構成要素であり、judgments はその pairs を
        参照する。よって「pairs に現れる item」を凍結対象（更新拒否）とする。
        """
        res = await self._db.prepare(
            "SELECT item_left AS iid FROM pairs UNION SELECT item_right FROM pairs"
        ).all()
        return {r["iid"] for r in to_py(res)["results"]}

    # ---------------------------------------------------------- 投入（U4a）

    async def insert_items(self, items: list[Item]) -> dict:
        """刺激プールを bulk 投入（DP-U4a-03/04）。

        - 未参照 item_id は upsert（`ON CONFLICT DO UPDATE`, べき等）、新規は INSERT。
        - **参照済み item_id への更新は拒否**（凍結ガード BR-U4a-03）→ 投入全体を中断。
        - 参照集合の取得は投入 batch の直前（窓最小化, ロックなし, Q2=A）。
        戻り値: {inserted, updated, rejected: list[RejectedItem]}。
        """
        existing = {
            r["item_id"]
            for r in to_py(await self._db.prepare("SELECT item_id FROM items").all())["results"]
        }
        referenced = await self.referenced_item_ids()  # batch 直前に取得

        rejected: list[RejectedItem] = [
            RejectedItem(
                item_id=it.item_id,
                reason="参照済み item への更新は拒否（プール凍結, BR-U4a-03）",
            )
            for it in items
            if it.item_id in referenced
        ]
        if rejected:
            # 投入全体を中断（部分適用しない, BR-U4a-03）
            return {"inserted": 0, "updated": 0, "rejected": rejected}

        # D1 は Python None の bind を undefined として拒否するため、body_ref が None の
        # ときは bind せず SQL リテラル NULL を使う（U1 と同じイディオム）。
        stmts = [self._item_upsert_stmt(it) for it in items]
        if stmts:
            await self._db.batch(to_js_maybe(stmts))

        inserted = sum(1 for it in items if it.item_id not in existing)
        updated = len(items) - inserted
        return {"inserted": inserted, "updated": updated, "rejected": []}

    def _item_upsert_stmt(self, it: Item):
        """1 item の upsert 文（body_ref None は SQL NULL, 非 None は bind）。"""
        if it.body_ref is None:
            return self._db.prepare(
                "INSERT INTO items (item_id, layer, body, body_ref) VALUES (?, ?, ?, NULL) "
                "ON CONFLICT(item_id) DO UPDATE SET "
                "layer=excluded.layer, body=excluded.body, body_ref=NULL"
            ).bind(it.item_id, it.layer.value, it.body)
        return self._db.prepare(
            "INSERT INTO items (item_id, layer, body, body_ref) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(item_id) DO UPDATE SET "
            "layer=excluded.layer, body=excluded.body, body_ref=excluded.body_ref"
        ).bind(it.item_id, it.layer.value, it.body, it.body_ref)

    async def insert_tokens(self, tokens: list[str], now_iso: str) -> int:
        """トークンを bulk 投入（status=unused, issued_at, DP-U4a-03/BR-U4a-10）。

        衝突の事前排除は呼び出し側（AdminApi, BR-U4a-06）。PK 衝突で batch 失敗時は
        呼び出し側が全体リトライする。戻り値: 投入件数。
        """
        stmts = [
            self._db.prepare(
                "INSERT INTO tokens (token, status, issued_at, last_active_at) "
                "VALUES (?, 'unused', ?, NULL)"
            ).bind(tok, now_iso)
            for tok in tokens
        ]
        if stmts:
            await self._db.batch(to_js_maybe(stmts))
        return len(tokens)

    async def all_token_strings(self) -> set[str]:
        """既存トークン文字列集合（発行時の衝突事前排除用, BR-U4a-06）。"""
        res = await self._db.prepare("SELECT token FROM tokens").all()
        return {r["token"] for r in to_py(res)["results"]}

    # ---------------------------------------------------------- 露出導出（H-2）

    async def read_exposure_counts(
        self, *, now_iso: str, inactive_threshold_hours: int = 48
    ) -> ExposureCounts:
        """確定 PairSequence から露出を集計（保持テーブルなし）。derive_exposure に委譲。"""
        token_rows = to_py(
            await self._db.prepare(
                "SELECT token, status, last_active_at FROM tokens"
            ).all()
        )["results"]
        pair_rows = to_py(
            await self._db.prepare(
                "SELECT token, pair_id, idx, item_left, item_right, is_practice FROM pairs"
            ).all()
        )["results"]

        pairs_by_token: dict[str, list[Pair]] = {}
        for r in pair_rows:
            pairs_by_token.setdefault(r["token"], []).append(_row_to_pair(r))

        sessions = [
            SessionExposure(
                status=t["status"],
                last_active_at=t.get("last_active_at"),
                pairs=pairs_by_token.get(t["token"], []),
            )
            for t in token_rows
        ]
        return derive_exposure(
            sessions, now_iso=now_iso, inactive_threshold_hours=inactive_threshold_hours
        )

    # ---------------------------------------------------------- 原子確定（DP-01）

    async def save_pair_sequence(self, session: Session, pairs: list[Pair]) -> None:
        """Session + PairSequence + exposure_snapshot + likert_targets を単一 batch で
        all-or-nothing 保存。

        半端なペア列（再開 US-P08 / 露出導出 H-2 を壊す）を原理的に生じさせない（TSD-03）。

        **U5（DP-U5-02）**: `likert_targets` を**同じ batch に載せる**ことで「ペア列は保存
        されたが Likert ターゲットは未保存」という中間状態が**原理的に生じない**。別経路で
        保存するとその窓を新設してしまう（＝BR-U5-04 の保証に穴）。
        """
        stmts = [self._session_insert_stmt(session)]
        for p in pairs:
            stmts.append(
                self._db.prepare(
                    "INSERT INTO pairs (token, pair_id, idx, item_left, item_right, is_practice) "
                    "VALUES (?, ?, ?, ?, ?, ?)"
                ).bind(
                    session.token, p.pair_id, p.index,
                    p.item_left, p.item_right, 1 if p.is_practice else 0,
                )
            )
        await self._db.batch(to_js_maybe(stmts))

    def _session_insert_stmt(self, session: Session):
        """sessions の INSERT 文（`likert_targets` None は SQL リテラル NULL）。

        D1 は Python None の bind を undefined として拒否するため、None のときは bind せず
        SQL リテラル NULL を使う（`_item_upsert_stmt` の body_ref と同じイディオム）。
        """
        base = ("INSERT INTO sessions "
                "(token, phase, seed, exposure_snapshot, created_at, likert_targets) ")
        common = (
            session.token,
            session.phase.value,
            session.seed,
            json.dumps(session.exposure_snapshot),
            session.created_at,
        )
        if session.likert_targets is None:
            return self._db.prepare(base + "VALUES (?, ?, ?, ?, ?, NULL)").bind(*common)
        # 順序を保って保存（提示順が意味を持つ, U5-NFR-07 / PBT-02）。
        return self._db.prepare(base + "VALUES (?, ?, ?, ?, ?, ?)").bind(
            *common, json.dumps(session.likert_targets)
        )

    # ---------------------------------------------------------- 参加者フロー読取（U2）

    async def get_session(self, token: str) -> Session | None:
        """セッション行を取得（再開・監査再現用, U2）。

        U5: `likert_targets`（JSON 配列 / NULL）を復元する。NULL → None は「U5 以前に開始した
        セッション」を意味し、呼び出し側（`get_likert_targets`）が全件導出にフォールバックする
        （BR-U5-04）。順序はそのまま保たれる（U5-NFR-07 / PBT-02）。
        """
        row = await (
            self._db.prepare(
                "SELECT token, phase, seed, exposure_snapshot, created_at, likert_targets "
                "FROM sessions WHERE token = ?"
            ).bind(token).first()
        )
        if row is None:
            return None
        d = to_py(row)
        d["exposure_snapshot"] = json.loads(d.get("exposure_snapshot") or "{}")
        # `[]`（Likert 対象なしのセッション）と NULL（U5 以前の旧セッション）は**意味が違う**:
        # 前者は「対象なしが確定済み」、後者は「未保存ゆえ全件導出にフォールバック」。
        # `[]` を None に潰すとフォールバックが走り、**本来ないはずの Likert 対象が生える**。
        # よって truthy 判定ではなく `is not None` で厳密に分ける（PBT-02 で検出）。
        raw_targets = d.get("likert_targets")
        d["likert_targets"] = json.loads(raw_targets) if raw_targets is not None else None
        return Session.model_validate(d)

    async def get_pairs(self, token: str) -> list[Pair]:
        """あるトークンの確定ペア列を index 昇順で取得（U2 再開・進捗）。"""
        res = await self._db.prepare(
            "SELECT token, pair_id, idx, item_left, item_right, is_practice "
            "FROM pairs WHERE token = ? ORDER BY idx"
        ).bind(token).all()
        return [_row_to_pair(r) for r in to_py(res)["results"]]

    async def answered_pair_ids(self, token: str) -> set[str]:
        """判定済み pair_id 集合（進捗・フェーズ導出・再開位置, U2）。"""
        res = await self._db.prepare(
            "SELECT pair_id FROM judgments WHERE token = ?"
        ).bind(token).all()
        return {r["pair_id"] for r in to_py(res)["results"]}

    async def answered_likert_refs(self, token: str) -> set[str]:
        """評定済み Likert target_ref 集合（フェーズ導出・次対象, U2）。"""
        res = await self._db.prepare(
            "SELECT target_ref FROM likert_responses WHERE token = ?"
        ).bind(token).all()
        return {r["target_ref"] for r in to_py(res)["results"]}

    async def survey_exists(self, token: str) -> bool:
        """事後アンケート行の有無（完了順序のサーバ確認, BR-U2-24）。"""
        row = await self._db.prepare(
            "SELECT 1 FROM survey_responses WHERE token = ?"
        ).bind(token).first()
        return row is not None

    # ---------------------------------------------------------- 参加者フロー書込（U2）

    async def insert_likert(
        self, token: str, target_ref: str, rating: int, now_iso: str
    ) -> int:
        """Likert 評定を冪等に挿入し、**保存されている rating**（初回優先）を返す。

        UNIQUE(token,target_ref)（migration 0003）+ ON CONFLICT DO NOTHING で初回不変
        （BR-U2-17。判定 insert_judgment と同型）。
        """
        await (
            self._db.prepare(
                "INSERT INTO likert_responses (token, target_ref, rating, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(token, target_ref) DO NOTHING"
            ).bind(token, target_ref, rating, now_iso).run()
        )
        kept = await (
            self._db.prepare(
                "SELECT rating FROM likert_responses WHERE token = ? AND target_ref = ?"
            ).bind(token, target_ref).first("rating")
        )
        return to_py(kept)

    async def upsert_survey(self, token: str, answers: dict, now_iso: str) -> None:
        """事後アンケートを upsert（PK=token, 再送・修正で 1 行, BR-U2-21）。"""
        await (
            self._db.prepare(
                "INSERT INTO survey_responses (token, answers, created_at) "
                "VALUES (?, ?, ?) ON CONFLICT(token) DO UPDATE SET "
                "answers = excluded.answers, created_at = excluded.created_at"
            ).bind(token, json.dumps(answers), now_iso).run()
        )

    # ---------------------------------------------------------- 冪等判定（DP-02）

    async def insert_judgment(
        self, token: str, pair_id: str, choice: str, now_iso: str
    ) -> str:
        """判定を冪等に挿入し、**保存されている choice**（既存優先）を返す。

        再送は既存値をそのまま観測できる（ON CONFLICT DO NOTHING, TSD-04 / U1-NFR-04）。
        """
        await (
            self._db.prepare(
                "INSERT INTO judgments (token, pair_id, choice, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(token, pair_id) DO NOTHING"
            ).bind(token, pair_id, choice, now_iso).run()
        )
        kept = await (
            self._db.prepare(
                "SELECT choice FROM judgments WHERE token = ? AND pair_id = ?"
            ).bind(token, pair_id).first("choice")
        )
        return to_py(kept)

    # ---------------------------------------------------------- 管理集計（U3・読み取り専用）

    async def read_progress(self) -> dict:
        """進捗カウント（US-R01, BR-U3-04）。judgments は本番のみ（is_practice=0）。"""
        row = await self._db.prepare(
            "SELECT "
            "(SELECT COUNT(*) FROM tokens) AS tokens_issued, "
            "(SELECT COUNT(*) FROM tokens WHERE status IN ('in_progress','completed')) AS tokens_started, "
            "(SELECT COUNT(*) FROM tokens WHERE status='completed') AS tokens_completed, "
            "(SELECT COUNT(*) FROM judgments j JOIN pairs p "
            "   ON j.token=p.token AND j.pair_id=p.pair_id WHERE p.is_practice=0) AS judgments_total, "
            "(SELECT COUNT(*) FROM likert_responses) AS likert_total, "
            "(SELECT COUNT(*) FROM survey_responses) AS survey_total"
        ).first()
        return to_py(row)

    async def read_winrates(self) -> list[dict]:
        """暫定勝率（US-R03, BR-U3-05）。本番判定を item 単位に UNION 展開して集計。

        各本番判定について item_left/item_right の 2 項目が「1 試合」、choice 側が勝ち。
        matches = 出場数、wins = 勝ち数、winrate = wins/matches（matches=0 は 0）。
        """
        res = await self._db.prepare(
            "WITH prod AS ("
            "  SELECT p.item_left, p.item_right, j.choice "
            "  FROM judgments j JOIN pairs p ON j.token=p.token AND j.pair_id=p.pair_id "
            "  WHERE p.is_practice=0"
            "), tallies AS ("
            "  SELECT item_left AS item_id, CASE WHEN choice='A' THEN 1 ELSE 0 END AS win FROM prod "
            "  UNION ALL "
            "  SELECT item_right AS item_id, CASE WHEN choice='B' THEN 1 ELSE 0 END AS win FROM prod"
            ") "
            "SELECT i.item_id AS item_id, i.layer AS layer, "
            "       COUNT(t.item_id) AS matches, COALESCE(SUM(t.win),0) AS wins "
            "FROM items i LEFT JOIN tallies t ON t.item_id=i.item_id "
            "GROUP BY i.item_id, i.layer"
        ).all()
        return to_py(res)["results"]

    async def read_export_rows(self, entity: str) -> list[dict]:
        """エクスポート用の行を返す（entity 別, BR-U3-06/07）。判定は本番のみ。"""
        if entity == "items":
            res = await self._db.prepare("SELECT item_id, layer FROM items").all()
        elif entity == "judgments":
            res = await self._db.prepare(
                "SELECT j.token AS token, j.pair_id AS pair_id, p.idx AS pair_index, "
                "       p.item_left AS item_left, p.item_right AS item_right, "
                "       j.choice AS choice, j.created_at AS created_at "
                "FROM judgments j JOIN pairs p ON j.token=p.token AND j.pair_id=p.pair_id "
                "WHERE p.is_practice=0"
            ).all()
        elif entity == "likert":
            res = await self._db.prepare(
                "SELECT token, target_ref, rating, created_at FROM likert_responses"
            ).all()
        elif entity == "surveys":
            res = await self._db.prepare(
                "SELECT token, answers, created_at FROM survey_responses"
            ).all()
        else:
            return []
        return to_py(res)["results"]


def _row_to_pair(r: dict) -> Pair:
    """pairs 行（idx / is_practice int）を Pair モデルへ写像する。"""
    return Pair(
        pair_id=r["pair_id"],
        index=r["idx"],
        item_left=r["item_left"],
        item_right=r["item_right"],
        is_practice=bool(r["is_practice"]),
    )
