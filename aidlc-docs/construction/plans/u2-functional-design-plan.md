# U2 Functional Design Plan — 参加者セッション（participant）

**ユニット**: U2（`C-FE-PART` / `C-SVC-SESSION` / `C-SVC-RESPONSE` / `C-SVC-SURVEY` / `C-API`〈参加者系〉）
**目的**: 評価者の線形ウィザード（アクセス→教示→練習→判定→Likert→アンケート→完了/再開）の業務ロジックを設計する。対象ストーリー **US-P01〜US-P08**、横断制約 **XC-02（状態ラウンドトリップ）・XC-04（モバイル/日本語）**、波及 **XC-01（割当）・XC-03（トークン衛生）**。
**前提（既決）**: U1 完了（schema・Repository・AssignmentEngine・Serializer 確定）、U4a 完了（管理 API・Basic 認証・pool_ingest / token_issue、`Item.body` を D1 格納）。参加者フローは実データ（投入済みプール・発行済みトークン）に対して動作する。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `business-logic-model.md` / `business-rules.md` / `domain-entities.md` / `frontend-components.md`（UI ありのため生成）を作成します。

---

## 中核論点（このユニットの肝）

U1/U4a が土台（データ契約・I/O 境界・割当純関数・シリアライザ・管理境界）を提供済みのため、**U2 は既存部品の組み合わせと薄いサービス層が中心**。ただし U1 に無い新規設計が 3 点あり、ここが本設計の肝:

1. **セッション・フェーズ状態機械の駆動**（instruction→practice→judging→likert→survey→done）。`sessions.phase` 列を明示 UPDATE するか、DB の判定・回答カウントから毎回導出するか。**H-3（`is_practice` サーバ判定 + XC-02 ラウンドトリップ対象の確定）に直結**。→ **Q1/Q2 が最重要**。
2. **ブリッジ Likert 対象の選定ロジック**。`generate_pairs`（U1）は Likert 対象を返さない。誰が・どう・決定論的に選ぶか（BT 較正アンカーとしての妥当性 US-P05）。→ **Q3 が最重要**。
3. **参加者 API 境界**。管理系（U4a `/admin/*` + Basic 認証）と異なり、**トークンそのものが資格**（Basic 認証なし）。ルート接頭辞・エンドポイント・トークン受け渡し・冪等応答の形を確定する。

**U1 が既に提供しており U2 では再設計しないもの**（前提として固定）:
- ペア列生成（`generate_pairs`：先頭 `practice_pairs` 件が練習、層間比率・露出均衡・位置一様割当まで内包）。
- 露出導出（`derive_exposure` / `read_exposure_counts`：H-2 導出方式・非アクティブ除外 BR-04）。
- 原子確定（`save_pair_sequence`：Session + PairSequence を単一 batch, DP-01）。
- 冪等判定保存（`insert_judgment`：`ON CONFLICT DO NOTHING` + 既存 choice 返却, DP-02）。
- 再開位置導出（`next_unanswered_index(pairs, answered_pair_ids)`）と XC-02 シリアライザ（`serialize`/`deserialize`, `SessionState = pairs + next_index`）。
- トークン状態遷移（`get_token` / `mark_token_in_progress` / `mark_token_completed` / `touch_token`、一方向 BR-09）。

## スコープ境界
- **U2 に含む**: 参加者 API エンドポイント群（`entry.py` へ配線）、`backend/participant/`（SessionService / ResponseService / SurveyService の薄いオーケストレーション）、`frontend/`（参加者ウィザード UI・バニラ JS）、Likert 対象選定の新規純関数（`backend/domain/` に追加想定）、必要なら Repository への読み取り追加（回答済み判定・Likert/Survey 保存）。
- **U2 に含まない**: 研究者管理 UI・進捗モニタリング・エクスポート・暫定勝率（U3）、`bt_aggregate`（U4b）、Likert 設問の最終文言・アンケート設問の最終確定（プール確定後・Negotiable）。
- **依存**: U1 の公開面（schema・Repository・AssignmentEngine・Serializer）と U4a が投入したデータのみ。**層の逆流禁止**（`backend/participant` → `backend/domain`/`backend/repo`/`schema` の一方向）。

---

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-14）

