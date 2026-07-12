# U1 Deployment Architecture — 共有基盤 (foundation)

**ユニット**: U1（共有基盤。デプロイ単位はプロジェクト全体で単一）
**前提**: 案 A′（Cloudflare Python Workers + D1）。実験用サブドメインに分離デプロイ（NFR-09）。運用基盤確保済み。

---

## 1. 環境（Q3=A）

| 環境 | 用途 | Compute | D1 |
|---|---|---|---|
| **dev（ローカル）** | 開発・動作確認 | `wrangler dev`（Python Workers, local） | **ローカル D1 / miniflare**（実験データを汚さない） |
| **prod** | 実験運用 | Cloudflare Python Workers（実験用サブドメイン） | **本番 D1**（単一 DB） |

- **単一 D1 DB を dev/prod で分離**。dev/prod の DB を明確に分け、実験データの汚染を防ぐ。
- prod は実験用サブドメインの Workers ルートに紐付け。

---

## 2. トポロジ

```
[Participant UI (静的)]  --HTTPS/JSON-->  ┐
[Admin UI (静的)]        --HTTPS/JSON-->  │
                        (Basic 認証)      ▼
                              [ Cloudflare Python Workers (FastAPI) ]
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
| `wrangler.toml` | Workers 設定。`python_workers` flag、D1 バインディング、ルート（サブドメイン）、環境（dev/prod）定義。詳細は Code Generation。 |
| D1 バインディング | Worker から D1 を参照する binding 名を定義（例: `DB`）。 |
| マイグレーション | `wrangler d1 migrations`（versioned `.sql`）。dev/prod 各環境へ適用（§1）。 |
| シークレット | `wrangler secret`（Basic 認証情報等）。ローカルは `.dev.vars`（gitignore）。 |

---

## 4. デプロイ手順（概略・Code Generation で確定）

1. **smoke test**（infrastructure-design.md §2）: 最小 Worker で `python_workers`+FastAPI+Pydantic v2+D1 binding+batch を確認。
2. **マイグレーション適用**: `wrangler d1 migrations apply`（dev → 確認 → prod）。
3. **シークレット設定**: `wrangler secret put`（prod）。
4. **Worker デプロイ**: `wrangler deploy`（prod = 実験用サブドメイン）。
5. **刺激・トークン投入**（U4a, 別経路・リポジトリ管理外）: 管理 API（Basic 認証）経由で pool_ingest / token_issue。

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
