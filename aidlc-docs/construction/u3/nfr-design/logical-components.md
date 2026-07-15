# U3 Logical Components — 研究者・管理（admin）

**方針**: U3 は U1（schema・Repository・LogEmitter）と U4a（AuthGuard・handle_admin・AdminLog）を**消費・拡張**し、管理系の集計・エクスポート・UI を追加する。専用インフラ部品（queue/cache/CB/lock）は導入しない（DP-U3 非採用表）。**読み取り専用**（書き込みなし・migration なし）。層の逆流禁止。新規 backend は `src/backend/admin/` 配下（F-8）。

---

## 論理コンポーネント一覧

### LC-U3-01: AdminApi 拡張（`src/backend/admin/api.py`, U4a LC-U4a-01 拡張）
- **役割**: `handle_admin` に **GET ルートを追加ディスパッチ**（`/admin/`・`/admin/progress`・`/admin/winrates`・`/admin/export`）。既存 AuthGuard（LC-U4a-02）を必ず通す（DP-U3-01）。**共通レスポンスヘルパ**で no-store + 統一封筒 + attachment（DP-U3-02/05）。
- **依存**: LC-U4a-02（AuthGuard 再利用）、LC-U3-02〜04、LC-U4a-05（AdminLog 再利用）。

### LC-U3-02: AdminService（`src/backend/admin/`）
- **役割**: `get_progress`（→ ProgressView）・`get_provisional_winrates`（→ list[WinrateRow]）。Repository 集計を**純関数整形**で view 型へ（薄い層）。
- **依存**: Repository（集計読み取り, LC-U3-05）、schema（ビュー型）。

### LC-U3-03: ExportService（`src/backend/admin/`）
- **役割**: `export(format, entity)`。Repository の export_rows を **ExportBundle 組立（JSON 正本）** または **CSV 純粋直列化**（エンティティ別）へ。`schema_version`/`exported_at` 付与、**body 非含有**（型で排除, DP-U3-02(b)）。
- **依存**: Repository（export_rows）、schema（バンドル型・EXPORT_FORMAT_VERSION）、CSV 直列化純関数（LC-U3-04）。

### LC-U3-04: 純粋整形関数（`src/backend/admin/`）
- **役割**: `rows → csv_text`（カンマ/引用符/改行エスケープ）、ExportBundle/ProgressView/WinrateRow 組立。**副作用なし**＝example 単体テスト。ExportBundle 自己完結は PU3-3 で PBT。
- **依存**: schema（型）のみ。

### LC-U3-05: Repository 集計拡張（`src/backend/repo/repository.py`, U1 LC-03 拡張）
- **役割**: `read_progress()`（tokens 状態カウント + 本番判定/likert/survey 数）・`read_winrates()`（judgments×pairs, is_practice=0, item ごと matches/wins）・`read_export_rows(entity)`（items / judgments〈pairs join・本番のみ・pair_index〉/ likert / surveys）。**全パラメータ化・練習除外を SQL に**（DP-U3-03）。**読み取りのみ**。
- **依存**: schema、`_d1` ヘルパ。Worker 内専用。

### LC-U3-06: AdminUI（`src/backend/admin/ui.py`）
- **役割**: 管理 HTML/JS/CSS 一体の**モジュール定数**（進捗 + 暫定勝率 + エクスポート）。`handle_admin` が `GET /admin/` で返す（**assets 非配置**, BR-U3-02）。デスクトップ主・日本語・非BT 明示・`data-testid`。ビルドステップなし。
- **依存**: なし（静的文字列）。ブラウザから `/admin/*`（Basic 認証背後）を叩く。

### DataContract 拡張（U1 LC-01 = `src/schema/`, U3 波及）
- **ビュー/バンドル型追加**: `ProgressView` / `WinrateRow` / `ExportBundle`（+ `ExportItem`〈body なし〉/ `ExportJudgment`〈pair_index 込み〉/ `ExportLikert` / `ExportSurvey`）。`ExportBundle.schema_version = EXPORT_FORMAT_VERSION`。**DDL 変更なし**（読み取り専用）。

---

## 依存方向（層の逆流禁止）

```
[ブラウザ 管理UI (LC-U3-06 が返した HTML)] ──HTTPS + Basic──►  ┐
                                                             ▼
      ┌──────────── LC-U3-01 AdminApi 拡張 (handle_admin, GET 追加) ────────────┐
      │  入口: AuthGuard 再利用(LC-U4a-02) / no-store+封筒+attachment(DP-U3-02/05) │
      │   → LC-U3-02 AdminService   → LC-U3-04 純粋整形(CSV/ビュー/バンドル)       │
      │   → LC-U3-03 ExportService  → LC-U4a-05 AdminLog(秘匿・再利用)             │
      │   → LC-U3-06 AdminUI(/admin/ で HTML 返却)                                 │
      └───────────────┬───────────────────────────────────────────────────────────┘
                       │ import（公開面のみ）
          ┌────────────▼───────────┐        ┌───────────────────────────┐
          │ LC-U3-05 Repository 集計 │        │ LC-01 DataContract         │
          │ 拡張 (read_*・読み取り専用) ├───────►│ (src/schema, U3 でビュー/   │
          └────────────┬───────────┘        │  バンドル型追加・DDL 不変)  │
                       │                      └───────────────────────────┘
                    [ D1 ]（読み取りのみ・migration なし）
```

- **一方向依存**: ブラウザは `/admin/*` のみ、AdminApi は U1/U4a 公開面（Repository/AuthGuard/AdminLog）+ schema。**U3 から上位（U4b）への依存なし**。集計は Repository、整形は純関数（副作用なし）。
- **秘匿は 2 点集約**: no-store/封筒はレスポンスヘルパ、body 非含有は export 型（DP-U3-02）、トークン非ログは AdminLog（再利用）。

---

## 後続への申し送り（Infrastructure Design / Code Generation）
- **Infrastructure Design（U3）**: 既存 Worker/D1/デプロイを流用・**migration なし・新規シークレットなし・CORS なし**。差分は `/admin/*` の GET ルート追加のみ（極小）。管理 UI は Worker 配信（assets 追加不要）。
- **Code Generation**: `src/backend/admin/`（api 拡張・AdminService・ExportService・純粋整形・ui.py）、`src/backend/repo` の read_* 追加、`src/schema/` ビュー/バンドル型、unit（整形・CSV エスケープ）+ PBT（PU3-3）+ integration（PU3-1/2/4/5・`/admin/*` 越し）。
