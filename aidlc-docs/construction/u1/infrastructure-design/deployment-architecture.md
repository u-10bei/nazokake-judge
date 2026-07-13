# U1 Deployment Architecture — 共有基盤 (foundation)

**ユニット**: U1（共有基盤。デプロイ単位はプロジェクト全体で単一）
**前提**: 案 A′（Cloudflare Python Workers + D1）。実験用サブドメインに分離デプロイ（NFR-09）。運用基盤確保済み。

---

## 1. 環境（Q3=A）

| 環境 | 用途 | Compute | D1 |
|---|---|---|---|
| **dev（ローカル/CI）** | 開発・動作確認・テスト | `uv run pywrangler dev`（**Linux/CI**。Windows ネイティブ非サポート, F-3） | **ローカル D1 / miniflare**（実験データを汚さない） |
| **prod** | 実験運用 | Cloudflare Python Workers（**raw workers API**, 実験用サブドメイン）。**デプロイは CI 経由**（下記 §4） | **本番 D1**（単一 DB） |

- **単一 D1 DB を dev/prod で分離**。dev/prod の DB を明確に分け、実験データの汚染を防ぐ。
- prod は実験用サブドメインの Workers ルートに紐付け（`wrangler.toml` に `workers_dev = true`, F-6）。

### 開発環境要件（smoke test で確定, F-1/F-3/F-5/F-6）
- **依存**: `pyproject.toml` の `dependencies`（`requirements.txt` 不可, F-1）。
- **デプロイ経路**: **CI（GitHub Actions ubuntu-latest）を正**。開発機が Windows の場合、ローカル `pywrangler dev/deploy` は非サポート（uv の Pyodide 配置と `python.exe` 期待パス不整合, F-3。WSL で回避可だが本プロジェクトは CI に一本化）。
- **ハンドラ**: モジュールレベル `async def on_fetch(request, env)`（クラス形式不可, F-5）。
- **ルート**: `wrangler.toml` に `workers_dev = true` 明記（F-6）。

---

## 2. トポロジ

```
[Participant UI (静的)]  --HTTPS/JSON-->  ┐
[Admin UI (静的)]        --HTTPS/JSON-->  │
                        (Basic 認証)      ▼
                              [ Cloudflare Python Workers (raw workers API + Pydantic) ]
                                          │  D1 バインディング
                                          ▼
                                     [ D1 (SQLite 互換) ]
                                          ▲
[scripts/ (token_issue/pool_ingest)] --HTTPS + Basic 認証--> [Worker 管理 API] ┘
                                          （H-1 = (c)：実行時 D1 アクセスは Worker に集約）

[scripts/bt_aggregate]  <-- schema/ 準拠 file (CSV/JSON) --  [Export (U3)]  （DB 直参照なし）
```

- **実行時の D1 アクセスは Worker のみ**（H-1 (c)）。scripts は管理 API を叩く。
- `bt_aggregate` は DB に触れず、エクスポート出力（schema/ 準拠）を入力に取る（US-R02↔R04）。

---

## 3. デプロイ構成要素

| 要素 | 内容 |
|---|---|
| `wrangler.toml` | Workers 設定。`python_workers` flag、**`workers_dev = true`**（F-6）、D1 バインディング、ルート（サブドメイン）、環境（dev/prod）定義、`main`=ソース隔離ディレクトリ。詳細は Code Generation。 |
| `.github/workflows/*.yml` | **CI デプロイ workflow**（`smoke-test-deploy.yml` を雛形に流用, §4）。Secrets: `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID`。 |
| D1 バインディング | Worker から D1 を参照する binding 名を定義（例: `DB`）。 |
| マイグレーション | `wrangler d1 migrations`（versioned `.sql`）。dev/prod 各環境へ適用（§1）。 |
| シークレット | `wrangler secret`（Basic 認証情報等）。ローカルは `.dev.vars`（gitignore）。 |

---

## 4. デプロイ手順（CI 経由・GitHub Actions workflow）

**デプロイは手元 wrangler ではなく GitHub Actions workflow で行う**（wrangler は CI 内で実行, F-3）。smoke 検証用の `.github/workflows/smoke-test-deploy.yml` を**本実装用 deploy workflow の雛形として流用**する。

- **Secrets**: `CLOUDFLARE_API_TOKEN`（**Workers Scripts:Edit + D1:Edit**）、`CLOUDFLARE_ACCOUNT_ID`。
- **手順（workflow 内）**:
  1. `uv` セットアップ → `uv sync`（依存は `pyproject.toml`）。
  2. **マイグレーション適用**: `uv run pywrangler d1 migrations apply`（dev 確認 → prod `--remote`）。
  3. **シークレット設定**: `wrangler secret put`（prod, Basic 認証情報等）。
  4. **Worker デプロイ**: `uv run pywrangler deploy`（prod = 実験用サブドメイン, `workers_dev = true`）。
  5. **刺激・トークン投入**（U4a, 別経路・リポジトリ管理外）: 管理 API（Basic 認証）経由で pool_ingest / token_issue。
- smoke worker 自体の検証結果 `result-prod.json` は CI artifact として取得可（G-1 実績）。

---

## 5. デプロイ時操作 vs 実行時接続（H-1 の明確化）

| 操作 | 分類 | 経路 |
|---|---|---|
| DDL 適用（migrations） | **デプロイ時操作** | `wrangler d1 migrations`（管理 API を通らない。H-1 の例外ではない） |
| シークレット設定 | デプロイ時操作 | `wrangler secret` |
| token_issue / pool_ingest | **実行時接続** | Worker 管理 API（Basic 認証）→ D1（H-1 (c)） |
| 参加者フロー | 実行時接続 | Worker API → D1 |

---

## 6. 後続申し送り
- `wrangler.toml` の具体（binding 名・ルート・環境変数）と migrations ディレクトリ構成は **Code Generation**。
- 実験用サブドメインの具体ホスト名は運用時に確定（運用基盤確保済み）。