- [x] `construction/u2/functional-design/business-logic-model.md`（5 状態機械・derive_phase・start_or_resume / 送信フロー・select_likert_targets・XC-02 クローズ・Testable Properties PU2-1〜8・U1 波及スコープ）
- [x] `construction/u2/functional-design/business-rules.md`（BR-U2-01〜30: フェーズ導出/教示前置、練習判定保存・集計除外、判定/Likert 冪等、進捗意味論、Likert 選定機構、完了順序保証、トークン露出防御・統一エラー）
- [x] `construction/u2/functional-design/domain-entities.md`（ビュー型 SessionView/PairView/ItemView/LikertTargetView/SubmitResult、U1 波及= AssignmentParams.likert_fixed_targets / migration 0003 UNIQUE、出自の非公開）
- [x] `construction/u2/functional-design/frontend-components.md`（画面階層＝5 フェーズ、サーバ権威の状態管理、操作フロー、フォーム検証、API 結合点、モバイル/日本語 XC-04）

**回答サマリ**: Q1/2/4/5/6/7/8/9/10/11/12=A、**Q3=X（選定機構を実装・方針はプール凍結時確定 / `likert_fixed_targets` 追加）**、Q3-b=A。Q1=5 状態機械（instruction 除外・UI 前置）、Q2 で **H-3 宿題クローズ**、Q8=Likert は初回不変・Survey は upsert（migration 0003）。

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【最重要・フェーズ状態機械】`sessions.phase` を明示保存するか導出するか
参加者は instruction→practice→judging→likert→survey→done を線形に進む。現在位置（phase）の真実をどこに置くか。
- **★A（推奨）**: **DB の実データから毎回導出**（H-2「単一の真実」と一貫）。判定済み本番ペア数 / Likert 回答数 / survey 行の有無から現在フェーズを算出する純粋な述語を置く。`sessions.phase` 列は監査スナップショット（開始時値）に留め、遷移判定の権威にはしない。教示・練習の完了だけは判定行から一意に導けないため、その扱いを Q4 で確定。
- **B**: 各遷移で `sessions.phase` を UPDATE し、それを権威とする。→ 更新漏れで実データと乖離するリスク（H-2 が露出で退けた方式と同型の弱点）。
- **C**: クライアントが phase を保持・申告。→ H-3 の方針（クライアント申告を信用しない）に反するため非推奨。

[Answer]: A — DB 実データから毎回導出（`sessions.phase` は監査スナップショットに留める）。**補足**: 教示完了は判定行から導出不能のため、**サーバの phase 集合から `instruction` を外し 5 状態（practice / judging / likert / survey / done）とする**。「phase=practice かつ練習判定 0 件」でクライアントが教示画面を前置する、を UI 規約として固定。再開時の教示再表示は無害（操作の思い出しに有益）。

### Q2【最重要・XC-02】再開（US-P08）とラウンドトリップ対象の確定
H-3 の宿題「XC-02 のラウンドトリップ対象は `SessionView` か DB 行の復元か」を確定する。
- **★A（推奨）**: **永続化は DB 行（sessions + pairs + judgments）のみ**とし、再開は毎回それらから再構成する。`SessionState`（= 確定 pairs + `next_index`）は「保存前後で論理的に等価」を保証すべき**論理単位**として XC-02/PBT-02 で検証（既存 `serialize`/`deserialize` を使用）。`next_index` は `next_unanswered_index(pairs, 回答済み pair_id 集合)` で導出（既存部品）。別途 `SessionState` の JSON blob は**永続化しない**（単一の真実）。
- **B**: セッションごとに `SessionState` を JSON blob として保存し、再開時にそれを復元。→ pairs/judgments と二重管理になり乖離リスク。
- 備考: 再開時に既回答ペアを重複提示しない（US-P08 チェックリスト）を A の導出で満たす。

[Answer]: A — 永続化は DB 行（sessions + pairs + judgments）のみ、再開は毎回再構成。`SessionState`（pairs + next_index）は XC-02/PBT-02 で検証する論理単位（`serialize`/`deserialize` 使用）、JSON blob は永続化しない。既回答ペアの非重複提示は `next_unanswered_index` の導出で満たす。**→ これをもって H-3 の宿題（ラウンドトリップ対象の確定）はクローズ**。

### Q3【最重要・Likert 較正】ブリッジ Likert 対象の選定ロジック
`generate_pairs` は Likert 対象を返さない。`likert_items`（既定 10）件の対象をどう選び、どこに固定するか。`LikertResponse.target_ref` に何を入れるか。
- **★A（推奨）**: **セッション組立時に決定論的純関数 `select_likert_targets(pool, seed, params)` を `backend/domain/` に追加**し、`target_ref = item_id`。選定はセッションの `seed` 由来で**監査リプレイ可能**（P-6 と一貫）。較正アンカーの妥当性のため**各層からなるべく均等に**選ぶ（層網羅を優先）。対象の固定は Q3-b で確定。
- **B**: Likert 対象を判定ペアと独立に扱わず、判定に使った item から事後にサンプリング。→ セッション横断の較正網羅が保証しにくい。

