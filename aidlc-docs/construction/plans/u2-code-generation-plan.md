# U2 Code Generation Plan — 参加者セッション（participant）

**ユニット**: U2（C-FE-PART / C-SVC-SESSION / C-SVC-RESPONSE / C-SVC-SURVEY / C-API〈参加者系〉）
**前段**: Functional Design / NFR Requirements / NFR Design / Infrastructure Design — すべて承認済み（2026-07-14）。
**目的**: LC-U2（ParticipantApi / Session・Response・Survey Service / ViewSerializer / ParticipantLog / LikertSelector / ParticipantFrontend）を実コードに落とす。**U1 波及**（`AssignmentParams.likert_fixed_targets` 追加・migration 0003）と **既存 U1/U4a テストの回帰確認**も対象。

> 実装規約（G-1 確定）: raw workers API + Pydantic v2 / module-level `on_fetch` / uv+pywrangler / CI デプロイ / `workers_dev=true`。トップレベル import 最小限（10021 回避、重い import は関数内）。

このドキュメントは **Part 1（Plan + 決定点）**。承認後 Part 2 で本計画を**単一の真実**として生成する。

---

## 1. ユニット・コンテキスト

| 項目 | 内容 |
|---|---|
| **実装ストーリー** | US-P01（トークンアクセス）/ P02（教示・練習）/ P03（判定送信・冪等）/ P04（進捗）/ P05（ブリッジ Likert）/ P06（アンケート）/ P07（完了）/ P08（中断・再開）。横断 XC-02（ラウンドトリップ）・XC-03（衛生）・XC-04（モバイル/日本語）。波及 XC-01（割当・U1 再利用）。 |
| **依存** | U1 公開面（schema / Repository / `generate_pairs` / `serialize`/`deserialize`/`next_unanswered_index`）、U4a（投入データ・`Item.body`・同一 Worker）。**層の逆流禁止**（`backend/participant` → domain/repo/schema 一方向）。 |
| **所有 D1 エンティティ** | なし（全テーブルは U1 所有）。U2 は `likert_responses` に **UNIQUE 制約を追加**（migration 0003）。 |
| **サービス境界** | 参加者フローのオーケストレーション。実 D1 I/O は Repository、純ロジックは domain / phase 述語 / ViewSerializer。 |

**スコープ外**: 管理 UI・エクスポート・暫定勝率（U3）、`bt_aggregate`（U4b）、Likert 設問文言・アンケート最終確定（プール凍結時・Negotiable）。

---

## 2. 生成ステップ（番号付き・Part 2 の単一の真実）

