# U4a Code Generation Plan — token_issue / pool_ingest（+ 管理 API）

**ユニット**: U4a（C-SCRIPT-TOKEN / C-SCRIPT-POOL + 管理 API 先行導入 + U1 波及）
**前段**: Functional Design / NFR Requirements / NFR Design / Infrastructure Design — すべて承認済み。
**目的**: LC-U4a（AdminApi / AuthGuard / PoolSufficiency / Repository 書込 / AdminLog / CLI）を実コードに落とす。**U1 コードへの追記**（`Item.body`・Repository 書込・entry.py 配線）を含むため、**既存 U1 テストの回帰確認**も対象。

> 実装規約（G-1 確定）: raw workers API + Pydantic v2 / module-level `on_fetch` / uv+pywrangler / CI デプロイ / `workers_dev=true`。トップレベル import 最小限（10021 回避）。

このドキュメントは **Part 1（Plan + 決定点）**。承認後 Part 2 で本計画を単一の真実として生成する。

---

## 1. スコープ

| 種別 | 対象 |
|---|---|
| **U1 波及（Item.body）** | `schema/models.py`（`Item.body: str` 追加, `body_ref` 任意化）・`validate_item`・`migrations/0002_item_body.sql`・`Repository.list_items`・**U1 既存テスト更新** |
| **新規 schema** | ペイロードモデル: `ItemIngestRequest`/`IngestResult`/`RejectedItem`/`TokenIssueRequest`/`TokenIssueResult`/`SufficiencyResult` |
| **新規 domain** | `backend/domain/pool_sufficiency.py`（純粋・単一実装, DP-U4a-05） |
| **Repository 拡張** | `insert_items`（bulk upsert + 凍結ガード）・`insert_tokens`（bulk）・参照済み item_id 読取 |
| **新規 admin** | `backend/admin/`：AdminApi（`/admin/items`,`/admin/tokens` ルーティング）・AuthGuard（Basic, 定数時間）・AdminLog（秘匿ラッパ）。`backend/entry.py` の `on_fetch` に配線 |
| **新規 scripts** | `scripts/pool_ingest`・`scripts/token_issue`（pure-Python CLI, urllib, HTTPS+Basic） |
| **CI/構成** | `deploy.yml` 機能化（RT-1）・`.dev.vars.example` に `ADMIN_BASIC_*` 追記 |
| **テスト** | PBT（pool_sufficiency・トークン一意）・integration（admin 越し）・U1 回帰 |

**スコープ外**: 参加者 UI/API（U2）、管理 UI・エクスポート（U3）、bt_aggregate（U4b）。

---

## 2. 生成ステップ（番号付き・Part 2 の単一の真実）