**Q3-b（対象の固定先）**:
- **★A（推奨）**: **保存せず、リクエスト時に `(現行プール, seed)` から都度導出**（H-2 導出方式と一貫、プールは実験中凍結＝U4a 凍結ガードで担保）。新テーブル不要。
- **B**: セッション確定時に対象 item_id 群を `sessions` の JSON 列か新テーブルへ永続化。→ 明示的だが U1 スキーマ波及（migration）が発生。

[Answer]: **X（★A を修正）— 選定「機構」を今実装し、選定「方針」はプール凍結時に確定する**。
- 機構: ★A のシグネチャどおり `select_likert_targets(pool, seed, params)` を `backend/domain/` に純関数追加、`target_ref = item_id`、seed 由来で監査リプレイ可能（P-6 と一貫）。
- **params 拡張**: `likert_fixed_targets: list[item_id] | None` を追加。**固定リスト優先 + 不足分を seed 層均等ランダムで補充**の両対応。
- 方針は Negotiable（プール凍結時に確定）: 全固定 / 混合 / 全ランダム。
- ★A（全ランダム）修正の理由: 約 40〜50 セッション×10 = 400〜500 評定が 95 項目に薄く分散（1 項目 3〜5 評定）すると項目別 Likert 平均が不安定になり、かつ「誰がどの項目を評定したか」が参加者ごとに異なり評価者効果（甘辛）が項目平均に交絡する。固定アンカー方式（全員が同一項目を評定）は 1 項目≈40 評定で安定し、評価者効果が全アンカーに等しく乗り較正がクリーン。ただし固定項目の選択はプールの中身を見て行うべきで現時点の確定は早計 → 機構のみ先行実装。

**Q3-b**: A — 保存せず、リクエスト時に `(現行プール, seed, params)` から都度導出。固定リストは設定値（params）＝導出入力の一部。導出の安定性は「実験中のプール凍結（U4a 凍結ガード）+ 実験中に params 不変」の運用で担保（記録: 実験途中の params 変更は再開セッションの Likert 対象を変えうる）。

### Q4 練習フェーズの扱い（判定の保存・フィードバック・完了境界）
`generate_pairs` は先頭 `practice_pairs`（既定 3）件を `is_practice=True` で返す（既決）。
- **★A（推奨）**: **練習判定も `judgments` に保存**（冪等・再開に必要）。集計除外は `pairs.is_practice=1` をサーバが引いて判断（H-3・`derive_exposure`/`updated_exposure` の既存扱いと一貫、`judgments` に is_practice 列は追加しない）。**練習に正解フィードバックは出さない**（優劣は主観評価で正解概念がないため、操作習熟のみが目的）。練習→本番の境界は「練習ペア全件に判定行がある」で判定。
- **B**: 練習判定は保存せず破棄（クライアント内で完結）。→ 途中離脱後の再開でどこまで練習したか復元できない。

[Answer]: A — 練習判定も `judgments` に保存（冪等・再開に必要）。集計除外はサーバが `pairs.is_practice` から判断（is_practice 列は追加しない）。正解フィードバックなし。境界＝練習ペア全件に判定行。**補足**: 優劣は主観評価で正解概念がない＝練習の目的は操作習熟のみ、という理由付けを教示文言にも反映。

### Q5 参加者 API サーフェス（ルート接頭辞・エンドポイント・トークン受け渡し）
管理系（`/admin/*` + Basic 認証）と分離した参加者系の接続方式。
- **★A（推奨）**: 接頭辞 **`/api/*`**（`entry.py` に `/api/` 分岐を追加、`/admin/` と同じ raw workers ディスパッチ様式）。**認証は Basic ではなくトークン自体**（無効トークンは各エンドポイントで拒否）。エンドポイント案:
  - `GET  /api/session?token=…` — `start_or_resume` + `get_state` 統合。`SessionView` を返す（status / phase / next_pair / progress）。未使用トークンならここでペア列を確定・保存し in_progress へ。
  - `POST /api/judgment` `{token, pair_id, choice}` — 冪等保存、`SubmitResult` を返す。
  - `POST /api/likert` `{token, target_ref, rating}` — Likert 保存。
  - `POST /api/survey` `{token, answers}` — アンケート保存 + 完了遷移（Q12）。
  - サーバが `SessionView`/`SubmitResult` に次アクション（phase・next_pair・progress）を載せ、**クライアントは薄く**（サーバ権威）。
