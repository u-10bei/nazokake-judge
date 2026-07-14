# U2 Tech Stack Decisions — 参加者セッション（participant）

U1 の TSD-01〜08・U4a の TSD-U4a-01〜06 を前提に、U2 追加分を **TSD-U2-NN** で定義する。案 A′（raw workers API + Pydantic v2, F-4/F-5）・uv+pywrangler・CI デプロイは U1 で確定済み。参加者系は `/api/*` を同一 Worker に追加する（`/admin/*` と別接頭辞）。

---

## TSD-U2-01: 参加者 API のルーティングと衛生
- **方式**: raw workers API の `on_fetch` 内で `/api/*` を**手動ディスパッチ**（`/admin/*` と同様、ASGI/FastAPI 非前提, F-5）。`entry.py` に `/api/` 分岐を追加。**Basic 認証は付けない**（トークン=資格, U2-NFR-01）。
- **エンドポイント**: `GET /api/session?token=`（start_or_resume+get_state）、`POST /api/judgment`・`/api/likert`・`/api/survey`（body 渡し, U2-NFR-04）。
- **衛生**: 全 `/api/*` 応答に `Cache-Control: no-store`（U2-NFR-02）、HTTPS 前提、パラメータ化クエリ（U2-NFR-05）。
- **CORS/配信オリジン**: 参加者フロント（`frontend/`）を **API と同一オリジンで配信**すれば CORS 不要。別オリジン配信（例: Pages）を Infrastructure Design で採る場合は **許可オリジンをフロント配信元に限定**する。詳細は Infrastructure Design。
- 根拠: U2-NFR-01/02/04/05, BR-U2-26/27。

## TSD-U2-02: 参加者系ログと相関ハッシュ
- U1 LogEmitter（`emit`）を再利用。**トークン生値・本文は非出力**。相関が要る箇所は**トークンのハッシュ（SHA-256 先頭 8 文字を単一規約）**を相関キーに使う（U2-NFR-03）。ハッシュ算出方法・桁数は Code Generation で 1 箇所のユーティリティに固定（複数実装での桁数ブレを防ぐ）。
- 配置: `backend/participant/`（AdminLog=`backend/admin/log.py` と対をなす参加者系ログラッパ）。
- 根拠: U2-NFR-03, U4a-NFR-03 と同水準。

## TSD-U2-03: ビュー型（レスポンス契約・出自秘匿）
- **`SessionView` / `PairView` / `ItemView` / `LikertTargetView` / `SubmitResult` を `schema/` に追加**（Worker が返し、フロントが消費する単一データ契約）。
- **`ItemView = {item_id, body}` を固定**し、`layer`/`body_ref`/`seed`/`exposure_snapshot` を**構造的に含めない**（型に存在しない＝事故で露出しない, U2-NFR-06）。
- 業務エラーは **200 + `{ok:false, ...}`** 統一封筒（U4a と同水準, BR-U2-29）。`submit_likert`/`submit_survey` は更新後 SessionView を返す（次アクション同期）。
- 根拠: U2-NFR-06, domain-entities.md。

## TSD-U2-04: フェーズ導出・Likert 選定の純粋関数
- **`derive_phase(...)`**: DB カウント（pairs/judgments/likert/survey/token.status）から 5 状態（practice/judging/likert/survey/done）を導出する**純粋述語**。配置は `backend/participant/`（サービス層）だが副作用なしで PBT 可能（PU2-3 単調性）。
- **`select_likert_targets(pool, seed, params) -> list[str]`**: `backend/domain/` に純関数追加。`likert_fixed_targets` 優先 + seed 層均等補充。決定論（P-6）、PBT 対象（PU2-6, PBT-03 系）。
- 既存純関数（`generate_pairs`/`serialize`/`deserialize`/`next_unanswered_index`）を再利用（再実装しない, 層の逆流禁止）。
- 根拠: U2-NFR-07（§7 テスト）, FD Q1/Q3, BR-U2-01/14。

## TSD-U2-05: データ・マイグレーション（migration 0003 + params 拡張）
- `migrations/0003_likert_unique.sql`（versioned）: `likert_responses` に `UNIQUE(token, target_ref)` 追加（既存行なしで安全, U2-NFR-15）。適用は `wrangler d1 migrations`（dev→prod、**適用→デプロイの順**、0002 と同じ流儀）。
- `schema/models.py`: `AssignmentParams.likert_fixed_targets: list[str] | None = None` 追加。
- `backend/repo/repository.py`: `insert_likert`（`ON CONFLICT DO NOTHING` + 既存 rating 返却=初回不変）・`upsert_survey`（PK=token）・回答済み pair_id / Likert 済み target_ref の読み取りメソッドを追加。既存（`save_pair_sequence`/`insert_judgment`/`mark_token_*`/`touch_token`/`list_items`/`read_exposure_counts`）を再利用。
- 根拠: U2-NFR-10/15, BR-U2-15/17/21。

## TSD-U2-06: フロントエンド・テスト
- **フロント**: 単一 HTML + バニラ JS の SPA ウィザード（フレームワーク不使用・静的配信）。状態はサーバ権威、クライアントは localStorage にトークンのみ。**楽観更新なし**（U2-NFR-09）。モバイルファースト・日本語のみ・合理的アクセシビリティ（U2-NFR-07/08）。配信方法は Infrastructure Design で確定。
- **テスト**: PBT（`tests/pbt/`）= PU2-1（ラウンドトリップ）/PU2-3（derive_phase 単調性）/PU2-6（select_likert_targets）。integration（`tests/integration/`、実 D1・`/api/*` 越し）= PU2-2/4/5/7/8。PBT 強制 PBT-02/03/07/08/09（U1/U4a と同一）。統合ハーネス流用。
- 根拠: U2-NFR-07/08/09, §7。

---

## 決定サマリ
| ID | 決定 |
|---|---|
| TSD-U2-01 | `/api/*` を on_fetch 手動ディスパッチ・トークン=資格・no-store・CORS は同一オリジンで不要（別オリジン時は限定） |
| TSD-U2-02 | 参加者系ログ・相関ハッシュ（SHA-256 先頭 8 文字単一規約）・トークン/本文非出力 |
| TSD-U2-03 | ビュー型を schema/ に・`ItemView={item_id,body}` 固定（出自を型から排除） |
| TSD-U2-04 | `derive_phase`（純粋述語）・`select_likert_targets`（純関数）・既存純関数再利用 |
| TSD-U2-05 | migration 0003（likert UNIQUE）+ `likert_fixed_targets` + Repository 追加メソッド |
| TSD-U2-06 | バニラ JS SPA（楽観更新なし）・PBT/integration 振り分け |

## 後続への申し送り
- **NFR Design**: `/api/*` の衛生（no-store・トークン非ログ）、出自秘匿（ItemView）、フェーズ導出/Likert 選定の LC 位置づけ、冪等（Likert UNIQUE）を設計パターン（DP）・論理コンポーネント（LC）に落とす。CORS/配信オリジンは Infrastructure Design。
- **Code Generation**: `backend/participant/`（サービス・ルーティング・参加者系ログ・derive_phase）、`backend/domain/select_likert_targets`、`schema/` ビュー型 + `likert_fixed_targets`、migration 0003、Repository 追加メソッド、`frontend/` SPA、PBT/integration。
