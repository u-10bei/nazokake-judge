# U4a Functional Design Plan — スクリプト先行分（token_issue / pool_ingest）

**ユニット**: U4a（`C-SCRIPT-TOKEN` / `C-SCRIPT-POOL` + 先行導入する管理 API 境界）
**目的**: US-R05（トークン発行）と US-R06（刺激プール投入、層ラベル必須）の業務ロジックを設計する。U2 の動作確認に不可欠なテストデータ供給と、**H-1=(c)（scripts→Worker 管理 API→D1）の早期検証**を担う。
**前提（既決）**: U1 完了（schema / Repository / トークン契約 `generate_token`/`is_valid_token` 確定）。H-1=(c)：実行時 D1 アクセスは Worker 管理エンドポイント（Basic 認証背後）経由、`SCRIPT→API`。単一データ契約（schema/ Pydantic を HTTP ペイロードにも使用）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `business-logic-model.md` / `business-rules.md` / `domain-entities.md` を生成します（UI なしのため frontend-components は N/A）。

---

## 中核論点（このユニットの肝）

実装順序が **U1 → U4a → U2 → U3 → U4b** のため、**U4a が U2/U3 に先行**する。しかし現状:
- **Worker 側の管理エンドポイント + Basic 認証（C-AUTH）が未実装**（`backend/entry.py` は最小ヘルスのみ）。
- **Repository に token/item の書き込みメソッドが未実装**（`list_items` は読み取りのみ、tokens は状態遷移のみで新規 INSERT なし）。

→ **U4a がこれらを先行導入する**構図。責務境界（どこまで U4a が作り、U2/U3 が何を再利用するか）の確定が本設計の中核。**Q1/Q2 が最重要**。

---

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-13）

- [x] `construction/u4a/functional-design/business-logic-model.md`（token_issue / pool_ingest フロー・構成要素・Testable Properties PU4a-1〜6・U1 波及の変更スコープ）
- [x] `construction/u4a/functional-design/business-rules.md`（BR-U4a-01〜11: 層ラベル/本文必須、凍結ガード、冪等 upsert、プール充足三点セット、トークン一意・秘匿、認証境界）
- [x] `construction/u4a/functional-design/domain-entities.md`（Item 波及=body 格納/body_ref 格下げ、ペイロードモデル ItemIngestRequest/IngestResult/TokenIssueRequest/TokenIssueResult）
- [x] frontend-components: **N/A**（UI なし・CLI + 管理 API）

**回答サマリ**: Q1/2/3/7/8=A。**Q4=A + 凍結ガード必須**（参照済み item への UPDATE 拒否）。**Q5=X（Item.body を D1 格納・body_ref 格下げ・U1 波及=migration 0002 含む）**。**Q6=A + 層間供給可能性の式**（三点セット）。

## スコープ境界
- **U4a に含む**: `scripts/token_issue`・`scripts/pool_ingest`（CLI）、それらが叩く **Worker 管理エンドポイント**（`/admin/*`）+ **Basic 認証**の先行導入、Repository の**書き込みメソッド追加**（insert_tokens/insert_items）。
- **U4a に含まない**: 参加者フロー API・UI（U2）、研究者管理 UI・エクスポート・暫定勝率（U3）、`bt_aggregate`（U4b）。
- **依存**: U1 の公開面（schema / Repository / トークン契約 / LogEmitter）のみ。層の逆流禁止。

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【最重要・責務境界】管理エンドポイント + Basic 認証（C-AUTH）の導入責務
U4a が U2/U3 に先行するため、Worker 側の管理境界を誰が作るか。
- **★A（推奨）**: **U4a が Worker 管理エンドポイント（`/admin/*`）+ Basic 認証ミドルウェアを先行導入**（`backend/admin/` に配置）。H-1(c) の「認証境界一本化」と整合し、U2/U3 は後で同じ Basic 認証を再利用。U4a は実 D1 書き込みを管理 API 経由でしか行えない（H-1(c)）ため不可避。
- **B**: 最小限のみ U4a（tokens/items 投入 2 エンドポイント + 素朴な Basic 認証）、本格的な認証・管理面は U3 で再設計。→ 二重実装・境界の作り直しリスク。
- **C**: U4a は当面 `wrangler d1 execute`/ローカル直投入で回避し、管理 API は U2/U3 まで先送り。→ **H-1(c) の早期検証という U4a 先行の主目的に反する**ため非推奨。

[Answer]:

