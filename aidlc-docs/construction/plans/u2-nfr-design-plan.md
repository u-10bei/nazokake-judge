# U2 NFR Design Plan — 参加者セッション（participant）

**ユニット**: U2。NFR Requirements（U2-NFR-01〜15）を設計パターン（DP-U2）と論理コンポーネント（LC-U2）に落とす。技術非依存寄りだが案 A′（raw workers API, F-5）の制約に整合させる。
**前提（既決）**: トークン=資格・`/api/*`（U2-NFR-01）／全応答 no-store・ログにトークン/本文非出力・相関ハッシュ単一規約（02/03）／出自秘匿＝ItemView 固定（06）／楽観更新なし・サーバ権威（09）／DB 側冪等（10・migration 0003）／完了順序保証（11）／露出競合許容（12）／PBT PU2-1/3/6・integration PU2-2/4/5/7/8（§7）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-design-patterns.md`（DP-U2-NN）/ `logical-components.md`（LC-U2-NN + 依存方向）を生成します。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-14）
- [x] `construction/u2/nfr-design/nfr-design-patterns.md`（DP-U2-01〜07: トークン検証チョークポイント・出自秘匿の型排除・トークン非ログ単一ラッパ・no-store ヘルパ・純粋述語/純関数・DB 側冪等+完了順序・統一封筒/SessionView 再同期）
- [x] `construction/u2/nfr-design/logical-components.md`（LC-U2-01〜07 + ビュー型 DataContract 拡張・依存方向）

**回答サマリ**: 全 5 問 ★A。適用性評価（キャッシュ/キュー/CB/ロック/スケール=N/A）同意。Q2 の「(a) 出自秘匿=型で排除」が U2 設計の要。

---

## 設計パターン適用性評価（U2）
| 論点 | 適用 | 方針 |
|---|---|---|
| **認証/認可** | **適用（軽量）** | トークン=資格の検証点（Basic 認証なし）。`/api/*` 入口での token 解決。→ Q1 |
| **秘匿/データ保護** | **適用（U2 固有・最重要）** | (a) 出自秘匿の強制点＝ItemView 構造化、(b) トークン非ログの強制点＝相関ハッシュ、(c) no-store。→ Q2 |
| **純粋ドメインロジック** | **適用** | `derive_phase`（純粋述語）・`select_likert_targets`（純関数）。→ Q3 |
| **一貫性/冪等** | **適用** | DB 側一意制約（judgment/likert）+ 完了順序のサーバ確認。→ Q4 |
| **エラー処理/UI 契約** | **適用** | 統一エラー封筒 + 楽観更新なしのサーバ権威契約。→ Q5 |
| キャッシュ/キュー/CB/ロック/スケール | **N/A** | 小規模・同期・単独研究者・同時数名（U1/U4a と同方針）。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【認証/認可】トークン検証の配置
参加者 API はトークン自体が資格（Basic 認証なし, U2-NFR-01）。
- **★A（推奨）**: **`/api/*` ディスパッチ入口で token を解決し `get_token` で検証する共通ステップを 1 箇所**に置く（U4a の認証チョークポイント DP-U4a-01 と対をなす軽量版）。各ハンドラは検証済みトークン/状態を受け取る。無効/completed の一次判定を入口に集約し、検証漏れのエンドポイントを構造的に作らない。ただし「completed で拒否 vs 完了画面表示」等の**状態別分岐はハンドラ側**（GET session は完了画面、POST 系は拒否）。
- **B**: 各ハンドラ内で個別に `get_token`。→ 付け忘れ・分岐の重複リスク。

[Answer]: A — `/api/*` ディスパッチ入口で token 解決 + `get_token` 検証を 1 箇所に集約。状態別分岐（GET session は完了画面 / POST 系は拒否）はハンドラ側。補足: U4a 認証チョークポイント（DP-U4a-01）の軽量版。「一次判定は入口・状態別分岐はハンドラ」の責務分割で、GET/POST の completed 挙動差（BR-U2-25 vs 拒否）を検証漏れなく収める。

### Q2【秘匿/データ保護】3 つの秘匿を「構造で守る」強制点
U2 固有の最重要。(a) 出自秘匿、(b) トークン非ログ、(c) no-store を規律ではなく構造で担保する。
- **★A（推奨）**:
  - **(a) 出自秘匿＝型で排除**: 参加者向けレスポンスは **`ItemView = {item_id, body}` 等のビュー型のみ**を通し、`Item`（layer/body_ref 込み）を直接シリアライズしない。**Serializer 境界（domain→view への写像を 1 箇所）**で layer/body_ref/seed/exposure_snapshot を構造的に落とす（型に存在しない＝事故で出せない, U2-NFR-06）。
  - **(b) トークン非ログ＝単一ラッパ**: 参加者系ログは U1 `emit` を**許可フィールド限定で呼ぶ薄いラッパ**（`backend/participant/log.py`）を通し、相関は**トークンのハッシュ（SHA-256 先頭 8 文字・1 箇所のユーティリティ）**のみ（U4a の AdminLog=DP-U4a-02 と同型, U2-NFR-03）。
  - **(c) no-store＝レスポンスヘルパ**: 全 `/api/*` 応答を**共通ヘルパ経由**で生成し `Cache-Control: no-store` を必ず付与（付け忘れ防止, U2-NFR-02）。
- **B**: 各呼び出し側の規律に委ねる。→ 漏出・付け忘れの温床。不採用。

[Answer]: A — (a) 出自秘匿=型で排除（ビュー型のみ通し、domain→view 写像を Serializer 境界 1 箇所に）／(b) トークン非ログ=単一ラッパ + SHA-256 先頭 8 文字の単一ユーティリティ／(c) no-store=共通レスポンスヘルパで必ず付与。補足: (a) の「型で排除」が要 — `Item`（layer/body_ref 込み）を直接シリアライズせず `ItemView={item_id,body}` のみ通すことで **layer は出力型に存在せず事故で出せない**（U2-NFR-06 を型システムで守る最強形）。(b)(c) は DP-U4a-02 / U1 DP-06 と同型の単一強制点。

### Q3【純粋ロジック】フェーズ導出・Likert 選定の LC 位置づけ
- **★A（推奨）**:
  - **`derive_phase(...)` は純粋述語**（副作用なし）。配置はサービス層（`backend/participant/`）だが DB カウントを**引数で受け取り**、I/O は呼び出し側（サービスが Repository で集めて渡す）。これにより PBT（PU2-3 単調性）が純粋関数として可能。
  - **`select_likert_targets(pool, seed, params)` は `backend/domain/` の純関数**（`generate_pairs` と同居）。`likert_fixed_targets` 優先 + seed 層均等補充。決定論（P-6）、PBT（PU2-6）。
  - 既存純関数（`generate_pairs`/`serialize`/`deserialize`/`next_unanswered_index`）を再利用（再実装しない, 層の逆流禁止）。
- **B**: `derive_phase` を Repository/ハンドラ内にインライン（DB を直接触る）。→ PBT 不可・テスト戦略（U2-NFR §7）に反する。

[Answer]: A — `derive_phase` は DB カウントを引数で受け取る純粋述語（I/O は呼び出し側）。`select_likert_targets` は `backend/domain/` の純関数。既存純関数は再利用。補足: 「I/O は呼び出し側・述語は純粋」は AssignmentEngine（LC-02）で確立した型の踏襲で、PU2-3（単調性）を PBT で回すための必須条件。domain 配置は P-6（seed 監査再現）の系譜。

### Q4【一貫性/冪等】冪等と完了順序の担保点
- **★A（推奨）**:
  - **冪等は DB 側**: 判定 `(token,pair_id)`（既存 DP-02）、**Likert `(token,target_ref)` UNIQUE（migration 0003）+ `ON CONFLICT DO NOTHING` + 既存値返却（初回不変）**、**Survey は PK=token で upsert**。アプリ層 check-then-insert に依存しない（U2-NFR-10）。Repository に `insert_likert`/`upsert_survey` を追加。
  - **完了順序はサーバ確認**: `submit_survey` 内で「本番判定全件 ∧ Likert 全対象評定 ∧ survey 行あり」を Repository 集計で確認してから `mark_token_completed`（BR-U2-24/U2-NFR-11）。
  - 同時開始の露出競合は**ロックなし許容**（U2-NFR-12、U1 Q8 と同型）。
- **B**: 冪等をアプリ層で（読んでから書く）。→ 競合窓が残る。不採用。

[Answer]: A — 冪等は DB 側（judgment 既存 / Likert UNIQUE + DO NOTHING 初回不変 / Survey upsert）。完了順序は submit_survey 内のサーバ確認。露出競合はロックなし許容。補足: U1-NFR-04（DB 側保証・check-then-insert 不使用）の一貫適用。Repository 追加は `insert_likert` / `upsert_survey` / 完了確認用の集計読み取り。

### Q5【エラー契約/UI】統一エラー封筒 + サーバ権威（楽観更新なし）
- **★A（推奨）**:
  - **統一封筒**: `/api/*` の業務エラー（無効/completed トークン・不正 pair/choice/rating・フェーズ外）は **200 + `{ok:false, error, phase?}`**（U4a=DP-U4a-07 と同水準）。資格不備（無効トークン）は `ok=false` で明示。
  - **サーバ権威の再同期契約**: すべての送信レスポンスに**更新後の SessionView（phase/next/progress）を載せる**。クライアントは**楽観更新せず**、レスポンスの phase で描画（順序外・フェーズ外はサーバが現行 phase を返し UI が追従, BR-U2-03/29 / U2-NFR-09）。
  - **導出の単調性を契約に**: `derive_phase` は「前フェーズ未完なら現行に留める」ため、二重送信・順序外でも一貫した phase を返す。
- **B**: 個別 HTTP ステータス（409/422 等）+ クライアント側でフェーズ管理。→ サーバ権威（U2-NFR-09）と矛盾・UI 同期が壊れやすい。

[Answer]: A — 業務エラーは 200 + `{ok:false, error, phase?}` 封筒（U4a と同水準）。全送信レスポンスに更新後 SessionView を載せる再同期契約。楽観更新なし。補足: 「送信レスポンス = 常に最新の SessionView」により、順序外・二重送信・フェーズ外のすべてが「サーバの現行 phase に UI が追従」という単一の回復経路に収束（BR-U2-03/29 / U2-NFR-09 の設計化）。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-design-patterns.md`（DP-U2-NN）/ `logical-components.md`（LC-U2-NN + 依存方向）を生成 → 標準 2 択（Request Changes / Continue → **Infrastructure Design〈U2〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
