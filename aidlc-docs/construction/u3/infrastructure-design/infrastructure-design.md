# U3 Infrastructure Design — 研究者・管理（admin）

**ユニット**: U3。**U1/U4a/U2 の共有インフラ（D1 + 同一 Worker + CI デプロイ + Basic 認証）を全面流用**し、差分のみを定義する。共有分は `shared-infrastructure.md`、実装規約（F-1〜F-8）は U1 `infrastructure-design.md §2.1`、CI（`deploy.yml`）は U4a `§5`、静的配信（`[assets]`）は U2 `§2` を参照。
**方針**: **新規インフラは実質ゼロ**。差分は **`/admin/*` への GET ルート追加のみ**（同一 Worker・同一 Basic 認証背後）。**migration なし（読み取り専用）・新規シークレットなし・CORS なし・`[assets]` 変更なし・`deploy.yml` 無変更**。

---

## 1. LC-U3 → インフラ マッピング（差分）

| 論理コンポーネント | インフラ | 備考 |
|---|---|---|
| **LC-U3-01 AdminApi 拡張** | 既存 Worker の `handle_admin` に **GET ルート追加**（`/admin/`・`/admin/progress`・`/admin/winrates`・`/admin/export`, Q1=A） | 別 Worker にしない（U4a-NFR-02）。既存 AuthGuard を通す |
| **LC-U3-02/03/04 Service・整形** | Worker 内 compute（純粋整形含む） | インフラ依存なし |
| **LC-U3-05 Repository 集計拡張** | 既存 **D1 バインディング（`DB`）** 経由・**読み取りのみ** | **migration なし**（DDL 変更なし） |
| **LC-U3-06 AdminUI** | **Worker が `GET /admin/` で HTML 返却**（`src/backend/admin/ui.py` 定数） | **Static Assets 不使用**（BR-U3-02）。`[assets]` 変更なし |
| AuthGuard / AdminLog（再利用） | 既存（U4a） | 新規シークレット・新規認証なし |

---

## 2. Compute / Networking（Q1）
- `/admin/*` の GET ルートを**参加者 API・管理 POST（U4a）と同一 Worker・同一サブドメイン**に追加。管理 UI も同一 Worker が `GET /admin/` で返す。
- **CORS なし**（同一オリジン, U3-NFR-04 で決着）。管理系は Basic 認証で参加者系（`/api/*`）と分離。

## 3. Secrets（差分なし）
- **新規シークレットなし**。`ADMIN_BASIC_USER`/`ADMIN_BASIC_PASSWORD`（U4a・手元 `wrangler secret put`）を再利用。`.dev.vars` 追加項目なし。

## 4. Storage（読み取りのみ・migration なし）
- U3 は既存 D1 を**集計参照するだけ**（`read_progress`/`read_winrates`/`read_export_rows`）。**DDL 変更なし＝migration 追加なし**（0001〜0003 のまま）。全読み取りはパラメータ化クエリ・練習除外を SQL に（BR-U3-03）。

## 5. CI/CD（`deploy.yml` 無変更, Q3）
- **`deploy.yml` は無変更**。既存フロー `uv sync → test（unit+PBT）→ d1 migrations apply --remote（0001〜0003, 追加なし＝no-op）→ deploy` で U3 も配布される。テスト前置ゲートが回帰を担保。
- **beta 検証不要**（新規ランタイム機構なし。埋め込み HTML は文字列定数で F-4 実測対象の規模ではない）。

## 6. Static Assets（無関係, Q2 確認）
- 管理 UI は **Worker 埋め込み配信**（BR-U3-02）＝`wrangler.toml` の `[assets]`（参加者 `frontend/`）に**変更なし**。管理 UI を `frontend/` に置くことは公開漏れ（BR-U3-02 違反）ゆえ禁止。

## 7. エクスポートの受け取り経路（Q2）
- **ブラウザ**（Basic 認証セッション）から `GET /admin/export?format=json|csv` を直接ダウンロード（`Content-Disposition: attachment`）。
- **CLI 経路**（同一認証境界）: `curl -u $ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD -o export.json "https://<host>/admin/export?format=json"`。
  → **U4b の入力取得をスクリプト/CI で自動化する場合は curl 経路が正**（U4b Infrastructure への申し送り）。

## 8. Deployment / 動作確認（Q4）
- dev / prod（実験用サブドメイン）分離を流用。参加者フロント・参加者 API・管理 API/UI・scripts が**同一 Worker / 同一 D1 / 実験用サブドメイン一本**に収束（管理は Basic 認証で分離）。
- **動作確認**: API 応答（progress/winrates/export/401）は **統合テスト**（PU3-1/2/4/5・`/admin/*` 越し）。管理 UI 自体は**デプロイ後の手動確認**（表示・ボタン疎通の目視・数分）。UI は「表とボタン程度」（Inception Q8 スコープ）ゆえブラウザ自動化は導入コストに見合わず、UI の正しさの大半は「API が正しい JSON を返す」に還元。`data-testid` 付与済み（BR-U3-10）で将来の自動化余地は確保。

## 9. トレーサビリティ
| 項目 | 対応 |
|---|---|
| /admin/* GET ルート追加・同一 Worker | Q1 / U3-NFR-01 / LC-U3-01 |
| 管理 UI Worker 配信・assets 非配置 | Q2 / BR-U3-02 / LC-U3-06 |
| migration なし（読み取り専用） | U3-NFR-07 / LC-U3-05 |
| deploy.yml 無変更・beta 不要 | Q3 |
| CORS なし・新規シークレットなし | U3-NFR-04 / Secrets 差分なし |
| curl 経路を U4b 自動化の正 | Q2 補足（U4b 申し送り） |

## 10. 後続申し送り（Code Generation / U4b）
- **Code Generation（U3）**: `src/backend/admin/`（api 拡張・AdminService・ExportService・純粋整形・ui.py）、`src/backend/repo` の read_* 追加、`src/schema/` ビュー/バンドル型、unit（整形・CSV エスケープ）+ PBT（PU3-3）+ integration（PU3-1/2/4/5）。**migration・wrangler.toml・deploy.yml の変更なし**。
- **U4b Infrastructure**: エクスポート取得は curl 経路（Basic 認証）を自動化の正とする。`schema_version` を検証して読む。