- **B**: トークンをパスに（`/api/session/{token}`）。→ アクセスログ・キャッシュにトークンが残りやすく秘匿上不利。
- **C**: 単一 RPC 風エンドポイントに action を載せる。→ REST 的可読性・冪等単位の分離が弱い。

[Answer]: A — 接頭辞 `/api/*`、認証はトークン自体、4 本（GET session / POST judgment・likert・survey）、サーバ権威の SessionView/SubmitResult。**補足（トークンのクエリ露出の理屈・business-rules に明記）**: クエリ文字列もログに残りうるが、**配布 URL 自体がトークンを含む設計（US-R05）ゆえ URL 経路の露出は既に受容済み**。実効防御は (i) 自前ログにトークンを出さない（AdminLog と同水準を参加者系ログにも適用）、(ii) `/api/*` 応答に `Cache-Control: no-store`。POST 系のトークンは body 渡しで統一。

### Q6 `submit_judgment` のサーバ判定と冪等応答
- **★A（推奨）**: サーバは `pair_id` から保存済み `pairs` 行を引き、**(i) そのトークンに属するか (ii) `is_practice` か**を判定（H-3・クライアント申告不使用）。冪等は既存 `insert_judgment`（既存 choice 返却）。応答 `SubmitResult = {saved: bool, duplicate: bool, choice, next_pair: PairView|None, phase, progress}`。他トークンの `pair_id` や存在しない `pair_id` は拒否（400/404 相当・業務エラー封筒）。選択前送信はクライアントで抑止（US-P03）かつサーバは `choice ∈ {A,B}` を検証。
- **B**: `is_practice` をクライアントから受け取る。→ H-3 に反する。

[Answer]: A — `pair_id` の帰属・`is_practice` をサーバが `pairs` 行から判定（クライアント申告不使用）。冪等は既存 `insert_judgment`。`SubmitResult = {saved, duplicate, choice, next_pair, phase, progress}`。他トークンの/存在しない `pair_id` は拒否、`choice ∈ {A,B}` を検証。

### Q7 進捗（US-P04）の意味論
`SessionView.progress = {done, total}` の範囲。
- **★A（推奨）**: **本番判定のみ**（`done` = 本番ペアの判定済み数、`total` = `session_pairs`）。練習は「練習 x/3」として別表示、Likert・アンケートはフェーズ表示で扱い、判定進捗バーには混ぜない（25〜35 分の見通しは本番判定が主）。
- **B**: 全ステップ（練習+本番+Likert+アンケート）を分母に含める統合進捗。→ 見通しが実タスク量とずれやすい。

[Answer]: A — `progress` は本番判定のみ（done/total = 本番判定済み数 / `session_pairs`）。練習は「練習 x/3」の別表示、Likert・アンケートはフェーズ表示。

### Q8 Likert / 事後アンケート保存の冪等性
`likert_responses` は現状 UNIQUE 制約なし（多重挿入可）、`survey_responses` は PK=token。
- **★A（推奨）**: **Likert は `(token, target_ref)` で冪等化**（`UNIQUE(token, target_ref)` を追加、`ON CONFLICT DO NOTHING` または最新で upsert）。**Survey は PK=token で upsert**（再送・修正で 1 行）。再送安全性を判定と同じ水準に揃える。→ **U1 波及**: `migrations/0003_*.sql`（likert UNIQUE 追加）+ Repository に保存メソッド追加（`insert_likert`/`upsert_survey`）を U2 スコープに含む。
- **B**: 冪等化せず素朴に INSERT。→ ネットワーク再送で二重計上（US-P03 の冪等方針と不整合）。

[Answer]: A — Likert は `UNIQUE(token, target_ref)`、Survey は PK=token で upsert。**migration 0003 + Repository 保存メソッドを U2 スコープに含む**。**補足（衝突セマンティクス）**: **Likert の衝突は `ON CONFLICT DO NOTHING` + 既存 rating 返却（初回不変）**とし、判定（BR-08/DP-02）と同じ「初回を権威・再送は既存返却」に揃える。線形ウィザードで評定修正 UI は提供しないため最新 upsert の可変性は不要。**Survey のみ upsert**（完了前の再送・修正が現実的にありうるため）。

