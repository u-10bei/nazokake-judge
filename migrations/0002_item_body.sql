-- U4a: Item に本文 body を D1 格納（Q5=X）。body_ref を出自メモ（任意）へ格下げ。
-- SQLite は ALTER で NOT NULL 追加/制約緩和が難しいため items をテーブル再構築する。
-- 新規プロジェクトで既存行なし（あっても body='' で移送）。適用は「migration → deploy」の順（Infra §4）。

CREATE TABLE items_new (
  item_id  TEXT PRIMARY KEY,
  layer    TEXT NOT NULL CHECK (layer IN ('pro','ai','edit','rule')),  -- BR-11
  body     TEXT NOT NULL,                                              -- 謎かけ本文（D1 格納）
  body_ref TEXT                                                        -- 出自メモ（任意）
);

INSERT INTO items_new (item_id, layer, body, body_ref)
  SELECT item_id, layer, '', body_ref FROM items;

DROP TABLE items;
ALTER TABLE items_new RENAME TO items;
