-- U6: 層拡張（下帯アンカー / 練習専用）+ 事前生成割当。
--
-- ============================================================================
-- ★ items の再構築は「子行退避方式」で行う（単純再構築は失敗する）
-- ============================================================================
-- SQLite は CHECK 制約を ALTER できないためテーブル再構築が要るが、**pairs が items を
-- FK 参照する行を持つ状態では `DROP TABLE items` が FOREIGN KEY constraint failed になる**
-- （local D1 で実測）。0002 が通ったのは「新規プロジェクトで既存行なし」だったため
-- （0002 のコメント参照）＝**0005 が初めて「データがある状態での親テーブル再構築」**。
--
-- `PRAGMA foreign_keys=OFF` / `PRAGMA defer_foreign_keys=ON` はいずれも **D1 の migration
-- 実行環境では効かない**（両方とも実測で失敗）。よって子行を一時退避してから親を作り直す。
--
-- ---------------------------------------------------------------------------
-- ★ FK 全数調査の結果（退避対象が pairs だけで足りる根拠・0001 を全数確認）
-- ---------------------------------------------------------------------------
--   items を参照する FK      : pairs.item_left / pairs.item_right の **2 本のみ**
--   likert_responses.target_ref : **FK 非設定**（素の TEXT）
--   judgments                : tokens のみ参照（pair_id は FK ではない）
--   sessions / survey_responses : tokens のみ参照
--
-- ★ assignment_plan には FK を張らない（U6 Infra Q1=A′ の設計判断）
--   理由 (1) FK を張ると items 参照 FK が 2→4 本に増え、**将来 items を再構築する
--            migration の退避対象が増える**（負債を作らない）。
--        (2) プラン投入をプール構成から独立させる（投入順序の自由度を保つ）。
--   整合性は **plan_generate の verify（構成時）+ POST /admin/plan の実在検証（投入時）**
--   の二重で担保する。→ 将来 items を再構築する場合も **退避対象は pairs のみでよい**。
--
-- ★ 適用ウィンドウの制約（U6-NFR-04・ブロッキング）
--   退避中は「空の pairs を読む窓」が生じ、稼働中だと露出計算・セッション再開が壊れる。
--   **適用は「発行済み未消化トークンが存在しない時点」に限る**（実験開始前のカットオーバー）。
--
-- ★ 適用後検証（U6-NFR-05・必須）
--   ① PRAGMA foreign_key_check が違反なし
--   ② items / pairs の行数が適用前後で一致
--   ③ retired_at 非 NULL 件数が適用前後で一致（U5 の廃止状態が保全されたこと）
-- ============================================================================

-- ---- ① items 再構築（layer に anchor / practice を追加）----
CREATE TABLE pairs_bak AS SELECT * FROM pairs;   -- 子行を退避
DELETE FROM pairs;                                -- 親への参照を外す

CREATE TABLE items_new (
  item_id    TEXT PRIMARY KEY,
  -- BR-U6-01: anchor（下帯アンカー・役割層）/ BR-U6-04: practice（練習専用・分析的に不活性）
  layer      TEXT NOT NULL
               CHECK (layer IN ('pro','ai','edit','rule','anchor','practice')),
  body       TEXT NOT NULL,
  body_ref   TEXT,
  retired_at TEXT                                 -- ★ U5(0004) から必ず引き継ぐ
);
INSERT INTO items_new (item_id, layer, body, body_ref, retired_at)
  SELECT item_id, layer, body, body_ref, retired_at FROM items;
DROP TABLE items;
ALTER TABLE items_new RENAME TO items;

-- 子行を復元（列は明示。SELECT * に依存しない = 列順・列追加の変化に強くする）
INSERT INTO pairs (token, pair_id, idx, item_left, item_right, is_practice)
  SELECT token, pair_id, idx, item_left, item_right, is_practice FROM pairs_bak;
DROP TABLE pairs_bak;

-- ---- ② 事前生成プラン（BR-U6-09/12）----
-- plan_set で成立版 / フォールバック版をキーする。**D1 には選択されたセットのみ投入**する
-- （両セットはリポジトリにコミットして固定＝commit 履歴とハッシュが証跡, BR-U6-12 改訂）。
CREATE TABLE IF NOT EXISTS assignment_plan (
  plan_set    TEXT NOT NULL,
  plan_index  INTEGER NOT NULL,          -- 0..E-1（スロット = 評価者枠）
  idx         INTEGER NOT NULL,          -- スロット内の提示順（練習が先頭・BR-U6-16）
  item_left   TEXT NOT NULL,             -- ★ FK を張らない（上記の設計判断）
  item_right  TEXT NOT NULL,             -- ★ 同上
  is_practice INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (plan_set, plan_index, idx)
);

-- 生成メタ（監査再現性 BR-U6-11 / 証跡 DP-U6-07）。
CREATE TABLE IF NOT EXISTS assignment_plan_meta (
  plan_set       TEXT PRIMARY KEY,
  seed           INTEGER NOT NULL,       -- 初期 seed
  attempt        INTEGER NOT NULL,       -- 成功試行番号（再試行を挟むため初期 seed だけでは再現不可）
  content_hash   TEXT NOT NULL,          -- プラン内容のハッシュ（名前でなく内容に紐づく証跡）
  n_items        INTEGER NOT NULL,
  n_slots        INTEGER NOT NULL,       -- E
  n_pairs        INTEGER NOT NULL,       -- J（本番のみ）
  m_per_item     INTEGER NOT NULL,       -- m
  likert_targets TEXT NOT NULL,          -- ★ JSON 配列（BR-U6-06 全固定運用の運搬経路）
  generated_at   TEXT NOT NULL,
  is_active      INTEGER NOT NULL DEFAULT 0   -- activate は 1 セットのみ（BR-U6-12）
);

-- ---- ③ トークンへのスロット束縛（DP-U6-06）----
-- ★ (plan_set, plan_index) を「組」で束縛する。plan_index 単独だと「その時点の有効セット」
--    参照になり、発行 → セッション開始の間に activate が切り替わるとトークンの意味が変わる
--    競合窓が生じる。組で束縛すればこの窓が消え、activate ガードの述語も一意に定まる。
-- NULL 許容ゆえテーブル再構築は不要。NULL = U6 以前のトークン / ドライラン用の即席トークン
-- → 従来どおりオンライン生成にフォールバック（U6-NFR-14・dev 専用・統計的性質は非目標）。
ALTER TABLE tokens ADD COLUMN plan_set   TEXT;
ALTER TABLE tokens ADD COLUMN plan_index INTEGER;