- [x] **Step 1 — beta 検証（Static Assets × Python Workers, Infra §6-β）**: `wrangler.toml` に最小 `[assets]`（`frontend/` に placeholder 1 枚）+ `on_fetch` に `/api/ping` を置き、**smoke 流儀の実機確認**で ① アセット/`on_fetch` 実行順（`/api/*` は Worker 到達）② `[assets]` 設定キー（directory/binding）と deploy 同梱 ③ `run_worker_first` 相当の要否 を確定・記録。**この Claude 環境は Cloudflare 認証不可のため、リモート実機確認はユーザー側で実行実績を提示**（U4a integration と同流儀）。想定外→是正 / Static Assets 併用不能のみ **C（Worker 埋め込み配信）**へ、B（Pages）は最後の手段（Q5）。SPA フォールバックは不使用のため検証対象外（Infra Q2）。
- [x] **Step 2 — schema 波及（params 拡張）**: `schema/models.py` の `AssignmentParams` に `likert_fixed_targets: list[str] | None = None` 追加（frozen 維持・デフォルト None で既存呼び出し不変）。`schema/__init__` 公開面確認。
- [x] **Step 3 — schema ビュー型（レスポンス契約・出自秘匿）**: `schema/views.py`（新規）に `ItemView`（`{item_id, body}` のみ）/ `PairView`（`{pair_id, index, left: ItemView, right: ItemView, is_practice}`）/ `LikertTargetView`（`{target_ref, body, scale}`）/ `SessionView`（`{status, phase, next_pair, next_likert, progress, practice}`）/ `SubmitResult`（`{saved, duplicate, choice, next_pair, phase, progress}`）を定義。**`layer`/`body_ref`/`seed`/`exposure_snapshot` を型に持たせない**（DP-U2-02）。`__init__` に公開。
- [x] **Step 4 — migration 0003**: `migrations/0003_likert_unique.sql`（`likert_responses` に `UNIQUE(token, target_ref)`。新規プロジェクトで既存行なく安全）。適用は versioned（dev→prod、deploy 前）。deploy.yml は無変更（自動適用, Infra §6）。
- [x] **Step 5 — LikertSelector（純関数, domain）**: `backend/domain/likert.py` に `select_likert_targets(pool, seed, params) -> list[str]`（`likert_fixed_targets` 優先 + `Random(seed)` 層均等補充、件数 `min(likert_items, |pool|)`、fixed はプール実在のみ・重複排除）。副作用なし（P-6）。`backend/domain/__init__` に公開。
- [x] **Step 6 — LikertSelector PBT**: `tests/pbt/test_likert_selection.py`（PU2-6, PBT-03 系）: 決定論（同一 seed→同一結果）・fixed 包含・層網羅・件数。
- [x] **Step 7 — Repository 拡張**: `backend/repo/repository.py` に `insert_likert(token, target_ref, rating, now)`（`ON CONFLICT(token,target_ref) DO NOTHING` + 既存 rating 返却=初回不変, DP-U2-06）・`upsert_survey(token, answers, now)`（PK=token upsert）・`answered_pair_ids(token)`（判定済み集合）・`answered_likert_refs(token)`（Likert 済み集合）・`get_pairs(token)`（確定ペア列）・`get_survey(token)`（存在確認）。全パラメータ化クエリ。既存メソッド再利用。
- [x] **Step 8 — derive_phase（純粋述語, participant）**: `backend/participant/phase.py` に `derive_phase(pairs, answered_pair_ids, likert_targets, answered_likert_refs, survey_exists, token_status) -> SessionPhase`（5 状態、BR-U2-01/03、線形性=前フェーズ未完なら現行に留める）。副作用なし。
- [x] **Step 9 — derive_phase PBT**: `tests/pbt/test_phase.py`（PU2-3）: 送信を進めるほど practice→…→done を後戻りしない単調性。
- [x] **Step 10 — ParticipantLog（秘匿ラッパ + ハッシュ util）**: `backend/participant/log.py`。U1 `emit` を許可フィールド限定で呼ぶラッパ + `token_hash(token) -> str`（SHA-256 先頭 8 文字・単一ユーティリティ, DP-U2-03）。token 生値・本文を構造的に排除。
- [x] **Step 11 — ViewSerializer（出自秘匿の一点集約, participant）**: `backend/participant/view.py`。`Item→ItemView`・`Pair→PairView`（本文は `list_items` 由来）・`SessionView` 合成・`SubmitResult` 合成。**domain→view 写像を 1 箇所**に集約し出自を落とす（DP-U2-02）。純粋。
- [x] **Step 12 — Services（Session/Response/Survey）**: `backend/participant/session.py`（`start_or_resume`：unused=generate_pairs→save_pair_sequence→mark_in_progress、in_progress=DB 再構成、completed=完了 view / seed は決定点 Q1）、`response.py`（`submit_judgment`：pair 帰属・is_practice サーバ判定→insert_judgment→SubmitResult）、`survey.py`（`submit_likert` 初回不変 / `submit_survey` upsert + 完了順序サーバ確認→mark_completed）。`touch_token` を各操作で。
- [x] **Step 13 — ParticipantApi + entry.py 配線**: `backend/participant/api.py`（`/api/session`・`/api/judgment`・`/api/likert`・`/api/survey` のディスパッチ、**入口トークン検証チョークポイント** DP-U2-01、**no-store 共通レスポンスヘルパ** DP-U2-04、統一エラー封筒 DP-U2-07）。`backend/entry.py` の `on_fetch` に `/api/*` 分岐追加（既存 `/admin/*`・ヘルスは維持）。
- [x] **Step 14 — frontend SPA**: `frontend/index.html`（アプリシェル）・`frontend/app.js`（フェーズ駆動ウィザード・サーバ権威・localStorage はトークンのみ・**楽観更新なし**・`fetch /api/*`・失敗再試行）・`frontend/styles.css`（モバイルファースト・A/B 縦積み・日本語・合理的 a11y）。**`data-testid` を対話要素に付与**（automation-friendly, 例 `judging-choice-a-button`）。`wrangler.toml` に `[assets]`（Step 1 の検証結果を反映）。
- [x] **Step 15 — integration テスト**: `tests/integration/` 流用・拡張。実 D1・`/api/*` 越しに参加者フロー一巡（PU2-2 再開の非重複 / PU2-4 判定冪等 / PU2-5 練習の集計除外整合 / PU2-7 Likert 初回不変 / PU2-8 完了順序保証）。ドライバは U1/U4a ハーネス流用。実行実績提示。
- [x] **Step 16 — U1/U4a 回帰 + Documentation**: 既存 unit+PBT（U1 19 + U4a 8 系）を緑に保つ（`AssignmentParams` 追加は default None で不変の想定を確認、`serialize`/`deserialize` の SessionState ラウンドトリップ PU2-1 は既存 serializer で担保）。`aidlc-docs/construction/u2/code/README.md` にサマリ・公開面・API 一覧・beta 検証結果・PU2-1〜8 の PBT/integration 対応。README のディレクトリ構成に `backend/participant`・`frontend` 反映。

