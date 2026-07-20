"""in-memory の Repository ダブル（U5 のワイヤリング検証用）。

**なぜ必要か**: 本物の `Repository` は D1（workers ランタイム）を要するため unit/PBT から
呼べない。一方 U5 の要件は「**どの経路がどちらのプールを読むか**」という**ワイヤリング**に
かかっており、純関数テストでは検出できない（`generate_pairs` 自体は正しくても
`start_or_resume` が `list_items()` を呼んでいたら要件は壊れる）。

**責務の境界**:
  - 本ダブル = `session` / `survey` の**ワイヤリング**検証（PU5-1 / PU5-2）。
  - **SQL の意味論**（retire の冪等性・export の items 集合）は**本ダブルでは検証しない**
    （ダブルの再実装を検証することになり無意味）。→ **実 D1 の integration が正**
    （PU5-3 / PU5-4 = `tests/integration/drive_u5.py`）。
"""

from __future__ import annotations

from schema import Item, Pair, Session, Token


class FakeRepo:
    """`session`/`survey` が使う読み書きだけを持つ最小のダブル。

    `items` は `(Item, retired_at)` で保持し、`list_items`（全件）と `list_active_items`
    （現役のみ）を**本物と同じ意味論**で返す。retire は「フラグを立てるだけ」（SQL の
    冪等性は検証対象外＝integration の責務）。
    """

    def __init__(self, items: list[Item], retired: set[str] | None = None):
        self._items = list(items)
        self._retired = set(retired or ())
        self.sessions: dict[str, Session] = {}
        self.pairs: dict[str, list[Pair]] = {}
        self.tokens: dict[str, Token] = {}
        self.answered_pairs: dict[str, set[str]] = {}
        self.answered_likert: dict[str, set[str]] = {}
        self.surveys: set[str] = set()
        # U6: プラン関連（未設定＝フォールバック経路）
        self.plan_bindings: dict[str, tuple[str, int]] = {}
        self.plans: dict[str, dict[int, list[Pair]]] = {}
        self.plan_meta: dict[str, dict] = {}
        self.active_plan_set: str | None = None
        self.slot_answered: dict[tuple[str, int], set[str]] = {}

    # ---- プール（★U5 の中心: 二本立ての読み取り経路） ----
    async def list_items(self) -> list[Item]:
        """全件（廃止済みを含む）。"""
        return list(self._items)

    async def list_active_items(self) -> list[Item]:
        """現役のみ（`retired_at IS NULL` 相当）。"""
        return [i for i in self._items if i.item_id not in self._retired]

    def retire(self, *item_ids: str) -> None:
        """テスト用の状態操作（SQL の冪等性は integration の責務ゆえ再現しない）。"""
        self._retired.update(item_ids)

    def unretire(self, *item_ids: str) -> None:
        self._retired.difference_update(item_ids)

    # ---- U6: 事前生成割当（プラン）----
    # `plan_bindings[token] = (plan_set, plan_index)` / `plans[plan_set][plan_index] = [Pair]`
    # / `plan_meta[plan_set] = {...}`。未設定なら `get_token_plan` は None を返し、
    # `start_or_resume` は**従来のオンライン生成にフォールバック**する（U6-NFR-14）。

    async def get_token_plan(self, token: str) -> tuple[str, int] | None:
        return self.plan_bindings.get(token)

    async def get_plan_pairs(self, plan_set: str, plan_index: int) -> list[Pair]:
        return list(self.plans.get(plan_set, {}).get(plan_index, []))

    async def get_plan_meta(self, plan_set: str) -> dict | None:
        return self.plan_meta.get(plan_set)

    async def get_active_plan_set(self) -> str | None:
        return self.active_plan_set

    async def answered_pair_ids_for_slot(self, plan_set: str, plan_index: int) -> set[str]:
        """スロット上で回答済みの pair_id（補充トークンの引き継ぎ検証用）。"""
        return set(self.slot_answered.get((plan_set, plan_index), set()))

    # ---- セッション ----
    async def get_session(self, token: str) -> Session | None:
        return self.sessions.get(token)

    async def save_pair_sequence(self, session: Session, pairs: list[Pair]) -> None:
        # 本物は単一 batch で all-or-nothing（DP-U5-02）。ダブルでは同時代入で表現。
        self.sessions[session.token] = session
        self.pairs[session.token] = list(pairs)

    async def get_pairs(self, token: str) -> list[Pair]:
        return list(self.pairs.get(token, []))

    async def read_exposure_counts(self, now_iso: str, inactive_threshold_hours: int) -> dict:
        return {}

    # ---- トークン ----
    async def get_token(self, token: str) -> Token | None:
        return self.tokens.get(token)

    async def mark_token_in_progress(self, token: str, now_iso: str) -> None:
        tok = self.tokens.get(token)
        if tok is not None:
            self.tokens[token] = tok.model_copy(update={"status": "in_progress"})

    async def touch_token(self, token: str, now_iso: str) -> None:
        pass

    # ---- 回答 ----
    async def answered_pair_ids(self, token: str) -> set[str]:
        return set(self.answered_pairs.get(token, set()))

    async def answered_likert_refs(self, token: str) -> set[str]:
        return set(self.answered_likert.get(token, set()))

    async def survey_exists(self, token: str) -> bool:
        return token in self.surveys
