# U2 Business Rules — 参加者セッション（participant）

U1 の BR-01〜12・U4a の BR-U4a-01〜12 を前提に、U2 固有の規則を **BR-U2-NN** で番号付けする。パラメータは U1 と共有（`session_pairs=40` / `practice_pairs=3` / `likert_items=10` / `k=3` / `cross_layer_min_ratio=0.65` / `inactive_threshold_hours=48`, Negotiable）。

---

## セッション状態機械・フェーズ（Q1=A）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U2-01（5 状態・DB 導出）** | サーバのフェーズ集合は **`practice / judging / likert / survey / done`** の 5 状態。現在フェーズは `sessions.phase`（監査スナップショット）ではなく **DB 実データ（pairs/judgments/likert/survey/token.status）から毎回導出**する（`derive_phase`）。 | Q1 / H-2 |
| **BR-U2-02（教示の UI 前置規約）** | `instruction` はサーバ状態から**除外**。「教示を読み終えたか」は判定行から導出不能のため、**「phase=practice かつ練習判定 0 件」のときクライアントが教示画面を前置**する、を UI 規約として固定。再開時の教示再表示は許容（無害・操作の思い出しに有益）。 | Q1 補足 |
| **BR-U2-03（フェーズ線形性）** | `derive_phase` は「先に来るフェーズに未完があればそこを現行フェーズとする」。これにより順序外送信・フェーズ外操作でも常に正しい現行フェーズを返せる（UI 再同期の基盤, BR-U2-14）。 | Q1 / Q11 |

## 割当・セッション確定（U1 再利用, XC-01 波及）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U2-04（新規開始の原子確定）** | 未使用トークンの初回アクセスで `generate_pairs`（U1）によりペア列を確定し、`save_pair_sequence` で **Session + PairSequence を単一 batch 原子保存**（DP-01）してから `mark_token_in_progress`。半端なペア列を生じさせない。 | US-P01 / DP-01 / BR-09 |
| **BR-U2-05（露出は導出入力）** | 新規開始時の露出は `read_exposure_counts`（H-2 導出・非アクティブ除外 BR-04）を `generate_pairs` に渡す。専用カウンタは持たない。 | XC-01 / H-2 |
| **BR-U2-06（seed 保存・監査再現）** | セッションの `seed` を `sessions` に保存し、ペア列・Likert 対象を決定論的に再現可能にする（P-6）。 | Q3-b / XC-01 |

## 練習（US-P02, Q4=A）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U2-07（練習の位置・判定保存）** | 練習ペアは `generate_pairs` の先頭 `practice_pairs` 件（`is_practice=True`, BR-10）。**練習判定も `judgments` に保存**（冪等・再開に必要）。`judgments` に is_practice 列は追加しない。 | Q4 |
| **BR-U2-08（練習の集計除外）** | 練習/本番の区別は**サーバが `pairs.is_practice` から判定**（クライアント申告不使用, H-3）。集計除外は下流（`derive_exposure`・U3/U4b）が `is_practice` で行う。 | US-P02 / H-3 |
| **BR-U2-09（正解フィードバックなし）** | 優劣は主観評価で正解概念がないため、練習に正解表示はしない（目的は操作習熟のみ）。この意図を教示文言に反映。 | Q4 補足 |
| **BR-U2-10（練習→本番の境界）** | 「練習ペア全件に判定行がある」で practice→judging を導出。 | Q4 / BR-U2-01 |

## 判定送信（US-P03, Q6=A）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U2-11（サーバ帰属・冪等）** | `submit_judgment` は `pair_id` の**トークン帰属を検証**し、**存在しない/他トークンの `pair_id` は拒否**。冪等保存は `insert_judgment`（`ON CONFLICT DO NOTHING` + 既存 choice 返却, DP-02）。再送は二重登録しない。 | US-P03 / DP-02 |
| **BR-U2-12（choice 検証・無回答防止）** | `choice ∈ {A,B}` を検証。選択前送信はクライアントで抑止し、サーバでも不正値を拒否。 | US-P03 |
| **BR-U2-13（進捗の意味論）** | `progress = {done, total}` は**本番判定のみ**（`done`=本番判定済み数, `total`=`session_pairs`）。練習は「練習 x/`practice_pairs`」の別カウント、Likert・アンケートはフェーズ表示で扱い判定進捗に混ぜない。 | US-P04 / Q7 |

## ブリッジ Likert（US-P05, Q3/Q8=A）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U2-14（対象選定・決定論）** | Likert 対象は `select_likert_targets(pool, seed, params)`（純関数）で決定。`target_ref = item_id`。同一 `(pool, seed, params)` → 同一結果（監査リプレイ可能, P-6）。 | Q3 |
| **BR-U2-15（fixed 優先 + 層均等補充）** | `params.likert_fixed_targets`（プールに実在する item_id）を**優先採用**し、不足分を `seed` 由来で**各層均等ランダム補充**（層網羅優先）。件数 = `min(likert_items, |pool|)`。 | Q3 機構 |
| **BR-U2-16（対象は都度導出・非永続）** | Likert 対象は保存せず、リクエスト時に `(現行プール, seed, params)` から都度導出。導出安定性は**実験中のプール凍結（U4a 凍結ガード BR-U4a-03）+ 実験中に params 不変**の運用で担保。 | Q3-b |
| **BR-U2-17（Likert 冪等・初回不変）** | Likert 保存は `UNIQUE(token, target_ref)` + `ON CONFLICT DO NOTHING` + 既存 rating 返却（**初回不変**）。判定（BR-08/DP-02）と同じ「初回を権威・再送は既存返却」に揃える。評定修正 UI は提供しない。 | Q8 |
| **BR-U2-18（rating 検証）** | `rating ∈ [1,7]`（`LikertResponse` 契約）。範囲外は拒否。`target_ref` が当該セッションの Likert 対象に含まれることを検証。 | US-P05 |
| **BR-U2-19（方針は Negotiable）** | `likert_fixed_targets` の設定（全固定/混合/全ランダム）と Likert 設問文言は**プール凍結時に確定**（暫定）。 | Q3 / US-P05 |

