# U4a Infrastructure Design — token_issue / pool_ingest（+ 管理 API）

**ユニット**: U4a。**U1 の共有インフラ（D1 + schema/ + CI デプロイ）を流用**し、差分のみを定義する。共有分は `shared-infrastructure.md`、実装規約（F-1〜F-6）は U1 `infrastructure-design.md §2.1` を参照。
**方針**: 新規インフラは最小。差分は (a) `/admin/*` ルート、(b) `ADMIN_BASIC_*` シークレット、(c) `migration 0002` の適用順、(d) `deploy.yml` の肉付け（RT-1 消化）。

---

## 1. LC-U4a → インフラ マッピング（差分）

| 論理コンポーネント | インフラ | 備考 |
|---|---|---|
| **LC-U4a-01 AdminApi** | 既存 Worker に **`/admin/*` ルート追加**（同一サブドメイン, Q1=A） | 別 Worker にしない（NFR-02）。`on_fetch` 手動ディスパッチ |
| **LC-U4a-02 AuthGuard** | Worker 内 Basic 認証。秘密は **`ADMIN_BASIC_*`（wrangler secret）** | CORS なし（CLI 専用, NFR-02） |
| **LC-U4a-03 PoolSufficiency** | Worker 内 compute（純粋関数） | インフラ依存なし |
| **LC-U4a-04 Repository 書込** | 既存 **D1 バインディング（`DB`）** 経由 | migration 0002 で `items.body` 追加 |
| **LC-U4a-05 AdminLog** | Worker stdout（JSON）→ wrangler tail | トークン/本文は非出力（DP-U4a-02） |
| **LC-U4a-06 CLI** | **手元/CI の pure-Python**（Worker 外, 非デプロイ, Q5=A） | `urllib` で HTTPS+Basic。追加依存なし |

---

## 2. Compute / Networking（Q1）
- `/admin/*` は**参加者 API と同一 Worker・同一サブドメイン**にルート追加（別 Worker/サブドメインに分離しない）。証明書・デプロイの二重化を避ける。
- **CORS なし**（サーバ間 CLI 専用, NFR-02）。ブラウザ由来アクセスは想定しない。

## 3. Secrets（Q1 / Q4 補足）
- **`ADMIN_BASIC_USER` / `ADMIN_BASIC_PASSWORD`**: 本番は **手元からの一回きり `npx wrangler secret put`** を正とする（CI 経由で設定しない）。
  - 理由: (i) GitHub Secrets と Cloudflare の**二重管理を避ける**（Cloudflare 側にのみ存在）、(ii) `wrangler secret put` は Node のみで動作し、Windows ネイティブの Pyodide 問題（F-3）と無関係に手元 PowerShell の `npx wrangler secret put` で実行可能（wrangler login 済み）。
- ローカルは **`.dev.vars`（gitignore）**。`.dev.vars.example` に `ADMIN_BASIC_USER`/`ADMIN_BASIC_PASSWORD` 項目を追記（自己文書化）。
- **CI の GitHub Secrets は既存の `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` のみ**（G-1 検証で登録済みを流用）。

## 4. Storage — migration 0002（Q2）
- `migrations/0002_item_body.sql`（versioned）: `items` に `body TEXT NOT NULL` 追加、`body_ref` を NULL 許容化。**新規プロジェクトで既存行なし**のため一段階 NOT NULL 追加で安全（二段階不要）。
- **適用順序を厳守**: `wrangler d1 migrations apply`（**dev → prod**）を **管理 API デプロイより前**に。逆順では `body` 前提のコードが旧スキーマに当たる。
- **実験用 D1 は smoke 用（`nazokake-smoke`）とは別に作成**: `wrangler d1 create nazokake-judge` → 出力 `database_id` を `wrangler.toml` に転記 → `migrations apply`（0001 + 0002）。

## 5. CI/CD — `deploy.yml` の肉付け（RT-1 消化, Q4）
`.github/workflows/deploy.yml`（現状スケルトン）を `smoke-test-deploy.yml` を雛形に機能化する（Code Generation で実装）:
1. `uv sync`
2. **テスト（unit + PBT）** ← **デプロイの前に置く品質ゲート**（テスト失敗ならデプロイしない）
3. `uv run pywrangler d1 migrations apply nazokake-judge --remote`（0001 + 0002）
4. `uv run pywrangler deploy`
- Secrets（CI）: `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` のみ。`ADMIN_BASIC_*` は手元 `wrangler secret put`（§3）。
- 実デプロイ自体はユーザーのマシン/CI で（この Claude 環境は Cloudflare 認証不可）。
- **`smoke-test/` と `smoke-test-deploy.yml` は削除せず残置**（ランタイム再検証手段, G-1 記録どおり）。
- → これで **残タスク RT-1 を U4a で消化**（Code Generation で deploy.yml 実装 → CLOSED）。

## 6. デプロイ手順（U4a）
```
1. （初回のみ）wrangler d1 create nazokake-judge → database_id を wrangler.toml に転記
2. 手元: npx wrangler secret put ADMIN_BASIC_USER / ADMIN_BASIC_PASSWORD（一回きり）
3. CI(deploy.yml): uv sync → test → d1 migrations apply --remote(0001+0002) → deploy
4. 手元/CI: scripts/pool_ingest（層ごと段階投入可）→ token_issue（充足ゲート通過で発行）
```

## 7. トレーサビリティ
| 項目 | 対応 |
|---|---|
| /admin ルート・同一 Worker | Q1 / NFR-02 / LC-U4a-01 |
| ADMIN_BASIC_* 秘密（手元 put） | Q1/Q4 / NFR-08 / DP-U4a-01 |
| migration 0002・適用順 | Q2 / U4a-NFR-12 |
| deploy.yml 機能化（テスト前置） | Q4 / RT-1 |
| CLI 非デプロイ・urllib | Q5 / LC-U4a-06 |

## 8. 後続申し送り（Code Generation）
- `deploy.yml` の実装（RT-1 CLOSE）、`migration 0002`、`.dev.vars.example` 追記、実験用 D1 作成手順の README 反映。
- `wrangler.toml` の `database_id`（実 D1）設定はユーザー環境。