### Q2【最重要】Repository への書き込みメソッド追加
tokens/items への新規書き込みが U1 に存在しない。
- **★A（推奨）**: Repository に **`insert_tokens(bulk)` / `insert_items(bulk)` を追加**し、**D1 batch で原子投入**（`save_pair_sequence` の実証済みイディオム流用, DP-01）。U1 の I/O 境界に一貫（全 D1 アクセスは Repository 集約）。schema/ モデルで検証してから書き込み。
- **B**: 管理エンドポイント内で個別 INSERT をループ。→ 原子性が弱く、途中失敗で半端投入。
- 備考: U1 の Repository を U4a が拡張する形（U1 コードへの追記）。層の逆流は起きない（Repository は最下層寄り）。

[Answer]:

### Q3 管理 API の粒度 + HTTP ペイロードの schema/ モデル
- **★A（推奨）**: **単一 bulk POST**（`POST /admin/items` = 全件1回、`POST /admin/tokens` = count 指定で一括発行）。約95件=1 POST（INF §4 規模想定）。**リクエスト/レスポンスの Pydantic モデルは schema/ に追加**（`ItemIngestRequest`/`IngestResult`/`TokenIssueRequest`/`TokenIssueResult`）— 単一データ契約（Q6=A）が接続方式にも及ぶ。Worker と scripts が同一モデルを import。
- **B**: 個別 POST（1件ずつ）+ モデルは U4a ローカル。→ ラウンドトリップ増・契約の二重管理。

[Answer]:

### Q4 pool_ingest の冪等性・再投入方針
- **★A（推奨）**: **`item_id` をキーに upsert（`ON CONFLICT(item_id) DO UPDATE`）**。再実行・修正投入が安全（べき等）。刺激プール投入は**実験開始前の運用**である前提。
- **B**: 全置換（`DELETE FROM items` → INSERT）。→ 一括入れ替えは明快だが、既存参照（pairs/judgments）があると危険。
- **C**: 追記のみ（既存 `item_id` は拒否）。→ 修正投入ができず運用が固い。
- 備考: いずれも「参加判定データ（judgments/pairs）が既に存在する item の破壊的更新」をどう扱うかを business-rules で明記（安全ガードの要否）。

[Answer]:

### Q5 pool_ingest の CLI 入力形式 + `body_ref` の実体
- **★A（推奨）**: 入力は **JSON（または JSONL）ファイル**（`[{item_id, layer, body_ref}, ...]`）。schema/ の `validate_item` で層ラベル必須（BR-11）を検証。`body_ref` は**不透明な参照キー/相対パス**（本文実体はリポジトリ・DB 管理外, NFR-08。スクリプトは中身を解決しない）。
- **B**: CSV 入力 / `body_ref` を URL に限定。→ CSV は型・エスケープが弱く Pydantic 契約と乖離。

[Answer]:

### Q6 BR-05 プール充足の事前検証（構成不能の事前排除）
pool_ingest 時に「本番セッションを構成可能か」を事前チェックする述語。
- **★A（推奨）**: **総数 ≥（本番構成に必要な最小数）かつ 各層 ≥ 1（層間比率 0.65 の実行可能性）かつ k 制約下で構成可能**。目安: 総数 ≥ `ceil(2×session_pairs / k)` + 4 層すべて非空。不足は **error ログ + 投入拒否**（参加者アクセス前に弾く）。具体閾値は business-rules に数式で固定。
- **B**: 総件数のみをチェック（層構成は見ない）。→ 層欠けで層間ペアが作れず XC-01 を壊す。

[Answer]:

### Q7 token_issue の入出力
- **★A（推奨）**: CLI 引数で **`count` + ベース URL テンプレート**。トークンは U1 `generate_token()`（128-bit, XC-03）で生成、`tokens`（status=unused, issued_at）へ書き込み。出力は**トークン付き URL 一覧を stdout + ファイル**（テキスト/CSV）。DB 一意制約（PK）で衝突検出、衝突時は**再生成リトライ**。配布用ファイルは秘匿（gitignore・リポジトリ非コミット, NFR-08）。
- **B**: URL 生成は配布側に任せトークン文字列のみ出力。→ US-R05 受入基準（配布可能な URL 一覧）を満たさない。

[Answer]:

### Q8 CLI への認証情報の受け渡し
- **★A（推奨）**: **環境変数**（`ADMIN_BASIC_USER` / `ADMIN_BASIC_PASSWORD`）。本番 Worker 側の `wrangler secret` と同名、ローカルは `.dev.vars`（gitignore）。CLI はこれを読み HTTPS + Basic で管理 API を叩く。
- **B**: 実行時プロンプト / 認証ファイル。→ 自動化しにくい・ファイルは漏洩経路増。

[Answer]:

---

**回答後の流れ**: 回答の曖昧さを点検（曖昧なら追加質問）→ Part 2 で 3 成果物を生成 → 標準 2 択（Request Changes / Continue → NFR Requirements〈U4a〉または Code Generation）。
