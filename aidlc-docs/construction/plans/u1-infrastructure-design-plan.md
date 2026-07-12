# U1 Infrastructure Design Plan — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**目的**: U1 の論理コンポーネント（LC-01〜05）を実インフラ（Cloudflare）にマップし、申し送り **H-1（scripts→D1 接続方式）** と App Design リスク **R-1（Python Workers beta 互換）/R-2（D1 制約）** を確定する。
**前提（既決）**: 案 A′（Cloudflare Python Workers/Pyodide + FastAPI + D1、Hypothesis）。運用基盤（ドメイン・契約）確保済み、実験用サブドメインに分離デプロイ（NFR-09）。監視基盤は持たない（U1-NFR-10、wrangler tail/stdout）。

このドキュメントは **Part 1（Plan + 質問）**。回答後、承認を経て `infrastructure-design.md` / `deployment-architecture.md`（+ 共有分は `shared-infrastructure.md`）を生成します。

---

## 生成予定の成果物 → 生成済み（Part 2 実行済み, 2026-07-12）

- [x] `construction/u1/infrastructure-design/infrastructure-design.md`（論理→インフラ・マッピング、H-1=(c)/R-1 smoke test/R-2 確定）
- [x] `construction/u1/infrastructure-design/deployment-architecture.md`（dev/prod 環境・トポロジ・デプロイ手順・デプロイ時 vs 実行時の区別）
- [x] `construction/shared-infrastructure.md`（D1 + schema/ = 全ユニット共有インフラ）
- [x] 波及反映: `inception/application-design/component-dependency.md`（通信パターン・依存マトリクス C-SCRIPT-TOKEN/POOL: REPO→API・H-1 注記・mermaid を (c) 確定版に更新）

**回答サマリ**: 全 5 問 = 推奨デフォルト A。H-1=(c) 確定。Q1=A(smoke test 先行) / Q2=A(H-1=(c)) / Q3=A(dev/prod 分離・共有記録) / Q4=A(wrangler d1 migrations) / Q5=A(wrangler secret)

---

## インフラカテゴリの適用性評価（MANDATORY: 全カテゴリを評価）

| カテゴリ | 適用 | 判断根拠 |
|---|---|---|
| **Deployment Environment** | **適用** | Cloudflare、実験用サブドメイン=prod、dev 環境（NFR-09）。→ Q3。 |
| **Compute Infrastructure** | **適用** | Cloudflare **Python Workers（open beta, `python_workers` flag）**。R-1 互換性検証が最大論点。→ Q1。 |
| **Storage Infrastructure** | **適用** | **D1**（プロビジョニング・binding・マイグレーション）。R-2 制約。→ Q3/Q4。 |
| **Messaging Infrastructure** | **N/A** | キュー/イベント駆動なし（同期・小規模, NFR Design の非採用部品）。 |
| **Networking Infrastructure** | **最小限** | Workers ルート/サブドメイン。ロードバランサ・API GW 不要。CORS は U2/U3 API 層。 |
| **Monitoring Infrastructure** | **最小限** | wrangler tail / stdout JSON ログ（既決 U1-NFR-10）。専用可観測性基盤・アラートなし。 |
| **Shared Infrastructure** | **適用** | **D1 と schema/ は全ユニット共有**。→ `shared-infrastructure.md` を生成、Q3 で確認。 |

---

## 質問（すべて回答してください）

回答方法: 記号を `[Answer]:` の後ろに記入。各問に推奨デフォルト（★）付き。合意なら記号だけで可。

## Question 1 — Python Workers beta 互換性の検証タイミング（R-1）★重要
Python Workers は open beta（`python_workers` flag）で、FastAPI/ASGI・Pydantic v2・D1 binding の実可用性に不確実性があります（TSD-02, R-1）。検証方針は?

A) ★ **Infrastructure Design 段階で最小 smoke test を先行実施**（`python_workers` + FastAPI 起動 + Pydantic v2 import/validate + D1 binding 疎通の最小 Worker をデプロイ確認）。結果を `infrastructure-design.md` に記録。不可なら TSD-02 フォールバック（pydantic v1/dataclasses）または案 B へエスカレーション

B) **Code Generation で本実装と同時に確認**（先行 smoke test はしない。リスクは実装時に顕在化させる）

X) Other

[Answer]:

## Question 2 — H-1: scripts → D1 の接続方式 ★重要
`scripts/`（U4 token_issue/pool_ingest/bt_aggregate）は D1 にどう接続しますか?（App Design H-1、推奨は (c)）

A) ★ **(c) Worker に管理用エンドポイント（Basic 認証背後）を設け、スクリプトがそれを叩く**。認証境界を一本化、依存は `SCRIPT→API`。**U1 Repository は Worker 内専用**でよく、D1 アクセスは Worker に集約される（LC-03 の I/O 境界が一箇所に保たれる）

B) **(a) `wrangler d1 execute` 経由**（スクリプトが wrangler CLI を呼ぶ）

C) **(b) D1 HTTP API を直叩き**（スクリプトが D1 REST を直接使用）

X) Other

[Answer]:

## Question 3 — D1 プロビジョニングと環境分離（Storage + Deployment + Shared）
D1 データベースの構成は?

A) ★ **単一 D1 DB を dev/prod で分離**（prod=実験用サブドメイン、dev=`wrangler dev` のローカル D1/miniflare）。**この D1 と `schema/` は全ユニット共有**（`shared-infrastructure.md` に記録）

B) 単一 D1 DB のみ（環境分離せず 1 つ）

X) Other

[Answer]:

## Question 4 — DDL / マイグレーション適用方式（Storage）
`schema/` の D1 DDL をどう適用しますか?

A) ★ **`wrangler d1 migrations`**（versioned `.sql` を `schema/`（または `migrations/`）で管理し、migrations コマンドで適用）。一意制約（DP-02）・NOT NULL（BR-11）も DDL に含める

B) 起動時/手動で raw `execute`（マイグレーション管理を持たない）

X) Other

[Answer]:

## Question 5 — シークレット・認証情報の管理（Security / Deployment）
Basic 認証情報（管理 API, H-1 (c) 採用時）や機微設定の管理は?

A) ★ **`wrangler secret`**（Cloudflare の secret ストア）。**リポジトリに秘密を置かない**（NFR-08・データ管理方針と整合）。ローカルは `.dev.vars`（gitignore）

B) 環境変数ファイルで管理

X) Other

[Answer]:

---

## 回答後の進め方
1. 回答分析（曖昧・矛盾があれば追質問を本ファイルに追記、GATE 維持）。
2. `infrastructure-design.md` / `deployment-architecture.md` / `shared-infrastructure.md` を生成。
3. 標準 2 択完了メッセージ（Request Changes / Continue → **Code Generation**）を提示。

**備考**: Infrastructure Design 承認後の次段は U1 の **Code Generation**（per-unit ループで U1 の設計完了 → 実コード生成）。ただし実装順序は U1→**U4a**→… のため、U1 Code Generation 後に U4a へ移る点は Code Generation 計画時に扱う。
