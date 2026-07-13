# U4a Tech Stack Decisions — token_issue / pool_ingest（+ 管理 API）

U1 の TSD-01〜08 を前提に、U4a 追加分を **TSD-U4a-NN** で定義する。案 A′（raw workers API + Pydantic v2, F-4/F-5）・uv+pywrangler・CI デプロイは U1 で確定済み。

---

## TSD-U4a-01: 管理 API の認証実装
- **方式**: raw workers API の `on_fetch` 内で **Basic 認証を関数として実装**（ASGI ミドルウェア前提にしない, F-5）。`Authorization: Basic ...` を復号し、`ADMIN_BASIC_USER`/`ADMIN_BASIC_PASSWORD`（`env` 経由）と**定数時間比較**（`hmac.compare_digest` / `secrets.compare_digest`）。不一致は 401 + `WWW-Authenticate: Basic`。
- **配置**: `backend/admin/`（U4a 先行導入）。`/admin/items`・`/admin/tokens` のルーティングも `on_fetch` 内の手動ディスパッチ。
- **秘密**: 本番 `wrangler secret put`、ローカル `.dev.vars`（gitignore）。
- 根拠: U4a-NFR-01/02/05, Q1/Q2, App Design Q5=B。

## TSD-U4a-02: 充足判定の純粋関数（単一実装）
- **`pool_sufficiency(items, params) -> SufficiencyResult`** を `backend/domain/` に純粋関数として実装。三点セット（BR-U4a-05）を評価し、不足内訳を返す。
- **単一呼び出し規約**: pool_ingest（warn）と token_issue（gate）が同一関数を呼ぶ（U4a-NFR-10）。述語乖離を構造的に防止。
- **PBT 対象**（PBT-03）: 境界値・反例探索。
- 根拠: U4a-NFR-10/11, Q6。

## TSD-U4a-03: HTTP ペイロードモデル（単一データ契約）
- `ItemIngestRequest` / `IngestResult`（`sufficiency_warnings` 含む）/ `RejectedItem` / `TokenIssueRequest` / `TokenIssueResult`（`ok`/`gate_errors` 含む）を **`schema/` に追加**。Worker（`backend/admin/`）と scripts が同一モデルを import（App Design Q6=A の単一データ契約が接続方式にも及ぶ）。
- 根拠: FD Q3=A, domain-entities.md。

## TSD-U4a-04: Item.body の D1 格納（migration 0002）
- `schema/models.py` の `Item`: `body: str`（必須, min_length=1）追加、`body_ref: str | None` に変更。`validate_item` は層ラベル + body 非空を検証。
- `migrations/0002_item_body.sql`: `items.body TEXT NOT NULL` 追加、`body_ref` NULL 許容化（既存行なしで安全）。
- `backend/repo/repository.py` の `list_items` に `body`/`body_ref` を含める。`insert_items`/`insert_tokens` を D1 batch 原子投入で追加。
- 根拠: FD Q5=X, U4a-NFR-06/12。

## TSD-U4a-05: CLI（scripts/）の実装
- `scripts/pool_ingest`・`scripts/token_issue` は **Worker 外の pure-Python**。HTTPS + Basic で管理 API を叩く（標準ライブラリ `urllib` またはユーザー明示時 `httpx`。依存は `pyproject.toml`）。
- 入力: JSON/JSONL ファイル（pool_ingest）、`count` + URL テンプレート引数（token_issue）。
- 出力: `IngestResult` の表示（rejected は非ゼロ終了）、トークン URL 一覧（stdout + gitignore ファイル）。
- 認証情報は環境変数（`ADMIN_BASIC_USER`/`ADMIN_BASIC_PASSWORD`）。
- 根拠: FD Q5/Q7/Q8, U4a-NFR-03/04。

## TSD-U4a-06: テスト
- **PBT**（`tests/pbt/`）: `pool_sufficiency`、トークン生成一意性/契約適合。PBT 強制 PBT-02/03/07/08/09（U1 と同一）。
- **integration**（`tests/integration/`）: 管理エンドポイント越しに冪等 upsert・凍結ガード・原子性・段階投入 warn・発行ゲート・認証 401（PU4a-1/2/3a/3b/5/6）。
- 根拠: U4a-NFR-10/11, Q6。

---

## 決定サマリ
| ID | 決定 |
|---|---|
| TSD-U4a-01 | Basic 認証を on_fetch 内関数で（定数時間比較）、`backend/admin/` |
| TSD-U4a-02 | `pool_sufficiency` 純粋関数・単一実装・2 呼び出し点（PBT） |
| TSD-U4a-03 | ペイロードモデルを schema/ に（単一データ契約） |
| TSD-U4a-04 | Item.body の D1 格納 + migration 0002 + Repository 書き込みメソッド |
| TSD-U4a-05 | scripts/ CLI（pure-Python, HTTPS+Basic, 環境変数） |
| TSD-U4a-06 | PBT（純粋）+ integration（実 D1） |

## 後続への申し送り
- **NFR Design**: Basic 認証・秘匿・冪等/原子/ゲートを設計パターン（DP）に落とす。`pool_sufficiency` の LC 位置づけ。
- **Code Generation**: `backend/admin/`・`scripts/`・`pool_sufficiency`・migration 0002・schema 波及・テスト。
