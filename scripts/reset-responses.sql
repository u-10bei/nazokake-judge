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

-- ★U6: assignment_plan / assignment_plan_meta は**意図的に残す**。同じプール・同じプランで
--   やり直すのが本手順の趣旨であり、プランを消すと再生成・再投入が必要になる。
--   judgments が消えるため **activate ガード（409）も解除**され、切替が必要なら可能になる。
--   トークンは消えるので、プランへの束縛は token_issue の再発行で張り直される。

DELETE FROM judgments;
DELETE FROM pairs;
DELETE FROM sessions;
DELETE FROM likert_responses;
DELETE FROM survey_responses;
DELETE FROM tokens;
