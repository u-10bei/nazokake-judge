-- smoke test 用の最小スキーマ(使い捨て)
-- smoke_items: 通常 insert / batch 原子性(NOT NULL 違反でロールバック)の検証用
CREATE TABLE IF NOT EXISTS smoke_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL
);

-- smoke_judgments: DP-02 (一意制約 + ON CONFLICT DO NOTHING) セマンティクスの検証用
CREATE TABLE IF NOT EXISTS smoke_judgments (
  token   TEXT NOT NULL,
  pair_id TEXT NOT NULL,
  choice  TEXT NOT NULL,
  UNIQUE (token, pair_id)
);
