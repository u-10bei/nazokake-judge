# U2 Infrastructure Design Plan — 参加者セッション（participant）

**ユニット**: U2。LC-U2（ParticipantApi / Session・Response・Survey Service / ViewSerializer / ParticipantLog / LikertSelector / ParticipantFrontend）を実インフラ（Cloudflare）にマップする。
**前提（既決・U1/U4a で確定）**: 案 A′（Python Workers + D1, raw workers API, F-4/F-5）。**共有インフラ（D1 + schema/）は U1 が所有**（`shared-infrastructure.md`）。CI デプロイ（GitHub Actions, F-3）・`wrangler.toml`（`workers_dev=true`）・`deploy.yml` は **U4a で機能化済み（RT-1 CLOSED）**。管理境界（Basic 認証・`ADMIN_BASIC_*`）は U4a 導入済み。

**方針**: U2 は U1/U4a の基盤を**大きく流用**するため新規インフラは最小。差分は **(a) 静的フロント（SPA）の配信方法〈U2 固有・最大論点〉、(b) `/api/*` ルート追加、(c) CORS/配信オリジン、(d) `migration 0003`（likert UNIQUE）の適用、(e) `deploy.yml` に 0003 追加**。参加者 API は**新規シークレットなし**（トークン=資格, U2-NFR-01）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `construction/u2/infrastructure-design/infrastructure-design.md`（差分中心）を生成します（共有分は既存 `shared-infrastructure.md` を参照）。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-14）
- [x] `construction/u2/infrastructure-design/infrastructure-design.md`（LC-U2→インフラ差分: Workers Static Assets 同一オリジン配信・`/api/*` ルーティング・CORS なし・migration 0003 適用順・deploy.yml 無変更・**beta 3 点検証を Code Generation 冒頭に**・デプロイ手順・トレーサビリティ）

**回答サマリ**: 全 5 問 ★A。Q1 に beta 3 点検証（Static Assets × Python Workers を Code Generation 冒頭の smoke で確定、受け皿は是正→C→B）。Q2 に SPA フォールバック不使用（`/` のみで完結）。deploy.yml は 0003 追加で無変更。

---

## インフラカテゴリ適用性評価（U2・差分のみ）
| カテゴリ | 適用 | 判断根拠 |
|---|---|---|
| **Deployment Environment** | 流用 | U1 の dev/prod（実験用サブドメイン）をそのまま。→ Q5 |
| **Compute** | 流用 + 差分 | 同一 Worker に `/api/*` 追加 + **静的アセット配信**。→ Q1/Q2 |
| **Storage** | 流用 + 差分 | 既存 D1 に **migration 0003（likert UNIQUE）**を追加適用。→ Q4 |
| **Networking** | 適用（差分） | フロント配信オリジンと **CORS**（同一オリジンなら不要）。→ Q3 |
| **Secrets** | N/A（差分なし） | 参加者 API はトークン=資格・**新規シークレットなし**（U2-NFR-01）。 |
| **CI/CD** | 適用（差分・小） | `deploy.yml`（U4a 機能化済み）に **migration 0003** を追加、フロント配信の反映。→ Q4 |
| **Monitoring** | 最小限（流用） | stdout JSON（U1 と同）。参加者ログはトークンハッシュ・本文非出力（DP-U2-03）。 |
| **Messaging** | N/A | — |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Compute・最大論点】静的フロント（SPA）の配信方法
TSD-U2-01 が本ステージに申し送った U2 固有の最大論点。単一 HTML + バニラ JS の SPA（`frontend/`）をどう配信するか。
- **★A（推奨）**: **Cloudflare Workers Static Assets** を使い、**参加者 API と同一 Worker・同一オリジン**で配信（`wrangler.toml` に `[assets]` = `frontend/` ディレクトリ + binding を宣言）。ルーティングは「**`/api/*` は Worker（`on_fetch`）、それ以外は静的アセット**」。同一オリジンゆえ **CORS 不要**（Q3）、デプロイも `pywrangler deploy` 一発（アセットも同時アップロード）。証明書・デプロイの一本化。
- **B**: **Cloudflare Pages** に別プロジェクトとしてフロントを配信し、API は Worker。→ 別オリジンになり CORS 必須・デプロイ二系統・運用二重化。小規模に過剰。
- **C**: Worker が HTML 文字列を直接 `Response` で返す（アセット機能を使わない）。→ CSS/JS の配信・キャッシュ制御が煩雑。小さな SPA でも保守性が落ちる。

[Answer]: A — Cloudflare Workers Static Assets で参加者 API と同一 Worker・同一オリジン配信（`wrangler.toml` に `[assets]` 宣言、`/api/*` は on_fetch・それ以外はアセット）。**補足（beta 3 点検証を Code Generation 冒頭の小検証に置く）**: Static Assets × Python Workers は G-1 と同種の「本番でしか確信できない」領域。smoke 流儀（最小アセット + `/api/ping` の実機確認）で ① アセット配信と on_fetch の実行順（`/api/*` はアセット非一致で Worker に届くはず）② `[assets]` の現行設定キー（directory/binding 名）と pywrangler deploy でのアセット同時アップロード ③ `run_worker_first` 相当の要否 を確定・記録。受け皿: 順序が想定外なら該当設定で是正 → Static Assets が Python Workers と併用不能な場合のみ C（Worker 埋め込み）へ、B=Pages は最後の手段。

