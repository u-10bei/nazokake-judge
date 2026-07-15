# U3 Tech Stack Decisions — 研究者・管理（admin）

U1 の TSD-01〜08・U4a の TSD-U4a-01〜06・U2 の TSD-U2-01〜06 を前提に、U3 追加分を **TSD-U3-NN** で定義する。案 A′（raw workers API + Pydantic v2, **src/ レイアウト F-8**）・uv+pywrangler・CI デプロイは確定済み。U3 は既存 `/admin/*` 境界を拡張する。

---

## TSD-U3-01: 認証・境界の再利用
- **U4a の AuthGuard（`src/backend/admin/auth.py`）・`handle_admin` ディスパッチをそのまま再利用**。U3 は `GET /admin/`（UI）・`/admin/progress`・`/admin/winrates`・`/admin/export` を `handle_admin` に**追加ディスパッチ**するのみ（新規認証・新規資格なし）。単一資格 `ADMIN_BASIC_*`。CORS なし（同一オリジン）。
- 根拠: U3-NFR-01/04, BR-U3-01。

## TSD-U3-02: 管理 UI の配信（src/ 埋め込み）
- **管理 HTML/JS は `src/backend/admin/` 配下の埋め込み文字列（モジュール・定数）**として保持し、`handle_admin` が `GET /admin/` で `text/html` を返す。**Static Assets（`frontend/`）には置かない**（公開漏れ防止, U3-NFR-02）。小 HTML ゆえトップレベル import 最小維持で F-4（起動 CPU 制限）影響は無視できる。
- 根拠: U3-NFR-02, BR-U3-02。

## TSD-U3-03: 集計 SQL の Repository 集約
- 進捗カウント・暫定勝率・エクスポート join の**集計 SQL は Repository の読み取りメソッド**に集約（`progress_counts` / `provisional_winrates` / `export_rows`）。**すべてパラメータ化クエリ**（SQLi 対策, U3-NFR-05）。**練習除外（`pairs.is_practice=0`）を SQL に埋め込む**（出力段保証, BR-U3-03）。
- AdminService/ExportService は Repository 結果を **ProgressView / WinrateRow[] / ExportBundle へ整形する薄い層**（純粋部分は関数化＝単体テスト可能）。
- 根拠: U3-NFR-07/09, BR-U3-09。

## TSD-U3-04: ビュー/バンドル型と CSV 直列化
- **`ProgressView` / `WinrateRow` / `ExportBundle`（+ `ExportItem`/`ExportJudgment`/`ExportLikert`/`ExportSurvey`）を `src/schema/` に追加**（Pydantic v2, 単一データ契約）。`ExportBundle.schema_version = EXPORT_FORMAT_VERSION`。
- **CSV 直列化は純粋関数**（エンティティ別・ヘッダ + 行）。JSON は Pydantic の `model_dump_json`。エクスポート応答は `Content-Disposition: attachment` + `Cache-Control: no-store`（U3-NFR-03）。
- 根拠: U3-NFR-03, BR-U3-06/07。

## TSD-U3-05: テスト
- **unit**（`tests/unit/u3/`）: CSV 直列化・ProgressView/WinrateRow 変換・ExportBundle 組立（構造・自己完結性 PU3-3）。
- **PBT**（`tests/pbt/`）: **PU3-3 のみ**（ExportBundle 自己完結: judgments の item ⊆ items を生成データで検証）。他の PBT 強制セットは U3 非該当（U3-NFR-10）。
- **integration**（`tests/integration/`, `/admin/*` 越し）: PU3-1（練習除外の出力段保証）・PU3-2（winrate 定義整合）・PU3-4（進捗カウント整合）・PU3-5（認証 401）。ハーネス流用（`src/` レイアウト同期）。
- 根拠: U3-NFR-09/10, Q4。

---

## 決定サマリ
| ID | 決定 |
|---|---|
| TSD-U3-01 | AuthGuard/handle_admin 再利用・GET ルート追加・CORS なし |
| TSD-U3-02 | 管理 HTML は src/ 埋め込みで Worker 配信（assets 非配置） |
| TSD-U3-03 | 集計 SQL は Repository 集約・練習除外を SQL に・Service は薄い整形層 |
| TSD-U3-04 | ビュー/バンドル型を schema/ に・CSV 純粋直列化・no-store + attachment |
| TSD-U3-05 | unit（整形）+ PBT（PU3-3 のみ）+ integration（集計・401） |

## 後続への申し送り
- **NFR Design**: 認証再利用・エクスポート秘匿（no-store/ログ非出力/body 非含有）・集計の Repository 集約を DP/LC に落とす。
- **Infrastructure Design**: U3 は既存 Worker/D1/デプロイを流用・**migration なし**・新規シークレットなし。差分は `/admin/*` の GET ルート追加のみ（極小）。
- **Code Generation**: `src/backend/admin/`（AdminService/ExportService/管理 UI 埋め込み・handle_admin 拡張）、`src/backend/repo` 集計読み取り、`src/schema/` ビュー/バンドル型、unit/PBT/integration。
