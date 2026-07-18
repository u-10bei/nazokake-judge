-- データのリセット（方法A: 回答データのみ・プール温存）
--
-- 用途: 同じ刺激プールで実験をやり直す。トークン・セッション・判定・Likert・アンケートを
--       消し、items（刺激プール）は残す。→ トークン再発行だけで再開できる。
--
-- 実行:
--   npx wrangler d1 execute nazokake-judge --remote --file=scripts/reset-responses.sql
--   （--remote を付けないと local(dev) D1 に効く。本番に効かせるときだけ --remote）
--
-- ⚠️ items.retired_at（出題停止フラグ）は残る。プールを完全に初期化したいなら
--    reset-all.sql（方法B）を使う。
-- ⚠️ スキーマ・migration は変更しない（再デプロイ不要）。
--
-- DELETE は **FK 安全な順（子 → 親）** で並べる。この順以外は FK 違反になる
--   （pairs/judgments/likert/survey/sessions → tokens、pairs → items）。

DELETE FROM judgments;
DELETE FROM pairs;
DELETE FROM sessions;
DELETE FROM likert_responses;
DELETE FROM survey_responses;
DELETE FROM tokens;