---

## 3. Part 1 決定点（★推奨デフォルト付き。回答は各 [Answer] に記入）

### Q1【seed 生成】新規セッションの決定論シード
FD §3.2 で「生成方法は Code Generation で確定」とした。
- **★A（推奨）**: **トークン由来の決定論シード**（`seed = int(SHA-256(token) の先頭 8 バイト)`）。同一トークンなら常に同一ペア列・同一 Likert 対象＝**監査再現性**が最大（P-6）、RNG 状態や `Math.random`（Pyodide 制約）不要。開始は unused→in_progress の一度きりだが、シードが token に紐づくため事後の再現・検証が容易。
- **B**: 乱数シード（`secrets` 由来）を生成し `sessions.seed` に保存。→ 再現には保存値が要る（保存はするが token から独立、監査の自己記述性が下がる）。

[Answer]: A — トークン由来の決定論シード（`seed = int(SHA-256(token) 先頭 8 バイト)`）。**U1 FD Q4=B の生成方法条項の改訂として記録**: Q4=B の本質（seed + exposure_snapshot 保存で完全リプレイ可能）は維持し、**生成方法のみ**を自己記述的（token から再導出可能）に改善。RNG 品質は 128-bit トークンのハッシュゆえ問題なし、seed は参加者レスポンスに非出力（U2-NFR-06）。手続き: audit.md に改訂を記録し、U1 側 `u1/functional-design/business-logic-model.md §4` に改訂注記を追加済み（黙示の上書きにしない）。`sessions.seed` 保存は継続（導出と保存値の一致を監査で検証できる二重化）。

### Q2【derive_phase 配置】純粋述語の置き場
- **★A（推奨）**: **`backend/participant/phase.py`**（サービス層だが**純粋述語**・DB カウントは引数で受領、DP-U2-05）。PU2-3 を PBT で回せる。
- **B**: `backend/domain/` に置く。→ phase はセッション進行の概念で domain（割当）より participant が自然。B も可だが A を推奨。

[Answer]: A — `backend/participant/phase.py`（純粋述語・DB カウントは引数受領）。補足: phase はセッション進行の概念で participant への配置が自然。純粋性維持で PU2-3 の PBT 可能。

### Q3【ViewSerializer 出力】SessionView をどこまでサーバが埋めるか
- **★A（推奨）**: **サーバが next_pair / next_likert / progress / practice をすべて算出して SessionView に載せる**（サーバ権威・楽観更新なし, U2-NFR-09）。クライアントは描画のみ。送信レスポンス（SubmitResult / submit_likert・survey）も**更新後 SessionView 相当**を返し単一の再同期経路（DP-U2-07）。
- **B**: 最小限（phase と生 pairs）だけ返しクライアントが算出。→ サーバ権威・出自秘匿（クライアントに pairs 全体を渡すと出自露出）と矛盾。不採用。