### Q9 事後アンケートの構造（暫定維持の確認）
`SurveyResponse.answers: dict[str, object]`（既存・暫定）。
- **★A（推奨）**: **暫定維持**。フロントで暫定設問キー（(i) なぞかけ経験/自己申告熟達度、(ii) ドメイン馴染み/経験様態、(iii) 判定時に重視した観点、(iv) 年代程度のデモグラフィック＝US-P06）を固定し、サーバは**緩く検証**（必須キーの存在チェック程度、型は object 許容）。最終確定はプール確定後（Negotiable）。
- **B**: いま設問スキーマを厳密 Pydantic 化。→ プール未確定の段階で早すぎる硬直化。

[Answer]: A — `answers: dict` の暫定維持。フロントで暫定設問キー（(i) 経験/熟達度 (ii) ドメイン馴染み/経験様態 (iii) 重視観点 (iv) 年代）を固定、サーバは必須キー存在チェック程度の緩い検証。最終確定はプール確定後（Negotiable）。

### Q10 フロントエンド構成（C-FE-PART）
- **★A（推奨）**: **単一 HTML + バニラ JS の SPA ウィザード**（フレームワーク不使用・静的配信）。画面＝フェーズ（教示 / 練習 / 判定 / Likert / アンケート / 完了）。**状態はサーバ権威**（各遷移で `SessionView` を取得して描画）、クライアントは **localStorage にトークンのみ**保持（URL 消失時の再開補助）。**モバイルファースト・A/B 縦積み・日本語のみ**（XC-04）。`fetch` で `/api/*`。送信失敗時はクライアント再試行（サーバ冪等で二重登録なし）。
- **B**: マルチページ（フェーズごとに別 HTML + サーバレンダリング）。→ Workers 静的配信・状態同期がかえって複雑。
- 備考: フロント配信方法（Worker から静的アセット返却 / Cloudflare Pages 併用等）は Infrastructure Design で確定。本 FD では UI 論理（コンポーネント階層・状態・API 結合点・検証）に集中。

[Answer]: A — 単一 HTML + バニラ JS の SPA ウィザード（画面=フェーズ）。状態はサーバ権威、クライアントは localStorage にトークンのみ。モバイルファースト・A/B 縦積み・日本語のみ。配信方法は Infrastructure Design で確定。

### Q11 エラー処理・境界シナリオ
- **★A（推奨）**: 統一方針:
  - 無効/存在しないトークン → エラー画面（判定へ進めない、US-P01）。
  - 完了済みトークン → 完了画面（新規回答拒否、US-P01/P07 整合）。
  - 送信のネットワーク失敗 → クライアント再試行（サーバ冪等で 1 件保存、US-P03）。
  - 既回答ペアへの再送・順序外送信 → 冪等応答（`duplicate=true` + 現行 `next_pair`）。
  - フェーズ外操作（例: judging 未完で survey 送信） → サーバが現行 phase を返し UI を再同期（サーバ権威）。
  - 業務エラーは U4a と同様に **200 + `ok=false` + 内訳**の統一封筒、資格不備（無効トークン）は明確なエラー応答。
- **B**: エンドポイントごとに個別方針。→ 一貫性が崩れテストしにくい。

[Answer]: A — 統一方針（無効トークン=エラー画面 / 完了済み=完了画面 / 再送=クライアント再試行+サーバ冪等 / 重複・順序外=`duplicate` 応答+`next_pair` / フェーズ外=現行 phase 返却で UI 再同期 / 業務エラー=200+`ok=false` 封筒、資格不備は明確なエラー応答）。

### Q12 完了遷移と再アクセス
- **★A（推奨）**: **`POST /api/survey` 成功時に `mark_token_completed`**（in_progress→completed, BR-09）。以後 `GET /api/session` は `status=completed` の `SessionView`（完了画面・判定不可）を返し、**US-P01 の「完了済み」挙動と一致**。完了は「本番判定・Likert・アンケートがすべて揃った」ことをサーバが確認してから遷移（順序保証）。
- **B**: 別途 `POST /api/complete` を明示エンドポイント化。→ アンケート送信と完了が二段になり離脱時に未完了が残りやすい。

[Answer]: A — `POST /api/survey` 成功時に `mark_token_completed`。完了は「本番判定・Likert・アンケートが全部揃った」ことをサーバ確認後（順序保証）。以後の `GET /api/session` は `status=completed` の SessionView（判定不可、US-P01 と一致）。

---

**回答後の流れ**: 回答の曖昧さを点検（曖昧なら追加質問）→ Part 2 で 4 成果物（business-logic-model / business-rules / domain-entities / frontend-components）を生成 → 標準 2 択（Request Changes / Continue → **NFR Requirements〈U2〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す（監査証跡の自己完結・メモリ方針）。
