# U3 Infrastructure Design Plan — 研究者・管理（admin）

**ユニット**: U3。LC-U3（AdminApi 拡張 / AdminService / ExportService / 純粋整形 / Repository 集計拡張 / AdminUI）を実インフラ（Cloudflare）にマップする。
**前提（既決・U1/U4a/U2 で確定）**: 案 A′（Python Workers + D1, raw workers API, **src/ レイアウト F-8**）。**共有インフラ（D1 + schema/）は U1 所有**（`shared-infrastructure.md`）。同一 Worker・実験用サブドメイン一本・CI デプロイ（`deploy.yml`, U4a 機能化済み）・Basic 認証境界（`ADMIN_BASIC_*`, U4a 導入済み）。

**方針**: U3 は既存インフラを**全面流用**するため新規インフラは実質ゼロ。差分は **`/admin/*` への GET ルート追加のみ**（同一 Worker・同一 Basic 認証背後）。**migration なし（読み取り専用）・新規シークレットなし・CORS なし・Static Assets 変更なし**。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `construction/u3/infrastructure-design/infrastructure-design.md`（差分中心）を生成します（共有分は既存 `shared-infrastructure.md` を参照）。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-15）
- [x] `construction/u3/infrastructure-design/infrastructure-design.md`（LC-U3→インフラ差分＝実質ゼロ: /admin/* GET ルート追加のみ・管理 UI Worker 配信・migration/シークレット/CORS/assets/deploy.yml すべて無変更・エクスポート受領〈ブラウザ + curl〉・U4b 申し送り・動作確認方針）

**回答サマリ**: 全 4 問 ★A。差分は「`/admin/*` GET ルート追加のみ」。エクスポートは **curl 経路を U4b 自動化の正**として申し送り。beta 検証不要。UI はデプロイ後手動確認。

---

## インフラカテゴリ適用性評価（U3・差分のみ）
| カテゴリ | 適用 | 判断根拠 |
|---|---|---|
| **Compute** | 流用 + 極小差分 | 同一 Worker に `/admin/*` GET ルート追加。管理 UI も Worker 配信（`GET /admin/`）。→ Q1 |
| **Storage** | 流用（読み取りのみ） | 既存 D1 を集計参照。**migration なし**（DDL 変更なし）。 |
| **Networking** | 流用 | 同一オリジン・**CORS なし**（U3-NFR-04 で決着）。管理系は Basic 認証背後。 |
| **Secrets** | N/A（差分なし） | `ADMIN_BASIC_*`（U4a）を再利用。**新規シークレットなし**。 |
| **CI/CD** | 流用（無変更） | `deploy.yml` は無変更（test → migrations apply〈0001〜0003, 追加なし〉→ deploy）。→ Q2 |
| **Static Assets** | 無関係 | 管理 UI は **assets ではなく Worker 埋め込み配信**（BR-U3-02）。参加者 `[assets]` に変更なし。→ Q3 |
| **Monitoring** | 流用 | stdout JSON・AdminLog 再利用（トークン/本文非出力）。 |
| **Messaging / Scalability / Resiliency** | N/A | — |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Compute】管理エンドポイント・管理 UI のホスティング
- **★A（推奨）**: `/admin/*` の GET ルート（`/admin/`・`/admin/progress`・`/admin/winrates`・`/admin/export`）を**既存 Worker・同一サブドメインに追加**（別 Worker/サブドメインに分離しない、U4a-NFR-02 と同方針）。管理 UI（HTML）も **Worker が `GET /admin/` で返す**（`src/backend/admin/ui.py` 定数, BR-U3-02）。認証は既存 AuthGuard（Basic）。
- **B**: 管理系を別 Worker に分離。→ デプロイ・証明書の二重化。小規模に過剰。

[Answer]: A — 変更なし（`/admin/*` へのルート追加のみ。migration なし・シークレット追加なし・assets 変更なし・D1/環境分離は現行のまま）。管理 UI も Worker が `GET /admin/` で返す（`ui.py` 定数）。**エクスポート受け取り**: ブラウザ（Basic 認証セッション）から `GET /admin/export` を直接ダウンロード。備考: CLI 経路 `curl -u $ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD -o export.json "https://<host>/admin/export?format=json"` も同一認証境界で利用可＝**U4b の入力取得をスクリプト/CI で自動化する場合は curl 経路が正**（U4b Infrastructure への申し送り）。

### Q2【CI/CD】デプロイ対象と deploy.yml
- **★A（推奨）**: U3 のデプロイ対象は「同一 Worker（`/admin/*` GET 追加分 + `ui.py`）」のみ。**`deploy.yml` は無変更**（`d1 migrations apply --remote` は **U3 で migration を追加しない**ため 0001〜0003 のまま・追加適用なし）。test（unit+PBT）→ migrations（no-op）→ deploy の既存フローで U3 も配布される。
- **B**: U3 用に別 workflow。→ 不要。

[Answer]: A — deploy.yml 変更なし（test → migrations〈差分なし〉→ deploy の既存フローで完結）。**beta 検証不要**（新規ランタイム機構なし。埋め込み HTML は文字列定数で F-4 実測対象の規模ではない）。既存のテスト前置ゲートが回帰を担保。

### Q3【Static Assets】参加者 `[assets]` への影響確認
- **★A（推奨）**: 管理 UI は **Static Assets を使わない**（Worker 埋め込み, BR-U3-02）ため、`wrangler.toml` の `[assets]`（参加者フロント `frontend/`）に**変更なし**。管理 UI を `frontend/` に置くと assets 公開配信で認証境界外へ漏れる（禁止, BR-U3-02）。`/admin/` は Worker（`on_fetch`）が処理し、アセットとは無関係。
- **B**: 管理 UI も `frontend/admin.html` として assets 配信。→ **BR-U3-02 違反**（公開漏れ）。不採用。

[Answer]: A — 参加者 `[assets]` に変更なし。管理 UI は Worker 埋め込み（BR-U3-02）で assets 無関係。

### Q4【Deployment】環境分離
- **★A（推奨）**: U1/U4a/U2 の **dev / prod（実験用サブドメイン）** 分離をそのまま流用。U3 固有の環境なし。参加者フロント・参加者 API・管理 API/UI・scripts が**同一 Worker / 同一 D1 / 実験用サブドメイン一本**に収束（管理は Basic 認証で分離）。
- **B**: U3 専用環境。→ 過剰。

[Answer]: A — dev/prod 分離を流用。全機能が同一 Worker / 同一 D1 / 実験用サブドメイン一本に収束（管理は Basic 認証で分離）。**動作確認**: API 応答（progress/winrates/export/401）は統合テスト（PU3-1/2/4/5）、管理 UI 自体はデプロイ後の手動確認（表示・ボタン疎通の目視・数分）。UI は「表とボタン程度」（Inception Q8 スコープ）でブラウザ自動化（Playwright 等）は導入コストに見合わず、UI の正しさの大半は「API が正しい JSON を返す」に還元（統合テストで担保）。`data-testid` 付与済み（BR-U3-10）で将来複雑化時の自動化余地は確保。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `infrastructure-design.md`（差分中心・極小）を生成 → 標準 2 択（Request Changes / Continue → **Code Generation〈U3〉**）。**Part 2 生成時に本 plan の `[Answer]:` 欄も記入する**。