[Answer]: A — サーバが next_pair / next_likert / progress / practice をすべて算出して SessionView に載せる。送信レスポンスも更新後 SessionView 相当を返す（単一の再同期経路）。補足: B（生 pairs をクライアントへ）は出自秘匿（U2-NFR-06）と直接矛盾するため成立しない。

### Q4【frontend 構成】ファイル分割と自動化属性
- **★A（推奨）**: **`index.html` + `app.js` + `styles.css` の 3 ファイル分割**（インライン肥大化を避ける）。対話要素に **`data-testid`**（`{component}-{role}`、例 `session-start-button`/`judging-choice-a-button`/`likert-scale-4-button`/`survey-submit-button`）。ビルド不要（バニラ JS・静的配信）。
- **B**: 単一 HTML にインライン。→ 小さくても保守性・テスト容易性が落ちる。

[Answer]: A — index.html + app.js + styles.css の 3 ファイル分割 + 対話要素に `data-testid`（`{component}-{role}` 規約）。補足: data-testid は将来 E2E 自動化への先行投資。Step 14 が肥大化する場合は「シェル → 画面部品 → API 結合」の内部分割で進めてよい（成果物は同一）。

### Q5【beta 失敗時の分岐】Static Assets が Python Workers と併用不能だった場合
- **★A（推奨・Infra 既決の再掲）**: **是正 → C（Worker が HTML/JS/CSS を `Response` で直接返す埋め込み配信・同一オリジン維持）→ B（Cloudflare Pages 分離＝要 CORS）** の順。C でも `/api/*` ルーティング・出自秘匿・no-store は不変（配信手段のみ差し替え）。Part 2 は Step 1 の結果に応じて Step 14 の配信部分だけ調整。
- **B**: 最初から Worker 埋め込み（C）で作る。→ Static Assets が使えるなら保守性で劣る。まず A を試す。

[Answer]: A — 是正 → C（Worker 埋め込み配信・同一オリジン維持）→ B（Pages 分離）の順（Infra §6-β 既決の再掲）。

### Q6【回帰の扱い】U1/U4a 既存テストの完了基準
- **★A（推奨）**: `AssignmentParams` へのフィールド追加（default None）・migration 0003 が既存を壊さないことを確認し、**既存 unit+PBT（U1 19 + U4a 系）+ U2 追加分をすべて緑**にしてから完了（ブロッキング完了基準）。integration は実 D1 実行実績を提示。
- **B**: U2 追加分のみ検証。→ 回帰見落としリスク。不採用。

[Answer]: A — U1/U4a 既存テスト + U2 追加分の全緑をブロッキング完了基準に。integration は実 D1 実行実績の提示。補足: U4a CG Q4 と同型。`AssignmentParams` 追加は default None で既存呼び出し不変の想定 — これ自体も回帰テストで確認する。

---

## 4. 完了基準
- [x] 全 Step `[x]`。schema ビュー型/params 拡張・migration 0003・domain select_likert_targets・Repository 拡張・`backend/participant/`（phase/log/view/session/response/survey/api）・entry.py 配線・frontend SPA・wrangler `[assets]` が生成。
- [x] **beta 検証（Static Assets × Python Workers）の結果を記録**（想定どおり or 是正/フォールバック）。
- [x] **U1/U4a 回帰含め全テスト緑**（unit+PBT: PU2-1/3/6 追加）、integration（`/api/*` 越し PU2-2/4/5/7/8）実行実績。
- [x] `aidlc-docs/construction/u2/code/README.md` サマリ。README ディレクトリ構成更新。
- [x] 標準 2 択（提示）（Request Changes / Continue → Build & Test〈U2〉）。

---

**Part 2 生成時の運用**: 各 Step を順に生成し完了ごとに `[x]`、対応ストーリーも `[x]`。**本 plan の [Answer] 欄を記入**（監査証跡の自己完結）。beta 検証のリモート実機部分はユーザー実行実績を待ち、コードはフォールバック順に沿って調整可能な形で用意する。
