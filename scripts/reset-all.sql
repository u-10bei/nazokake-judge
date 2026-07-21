-- データのリセット（方法B: 全データ・プールごと完全リセット）
--
-- 用途: 新しい刺激プールで一から始める。全 9 テーブルを空にする（items・プランも消す）。
--       → pool_ingest → token_issue から一巡をやり直す（runbook §2 の①以降）。
--
-- 実行:
--   npx wrangler d1 execute nazokake-judge --remote --file=scripts/reset-all.sql
--   （--remote を付けないと local(dev) D1 に効く。本番に効かせるときだけ --remote）
--
-- ⚠️ スキーマ（テーブル・migration 0001〜0005）はそのまま残る＝**再デプロイ不要**。
--    d1_migrations（適用済み記録）にも触れないので整合する。
--    テーブル定義ごと真っさらにしたい場合のみ「方法C: D1 を作り直す」（runbook 参照）。
-- ⚠️ ADMIN_BASIC_* シークレットは Worker 側にあり、D1 を消しても残る（再設定不要）。
--
-- DELETE は **FK 安全な順（子 → 親）**。items は最後（pairs が参照するため）。
--
-- ★U6: assignment_plan / assignment_plan_meta も必ず消す。**プランは item_id を参照する**ため、
--   items だけ消してプランを残すと「存在しない作品を指す有効プラン」が生き続け、
--   token_issue がそれに束縛し、セッション開始時に壊れる（FK は張っていないので DB は止めない）。
--   ※プールを保ったままやり直すなら方法A（reset-responses.sql）——**そちらはプランを残すのが正しい**。

DELETE FROM judgments;
DELETE FROM pairs;
DELETE FROM sessions;
DELETE FROM likert_responses;
DELETE FROM survey_responses;
DELETE FROM tokens;
DELETE FROM items;
DELETE FROM assignment_plan;
DELETE FROM assignment_plan_meta;
