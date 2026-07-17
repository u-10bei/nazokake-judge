-- U5: 出題停止（item retirement）。著作権配慮で「今後出題しない」を論理削除で表す。
--
-- 物理削除しない理由（BR-U5-01）:
--   (1) pairs.item_left/item_right は REFERENCES items(item_id) の FK を持つ（0001）
--   (2) ExportBundle の自己完結性（judgments の item ⊆ items, BR-U3-07）に items 全件が必要
--   → 論理削除が唯一の正解。過去の pairs/judgments/likert_responses は一切変更しない
--      ＝「それまでの判定結果は有効のまま」がデータ構造で保証される。
--
-- 安全な no-op 移行（U5-NFR-01）: いずれも NULL 許容ゆえ 0002 のようなテーブル再構築は不要・
-- 既存行のデータ移送も不要。適用直後の意味論は「既存 items = 全て現役 / 既存 sessions =
-- 全てフォールバック」＝**適用しただけでは挙動が一切変わらない**。
--
-- 適用は「migration → deploy」の順（U5-NFR-02。deploy.yml が既にこの順ゆえ自動的に守られる）。
-- インデックスは張らない（プール約 95 件・全走査で十分）。

-- 出題停止フラグ。NULL=現役 / ISO8601=廃止時刻（初回の廃止時刻を保持, BR-U5-06）。
-- retired_at は「現在状態」であり履歴ではない。履歴の正は admin_log（BR-U5-13）。
ALTER TABLE items ADD COLUMN retired_at TEXT;

-- U5: Likert ターゲットをセッション開始時に確定・保存（ペア列と同じ「開始時確定」原則,
-- BR-U5-04 / DP-U5-02）。save_pair_sequence の同一 batch で原子保存される。
-- NULL = U5 以前に開始したセッション → list_items()（全件）から導出にフォールバック
-- ＝従来挙動を完全再現し進行中セッションを壊さない（「新規のみ反映」の保証）。
ALTER TABLE sessions ADD COLUMN likert_targets TEXT;