### Q2【Compute】`/api/*` と静的アセットのルーティング優先順位
Q1=A（同一 Worker）を前提とした、Worker とアセットの実行順。
- **★A（推奨）**: **`/api/*` は必ず Worker が処理**し、それ以外のパス（`/`・静的ファイル）はアセットが応答。SPA のためアセット未ヒットのナビゲーションは**アプリシェル（`index.html`）にフォールバック**（クライアントルーティングはフェーズ駆動なので単一シェルで足りる）。`/api/*` 応答は Worker 側で `Cache-Control: no-store`（DP-U2-04）、静的アセットは既定キャッシュ（本文を含まないため可）。
- **B**: すべてのリクエストを Worker が先に受け、必要に応じてアセットへ委譲。→ 参加者フローに不要なオーバーヘッド。

[Answer]: A — `/api/*` は Worker、それ以外はアセット。**ただし SPA フォールバックは使わない（簡素化）**。補足: 本 SPA は参加者が `/`（+ `?token=`）しか開かない設計（フェーズ駆動・クライアントルーティング/ディープリンクなし）ゆえ `not_found_handling` 系のフォールバックは不要で、未知パスは 404 で構わない。フォールバックは assets/Worker 優先順位に beta の複雑さを一枚足すだけなので不使用とし、**Q1 検証対象からも外す**（使わない機能は検証しない）。`/api/*` は Worker 側で no-store（DP-U2-04）、静的アセットは既定キャッシュ（本文を含まないため可）。

### Q3【Networking】CORS / 配信オリジン
- **★A（推奨）**: **Q1=A（同一オリジン）ゆえ CORS を設けない**（`/api/*` はブラウザから同一オリジンで叩かれる）。HTTPS 強制（Cloudflare 既定）。将来フロントを別オリジンに分離する場合のみ、**許可オリジンをフロント配信元に限定**した CORS を追加（現時点は不要）。参加者 API は Basic 認証なし・トークン=資格（U2-NFR-01）。
- **B**: 予防的に緩い CORS（`*`）を付ける。→ 不要な露出面。同一オリジンでは有害無益。

[Answer]: A — 同一オリジンゆえ CORS を設けない。HTTPS 強制（既定）。将来別オリジン分離時のみ許可オリジン限定 CORS を追加。補足: 予防的 `*`（B）は同一オリジン構成では有害無益（不要な露出面）という判断に同意。

### Q4【Storage/CI-CD】migration 0003 の適用と deploy.yml 反映
- **★A（推奨）**: `migrations/0003_likert_unique.sql`（versioned）を追加（`likert_responses` に `UNIQUE(token, target_ref)`、新規プロジェクトで既存行なく安全）。適用は `wrangler d1 migrations apply`（**dev→prod**）で、**参加者 API デプロイより前**（0002 と同じ流儀）。`deploy.yml`（U4a 機能化済み）の `d1 migrations apply --remote` は**バージョン管理された全 migration を適用**するため、**0003 はファイル追加だけで自動的に適用対象に入る**（apply コマンドの引数変更は不要）。静的アセットは `pywrangler deploy` が同時アップロード。
- **B**: 0003 を手動適用し deploy.yml を変えない。→ dev/prod で適用漏れリスク。versioned 管理（U1 確定）に反する。

[Answer]: A — 0003 を versioned 追加、適用は dev→prod・デプロイ前（0002 と同じ流儀）。deploy.yml は migrations apply が versioned 全適用のため**ファイル追加のみで自動的に対象化**（コマンド変更不要）。補足: deploy.yml 無変更で済むのは U4a で RT-1 を先に消化した配当。静的アセットが deploy に含まれることは Q1 検証 ② で確認。

### Q5【Deployment】環境分離とデプロイ対象
- **★A（推奨）**: U1/U4a の **dev（miniflare/ローカル D1）/ prod（実験用サブドメイン・本番 D1）** 分離をそのまま流用。U2 のデプロイ対象は「同一 Worker（`/api/*` 追加分 + 静的アセット）+ migration 0003」。参加者フロント・API・管理 API（U4a）・scripts が**同一 Worker/同一 D1** を共有（実験用サブドメイン一本）。
- **B**: 参加者向けに専用環境/サブドメインを分ける。→ トークン配布 URL・運用が分散し小規模に過剰。

[Answer]: A — dev/prod 分離を流用。参加者フロント・参加者 API・管理 API・scripts が同一 Worker / 同一 D1 / 実験用サブドメイン一本に収束。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `infrastructure-design.md`（差分中心）を生成 → 標準 2 択（Request Changes / Continue → **Code Generation〈U2〉**）。**Part 2 生成時に本 plan の `[Answer]:` 欄も記入する**（監査証跡の自己完結）。
