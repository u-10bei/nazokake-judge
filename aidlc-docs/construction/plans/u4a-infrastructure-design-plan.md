# U4a Infrastructure Design Plan — token_issue / pool_ingest（+ 管理 API）

**ユニット**: U4a。LC-U4a（AdminApi / AuthGuard / PoolSufficiency / Repository 書込 / AdminLog / CLI）を実インフラ（Cloudflare）にマップする。
**前提（既決・U1 で確定）**: 案 A′（Python Workers + D1, raw workers API, F-4/F-5）。**共有インフラ（D1 + schema/）は U1 が所有**（`shared-infrastructure.md`）。CI デプロイ（GitHub Actions, F-3）・`wrangler.toml`（`workers_dev=true`）・シークレットは `wrangler secret`（NFR-08）。H-1=(c)：実行時 D1 は Worker 集約。

**方針**: U4a は U1 の基盤を**大きく流用**するため新規インフラは最小。差分は **(a) `/admin/*` ルート、(b) `ADMIN_BASIC_*` シークレット、(c) `migration 0002` の適用順、(d) `deploy.yml` の肉付け（残タスク RT-1）**。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `construction/u4a/infrastructure-design/infrastructure-design.md`（差分中心）を生成します（共有分は既存 `shared-infrastructure.md` を参照）。

---

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-13）
- [x] `construction/u4a/infrastructure-design/infrastructure-design.md`（LC-U4a→インフラ差分、/admin ルート・ADMIN_BASIC_* 秘密（手元 put）・migration 0002 適用順・deploy.yml 肉付け=RT-1 消化）

**回答サマリ**: 全 5 問 ★A。Q4 補足＝ADMIN_BASIC_* は手元 `wrangler secret put`（CI 二重管理回避）・テスト前置ゲート・実験用 D1 別作成。

## インフラカテゴリ適用性評価（U4a・差分のみ）
| カテゴリ | 適用 | 判断根拠 |
|---|---|---|
| **Deployment Environment** | 流用 | U1 の dev/prod（実験用サブドメイン）をそのまま。U4a 固有の環境なし。→ Q3 |
| **Compute** | 流用 + 差分 | 同一 Worker に `/admin/*` を追加（別 Worker にしない, NFR-02）。→ Q1 |
| **Storage** | 流用 + 差分 | 既存 D1 に **migration 0002（Item.body）**を追加適用。→ Q2 |
| **Networking** | 最小限 | `/admin/*` は同一サブドメインのルート。CORS なし（CLI 専用, NFR-02）。 |
| **Secrets** | 適用（差分） | `ADMIN_BASIC_USER`/`PASSWORD`。→ Q1 |
| **CI/CD** | 適用（差分） | `deploy.yml` を実機能化（RT-1）。→ Q4 |
| **Monitoring** | 最小限 | stdout JSON（U1 と同）。トークン/本文は非出力（DP-U4a-02）。 |
| **Messaging** | N/A | — |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Compute/Secrets】管理 API のホスティングとシークレット
- **★A（推奨）**: `/admin/*` は**参加者 API と同一 Worker・同一サブドメイン**にルートを追加（別 Worker/サブドメインに分離しない, NFR-02）。認証は AuthGuard（Basic）。シークレット `ADMIN_BASIC_USER`/`ADMIN_BASIC_PASSWORD` は **本番 `wrangler secret put`**・ローカル `.dev.vars`（gitignore）。`.dev.vars.example` に項目を追記（U1 で雛形あり）。
- **B**: 管理用に別 Worker/サブドメインを分離。→ デプロイ・証明書・運用の二重化。小規模に過剰。

[Answer]: A

### Q2【Storage】migration 0002（Item.body）の適用
- **★A（推奨）**: `migrations/0002_item_body.sql` を **versioned** で追加（`items.body TEXT NOT NULL`・`body_ref` NULL 許容化）。適用は `wrangler d1 migrations apply`（**dev→prod**）で、**管理 API デプロイより前**に適用（body 前提のコードが動く順序）。既存行なしのため NOT NULL 追加は安全。
- **B**: アプリ起動時に動的スキーマ変更。→ migrations の versioned 管理（U1 確定）に反する。

[Answer]: A

### Q3【Deployment】環境分離とデプロイ対象
- **★A（推奨）**: U1 の **dev（miniflare/ローカル D1）/ prod（実験用サブドメイン・本番 D1）**分離をそのまま流用。U4a のデプロイ対象は「同一 Worker（`/admin/*` 追加分）+ migration 0002」。scripts（CLI）はデプロイ対象外（手元/CI から実行）。
- **B**: U4a 専用のステージング環境を追加。→ 小規模に過剰。

[Answer]: A

### Q4【CI/CD】`deploy.yml` の肉付け（残タスク RT-1）
U4a は管理 API を実装する最初の実デプロイ可能ユニット。
- **★A（推奨）**: **RT-1 を U4a で消化** — `.github/workflows/deploy.yml`（現状スケルトン）を `smoke-test-deploy.yml` を雛形に機能化: `uv sync` → **テスト（unit+PBT）** → `d1 migrations apply --remote`（0001+0002）→ `pywrangler deploy`。Secrets: `CLOUDFLARE_API_TOKEN`/`ACCOUNT_ID` + `ADMIN_BASIC_*`（deploy 後に `wrangler secret put`、または CI で設定）。`database_id` を実 D1 に設定する手順を明記。実デプロイ自体はユーザーのマシン/CI で（この環境は Cloudflare 認証不可）。
- **B**: deploy.yml は据え置き、実デプロイは U2 まで先送り。→ H-1(c) 経路（scripts→管理 API→D1）を実運用で検証する U4a の主目的が遅れる。RT-1 も残り続ける。

[Answer]: A ＋ `ADMIN_BASIC_*` は手元からの一回きり `npx wrangler secret put` を正とする（CI 経由設定は不採用＝GitHub Secrets と Cloudflare の二重管理を避ける）。CI の GitHub Secrets は既存 `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` のみ。deploy.yml のテストはデプロイの前（品質ゲート）。実験用 D1 は smoke 用と別に作成。smoke-test-deploy.yml は残置。

### Q5【Compute】scripts/ CLI の実行形態
- **★A（推奨）**: `scripts/pool_ingest`・`scripts/token_issue` は **Worker 外の pure-Python CLI**（`uv run python scripts/...` or entry-point）。標準ライブラリ `urllib` で HTTPS+Basic（追加依存なし）。依存は `pyproject.toml`。CLI はデプロイされず、手元/CI から管理 API を叩く。
- **B**: CLI も Worker 化（scheduled/queue）。→ 手動運用の投入・発行に不要な複雑さ。

[Answer]: A

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `infrastructure-design.md`（差分）を生成 → 標準 2 択（Request Changes / Continue → Code Generation）。**Part 2 生成時に本 plan の `[Answer]:` 欄も記入する**（監査証跡の自己完結）。