## 事後アンケート（US-P06, Q9=A）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U2-20（暫定 dict・緩い検証）** | `answers: dict[str, object]` を暫定維持。フロントで暫定設問キー（(i) 経験/熟達度 (ii) ドメイン馴染み/経験様態 (iii) 重視観点 (iv) 年代）を固定、サーバは**必須キー存在チェック程度の緩い検証**。設問最終確定はプール確定後（Negotiable）。 | US-P06 / Q9 |
| **BR-U2-21（Survey upsert）** | Survey 保存は **PK=token で upsert**（完了前の再送・修正で 1 行）。Likert（初回不変）と扱いを分ける理由＝アンケートは提出前の修正が現実的。 | Q8 |

## 完了・再開・再アクセス（US-P07/P08, Q2/Q12=A）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U2-22（ラウンドトリップ対象=DB 行）** | 永続化は **DB 行（sessions + pairs + judgments）のみ**。`SessionState`（pairs + next_index）は XC-02/PBT-02 の論理単位で、別 blob は永続化しない。再開は毎回 DB 行から再構成（`next_index = next_unanswered_index`）。**H-3 の宿題クローズ**。 | Q2 / XC-02 / H-3 |
| **BR-U2-23（再開の非重複）** | 再開時、既回答ペアを重複提示しない（`next_unanswered_index` の導出で保証）。 | US-P08 |
| **BR-U2-24（完了遷移・順序保証）** | `POST /api/survey` 成功時、**本番判定全件 ∧ Likert 全対象評定 ∧ survey 行あり**をサーバ確認してから `mark_token_completed`（in_progress→completed, BR-09）。いずれか未完なら completed にしない。 | Q12 |
| **BR-U2-25（完了後の再アクセス）** | completed トークンの `GET /api/session` は `status=completed` の SessionView（完了画面・判定不可）を返す（US-P01 の「完了済み」挙動と一致）。 | US-P07 / US-P01 |

## セキュリティ衛生・API 境界（XC-03/XC-04, Q5/Q11=A）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U2-26（トークン=資格・接頭辞分離）** | 参加者 API は `/api/*`（`/admin/*` と分離）。**認証はトークン自体**（Basic 認証なし）。無効/存在しないトークンは各エンドポイントで拒否。 | Q5 / US-P01 |
| **BR-U2-27（トークン露出の防御）** | 配布 URL 自体がトークンを含む（US-R05）ため URL 経路の露出は受容済み。実効防御は **(i) 自前ログにトークンを出さない**（AdminLog と同水準を参加者系ログに適用）、**(ii) `/api/*` 応答に `Cache-Control: no-store`**。POST 系のトークンは **body 渡し**で統一。 | Q5 補足 / XC-03 |
| **BR-U2-28（HTTPS・SQLi・CORS）** | HTTPS 強制。全 D1 アクセスは Repository のパラメータ化クエリ（SQLi 対策, BR-12/DP-04）。CORS は同一オリジン配信前提（詳細は Infrastructure Design）。 | XC-03 |
| **BR-U2-29（統一エラー方針）** | 無効トークン=エラー画面 / 完了済み=完了画面 / 再送=クライアント再試行+サーバ冪等 / 重複・順序外=`duplicate` 応答+現行 `next_pair` / フェーズ外=現行 phase 返却で UI 再同期 / 業務エラー=**200 + `ok=false` 封筒**（U4a と同水準）。 | Q11 |
| **BR-U2-30（モバイル/日本語）** | 主要画面（判定・Likert・アンケート）はモバイルファースト・A/B 縦積みで読みやすく・**日本語のみ**（XC-04, 詳細は frontend-components.md）。 | XC-04 |

---

## 検証・エラー処理サマリ

| 状況 | 挙動 |
|---|---|
| 無効/存在しないトークン | エラー応答（判定へ進めない, BR-U2-26/29） |
| 完了済みトークンの再アクセス | 完了画面（新規回答拒否, BR-U2-25） |
| 判定/Likert の再送（同一キー） | 冪等・初回不変（既存値返却, `duplicate=true`, BR-U2-11/17） |
| 他トークン/不存在の pair_id | 拒否（業務エラー封筒, BR-U2-11） |
| フェーズ外送信（例: judging 未完で survey） | 現行 phase を返し UI 再同期・completed にしない（BR-U2-03/24/29） |
| choice/rating の不正値 | 拒否（BR-U2-12/18） |
| ネットワーク送信失敗 | クライアント再試行、サーバ冪等で 1 件保存（BR-U2-11/29） |