- [x] **Step 1 — schema 波及（Item.body）**: `Item` に `body: str`（必須, min_length=1）追加、`body_ref: str|None=None`。`validate_item` は層 + body 非空。`schema/__init__` 公開面更新。
- [x] **Step 2 — 新規 schema ペイロードモデル**: `ItemIngestRequest`/`IngestResult`（`inserted/updated/rejected/sufficiency_warnings`）/`RejectedItem`/`TokenIssueRequest`/`TokenIssueResult`（`ok/tokens/issued_at/gate_errors`）/`SufficiencyResult`（`ok/shortfalls`）。`__init__` に公開。
- [x] **Step 3 — migration 0002**: `migrations/0002_item_body.sql`（`items.body TEXT NOT NULL` 追加、`body_ref` NULL 許容化）。適用は migration→deploy の順（Infra §4）。
- [x] **Step 4 — pool_sufficiency（純粋）**: `backend/domain/pool_sufficiency.py`。三点セット（BR-U4a-05）を評価し `SufficiencyResult{ok, shortfalls}` を返す。domain `__init__` に公開。**単一実装**（ingest/issue が呼ぶ, U4a-NFR-10）。
- [x] **Step 5 — pool_sufficiency PBT**: `tests/pbt/` に三点セット境界値・反例探索（PBT-03）。
- [x] **Step 6 — Repository 拡張**: `insert_items`（未参照は upsert / 参照済み UPDATE 拒否=凍結ガード / D1 batch 原子）・`insert_tokens`（bulk batch, status=unused/issued_at）・`referenced_item_ids()`（pairs∪judgments）。`list_items` に body/body_ref。全パラメータ化クエリ。
- [x] **Step 7 — AdminLog（秘匿ラッパ）**: `backend/admin/log.py` 等。許可フィールド（event/level/count/item_id/result）限定で U1 `emit` を呼ぶ。token/body を構造的に排除（DP-U4a-02）。
- [x] **Step 8 — AuthGuard**: `backend/admin/auth.py`。`Authorization: Basic` 復号 → `env.ADMIN_BASIC_*` と定数時間比較（`hmac.compare_digest`）→ 不一致 401 + `WWW-Authenticate`。
- [x] **Step 9 — AdminApi**: `backend/admin/api.py`。`/admin/items`（ItemIngestRequest → validate → 凍結ガード → insert_items → **投入後 pool_sufficiency で warn 判定** → IngestResult）、`/admin/tokens`（**発行時 pool_sufficiency ゲート** → 衝突事前排除 → insert_tokens → TokenIssueResult）。統一エラー封筒（DP-U4a-07）。
- [x] **Step 10 — entry.py 配線**: `on_fetch` で `/admin/*` を AuthGuard（単一チョークポイント）→ AdminApi ディスパッチへ。既存ヘルスは維持。
- [x] **Step 11 — scripts CLI**: `scripts/pool_ingest`（JSON/JSONL 読込・validate・POST /admin/items・結果表示/終了コード）、`scripts/token_issue`（count+URL テンプレ・POST /admin/tokens・URL 一覧を stdout+gitignore ファイル）。urllib + Basic（env 認証）。
- [x] **Step 12 — 構成/CI**: `.dev.vars.example` に `ADMIN_BASIC_USER/PASSWORD`、`.gitignore` に配布物（`*.tokens.txt` 等）。**`deploy.yml` 機能化（RT-1）**: uv sync → test（unit+PBT）→ migrations apply --remote(0001+0002) → deploy。
- [x] **Step 13 — U1 回帰 + U4a テスト**: U1 既存テスト（Item 変更に伴う fixture 更新）を通す。integration（`tests/integration/` 流用・拡張）で admin 越しに PU4a-1/2/3a/3b/5/6 を検証。
- [x] **Step 14 — Documentation**: `aidlc-docs/construction/u4a/code/` にサマリ・公開面・CLI 使い方・RT-1 CLOSE 記録。README のディレクトリ構成に `backend/admin`・`scripts` 反映。

---

## 3. Part 1 決定点（★推奨デフォルト付き）

**回答サマリ**: 全 5 決定点 ★A（2026-07-13 承認）。Part 2 注記=レビュー時に Claude 環境で unit+PBT 実行・integration は実行実績提示、deploy.yml は smoke-test-deploy.yml の教訓（tee パイプで終了コード喪失・URL 抽出フォールバック）を反映。

- **Q1（entry.py 配線）**: ★**A** = `on_fetch` で path 接頭辞 `/admin/*` を **AuthGuard（単一チョークポイント）→ AdminApi** に委譲。参加者ルート（U2）は別接頭辞で後付け。B=admin を別 Worker（NFR-02 で否決済み）。 **[Answer]: A**
- **Q2（凍結ガードの読取位置）**: ★**A** = `referenced_item_ids()` を **`insert_items` 内・投入 batch の直前**に取得（窓最小化, DP-U4a-04, ロックなし）。B=API 層で事前取得（窓拡大）。 **[Answer]: A**
- **Q3（SufficiencyResult の配置）**: ★**A** = **`schema/` の Pydantic モデル**（API レスポンス内訳に載るデータ契約）。`pool_sufficiency`（domain）はこれを返す。B=domain ローカルの dataclass（契約から外れる）。 **[Answer]: A**
- **Q4（U1 回帰の扱い）**: ★**A** = `Item.body` 追加に伴い U1 の schema テスト・fixture を更新し、**既存 19 テスト + U4a 追加分をすべて緑**にしてから完了（ブロッキング完了基準）。B=U1 テストは据え置き（body 必須化で失敗する）。 **[Answer]: A**
- **Q5（CLI HTTP クライアント）**: ★**A** = 標準ライブラリ **`urllib`**（追加依存なし）。B=`httpx`（依存増、この規模で不要）。 **[Answer]: A**

---

## 4. 完了基準
- [x] 全 Step `[x]`。schema 波及・admin・domain・repo 拡張・scripts・migration 0002・deploy.yml が生成。
- [x] **U1 回帰含め全テスト緑**（unit+PBT）、integration（admin 越し）実行実績。
- [x] RT-1 CLOSE（deploy.yml 機能化）。
- [x] `aidlc-docs/construction/u4a/code/` サマリ。
