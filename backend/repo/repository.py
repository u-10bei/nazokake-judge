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
from schema import ExposureCounts, Item, Pair, Session, Token


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
        res = await self._db.prepare("SELECT item_id, layer, body_ref FROM items").all()
        rows = to_py(res)["results"]
        return [Item.model_validate(r) for r in rows]

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
        """Session + PairSequence + exposure_snapshot を単一 batch で all-or-nothing 保存。

        半端なペア列（再開 US-P08 / 露出導出 H-2 を壊す）を原理的に生じさせない（TSD-03）。
        """
        stmts = [
            self._db.prepare(
                "INSERT INTO sessions (token, phase, seed, exposure_snapshot, created_at) "
                "VALUES (?, ?, ?, ?, ?)"
            ).bind(
                session.token,
                session.phase.value,
                session.seed,
                json.dumps(session.exposure_snapshot),
                session.created_at,
            )
        ]
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


def _row_to_pair(r: dict) -> Pair:
    """pairs 行（idx / is_practice int）を Pair モデルへ写像する。"""
    return Pair(
        pair_id=r["pair_id"],
        index=r["idx"],
        item_left=r["item_left"],
        item_right=r["item_right"],
        is_practice=bool(r["is_practice"]),
    )
