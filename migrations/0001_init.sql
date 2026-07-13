-- nazokake-judge 初期スキーマ（U1 C-SCHEMA）。
-- `wrangler d1 migrations` で versioned 適用（DDL 適用はデプロイ時操作, H-1 の例外ではない）。
-- 制約は schema/models.py と 1:1。D1 = SQLite 互換。

-- 刺激（作品）。本文はリポジトリ管理外（body_ref で参照, NFR-08）。
CREATE TABLE IF NOT EXISTS items (
  item_id  TEXT PRIMARY KEY,
  layer    TEXT NOT NULL CHECK (layer IN ('pro','ai','edit','rule')),  -- BR-11: 層ラベル必須
  body_ref TEXT NOT NULL
);

-- トークン。状態遷移は一方向（BR-09）。
CREATE TABLE IF NOT EXISTS tokens (
  token          TEXT PRIMARY KEY,
  status         TEXT NOT NULL DEFAULT 'unused'
                   CHECK (status IN ('unused','in_progress','completed')),
  issued_at      TEXT NOT NULL,
  last_active_at TEXT                                                   -- BR-04 非アクティブ判定
);

-- セッション（token と 1:1）。seed / exposure_snapshot は監査リプレイ用（Q4=B）。
CREATE TABLE IF NOT EXISTS sessions (
  token             TEXT PRIMARY KEY REFERENCES tokens(token),
  phase             TEXT NOT NULL DEFAULT 'instruction'
                      CHECK (phase IN ('instruction','practice','judging','likert','survey','done')),
  seed              INTEGER NOT NULL,
  exposure_snapshot TEXT NOT NULL DEFAULT '{}',                        -- JSON: item_id -> count
  created_at        TEXT NOT NULL
);

-- 確定ペア列。位置（left/right）は一様ランダム記録（BR-07）。練習判定はサーバ（BR-10）。
CREATE TABLE IF NOT EXISTS pairs (
  token       TEXT NOT NULL REFERENCES tokens(token),
  pair_id     TEXT NOT NULL,
  idx         INTEGER NOT NULL,
  item_left   TEXT NOT NULL REFERENCES items(item_id),
  item_right  TEXT NOT NULL REFERENCES items(item_id),
  is_practice INTEGER NOT NULL DEFAULT 0,                              -- 0/1
  PRIMARY KEY (token, pair_id)
);
CREATE INDEX IF NOT EXISTS idx_pairs_token_idx ON pairs (token, idx);

-- 判定。(token, pair_id) 一意で冪等（DP-02 / BR-08 / U1-NFR-04）。
CREATE TABLE IF NOT EXISTS judgments (
  token      TEXT NOT NULL REFERENCES tokens(token),
  pair_id    TEXT NOT NULL,
  choice     TEXT NOT NULL CHECK (choice IN ('A','B')),
  created_at TEXT NOT NULL,
  UNIQUE (token, pair_id)
);

-- ブリッジ Likert 評定（BT 較正アンカー）。
CREATE TABLE IF NOT EXISTS likert_responses (
  token      TEXT NOT NULL REFERENCES tokens(token),
  target_ref TEXT NOT NULL,
  rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 7),
  created_at TEXT NOT NULL
);

-- 事後アンケート（token と 1:1）。
CREATE TABLE IF NOT EXISTS survey_responses (
  token      TEXT PRIMARY KEY REFERENCES tokens(token),
  answers    TEXT NOT NULL DEFAULT '{}',                              -- JSON
  created_at TEXT NOT NULL
);
