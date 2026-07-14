# U2 NFR Design Patterns — 参加者セッション（participant）

U2-NFR-01〜15 を設計パターン **DP-U2-NN** に落とす。U1 の DP-01〜08・U4a の DP-U4a-01〜07 を前提に、U2 固有分のみ。案 A′（raw workers API, F-5）の制約に整合。

---

## DP-U2-01: トークン検証チョークポイント（軽量・入口集約）
- `on_fetch` の `/api/*` ディスパッチ**入口で token を解決し `get_token` で検証する共通ステップを 1 箇所**に置く（U4a の認証チョークポイント DP-U4a-01 と対をなす軽量版）。各ハンドラは検証済みトークン/状態を受け取り、**検証漏れのエンドポイントを構造的に作らない**。
- **一次判定は入口・状態別分岐はハンドラ**: 無効/存在しないトークンは入口で一律拒否。`completed` の扱いはハンドラ側（`GET /api/session` は完了画面 = BR-U2-25、POST 系は新規回答拒否）。
- Basic 認証は付けない（トークン=資格, U2-NFR-01）。
- 対応: U2-NFR-01, Q1。

## DP-U2-02: 出自秘匿＝型で排除（本ユニットの要）
- 参加者向けレスポンスは **`ItemView = {item_id, body}` 等のビュー型のみ**を通し、**`Item`（layer/body_ref 込み）を直接シリアライズしない**。**domain→view の写像を 1 箇所（Serializer 境界）**に集約し、`layer`/`body_ref`/`seed`/`exposure_snapshot` を構造的に落とす。
- **型に存在しない＝事故で出せない**: U2-NFR-06（ブラインド評価の成立条件）を規律ではなく**型システム**で守る最強形。「デバッグ用に layer をフラグで返す」等の抜け穴を作らない。
- 対応: U2-NFR-06, Q2(a)。

## DP-U2-03: トークン非ログ＝単一ラッパ + ハッシュ規約
- 参加者系ログは U1 `emit` を**許可フィールド限定で呼ぶ薄いラッパ**（`backend/participant/log.py`）を通す。**トークン生値・謎かけ本文を構造的に排除**。
- 相関が要る箇所は**トークンのハッシュ（SHA-256 先頭 8 文字・1 箇所のユーティリティに固定）**のみを相関キーに使う（桁数ブレ防止）。wrangler tail で特定参加者フローを生値なしで追える。
- U4a の AdminLog（DP-U4a-02）・U1 の単一発行点（DP-06）と同型。
- 対応: U2-NFR-03, Q2(b)。

## DP-U2-04: no-store＝共通レスポンスヘルパ
- 全 `/api/*` 応答を**共通ヘルパ経由**で生成し、`Cache-Control: no-store` を必ず付与（付け忘れ防止）。JSON レスポンス生成・エラー封筒（DP-U2-07）も同ヘルパに集約。
- 対応: U2-NFR-02, Q2(c)。

## DP-U2-05: 純粋述語 + 純関数（I/O は呼び出し側）
- **`derive_phase(...)` は純粋述語**: DB カウント（pairs/judgments/likert/survey/token.status）を**引数で受け取り**、5 状態（practice/judging/likert/survey/done）を導出。副作用なし＝PBT（PU2-3 単調性）可能。I/O は呼び出し側サービスが Repository で集めて渡す。
- **`select_likert_targets(pool, seed, params)` は `backend/domain/` の純関数**（`generate_pairs` と同居）。`likert_fixed_targets` 優先 + seed 層均等補充。決定論（P-6）、PBT（PU2-6）。
- 既存純関数（`generate_pairs`/`serialize`/`deserialize`/`next_unanswered_index`）を再利用。AssignmentEngine（LC-02）で確立した「I/O は呼び出し側・述語は純粋」型の踏襲。
- 対応: U2-NFR §7, Q3, BR-U2-01/14。

## DP-U2-06: DB 側冪等 + サーバ確認の完了順序
- **冪等は DB 側**（アプリ層 check-then-insert 不使用, U1-NFR-04 の一貫適用）:
  - 判定 `(token,pair_id)` 一意（既存 DP-02）。
  - **Likert `(token,target_ref)` UNIQUE（migration 0003）+ `ON CONFLICT DO NOTHING` + 既存 rating 返却（初回不変）**。
  - **Survey は PK=token で upsert**。
- **完了順序はサーバ確認**: `submit_survey` 内で「本番判定全件 ∧ Likert 全対象評定 ∧ survey 行あり」を Repository 集計で確認してから `mark_token_completed`（一方向 BR-09, U2-NFR-11）。
- 同時開始の露出競合は**ロックなし許容**（U2-NFR-12、U1 Q8 と同型）。
- 対応: U2-NFR-10/11/12, Q4, BR-U2-17/21/24。

## DP-U2-07: 統一エラー封筒 + SessionView 再同期契約
- **統一封筒**: `/api/*` の業務エラー（無効/completed トークン・不正 pair/choice/rating・フェーズ外）は **200 + `{ok:false, error, phase?}`**（U4a=DP-U4a-07 と同水準）。
- **サーバ権威の再同期契約**: すべての送信レスポンスに**更新後の SessionView（phase/next/progress）を載せる**。クライアントは**楽観更新せず**レスポンスの phase で描画。順序外・二重送信・フェーズ外は「サーバの現行 phase に UI が追従」という**単一の回復経路**に収束（`derive_phase` の単調性が支える）。
- 対応: U2-NFR-09, Q5, BR-U2-03/29。

---

## 導入しない設計部品（意図的な非採用・U1/U4a と同方針）
| 部品 | 非採用理由 |
|---|---|
| キャッシュ | `list_items`/`read_exposure_counts` は小規模で瞬時（U2-NFR-14）。 |
| キュー | 同期・小規模、非同期処理なし。 |
| サーキットブレーカ / リトライ基盤 | 外部依存の連鎖なし。クライアント再送は UX 目的の局所リトライで十分（U2-NFR-13）。 |
| 分散ロック | 露出競合はロックなし許容（DP-U2-06 / U2-NFR-12）。 |
| スケール機構 | 総参加者数十名・同時数名（N/A）。 |
