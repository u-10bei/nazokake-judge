-- U2: likert_responses に (token, target_ref) の一意制約を追加（BR-U2-17 / U2-NFR-15）。
-- 初回不変の冪等化を DB 側で保証（ON CONFLICT DO NOTHING + 既存 rating 返却）。
-- SQLite は既存テーブルへの UNIQUE 追加を ALTER でできないため、UNIQUE INDEX で付与する
-- （0001 の likert_responses は制約なしで作成済み）。新規プロジェクトで既存行なく安全。
-- 適用は「migration → deploy」の順（Infra §5、deploy.yml は versioned 自動適用）。

CREATE UNIQUE INDEX IF NOT EXISTS idx_likert_token_target
  ON likert_responses (token, target_ref);
