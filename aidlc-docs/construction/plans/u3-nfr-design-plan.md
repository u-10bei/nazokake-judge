# U3 NFR Design Plan — 研究者・管理（admin）

**ユニット**: U3。NFR Requirements（U3-NFR-01〜11）を設計パターン（DP-U3）と論理コンポーネント（LC-U3）に落とす。**U1/U4a の DP/LC の再利用が大半**のため差分中心。
**前提（既決）**: 認証一本化（U3-NFR-01, 既存 AuthGuard 再利用）／管理 HTML の assets 非配置=src/ 埋め込み（02）／エクスポート秘匿=no-store/ログ非出力/body 非含有/実トークン（03）／CORS なし（04）／集計は Repository 集約・Service は薄い整形層（07/09）／PBT は PU3-3 のみ（10）。読み取り専用（migration なし）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-design-patterns.md`（DP-U3-NN）/ `logical-components.md`（LC-U3-NN + 依存方向）を生成します。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-15）
- [x] `construction/u3/nfr-design/nfr-design-patterns.md`（DP-U3-01〜05: 認証ルート相乗り・no-store ヘルパ・body 型排除・集計 Repository 集約 + 純粋整形・統一封筒 + 非採用部品表）
- [x] `construction/u3/nfr-design/logical-components.md`（LC-U3-01〜06 + ビュー/バンドル型 DataContract 拡張・依存方向）

**回答サマリ**: 全 4 問 ★A。管理 HTML=`src/backend/admin/ui.py` のモジュール定数（ビルドステップなし）。集計はエンドポイント 1:1 の Repository メソッド。CSV エスケープに単体テスト集中。

---

## 設計パターン適用性評価（U3）
| 論点 | 適用 | 方針 |
|---|---|---|
| **認証/認可** | **適用（再利用）** | 既存 Basic 認証チョークポイント（DP-U4a-01）に GET ルートを相乗り。→ Q1 |
| **秘匿/データ保護** | **適用（U3 固有）** | エクスポート秘匿の強制点（no-store ヘルパ・ログ非出力・body 型排除）。→ Q2 |
| **純粋ドメインロジック** | **適用** | 集計は Repository・整形（CSV/ビュー/バンドル組立）は純関数。→ Q3 |
| **エラー処理契約** | **適用（最小限）** | 管理 API の統一エラー封筒（U4a=DP-U4a-07 に整合）。→ Q4 |
| キャッシュ/キュー/CB/ロック/スケール | **N/A** | 読み取り専用・小規模・同期（U1/U2/U4a と同方針）。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【認証/認可】GET ルートの認証相乗り
既存 `handle_admin` は POST（`/admin/items`・`/admin/tokens`）を AuthGuard 背後でディスパッチ。U3 は GET（UI・progress・winrates・export）を追加する。
- **★A（推奨）**: **既存の認証チョークポイント（`handle_admin` 入口の `check_basic`, DP-U4a-01）をそのまま通し、GET ルートを同じディスパッチに追加**。GET も POST も**単一の認証点**を必ず通る（`/admin/*` 全体が Basic 認証背後）。認証漏れの GET エンドポイントを構造的に作れない。
- **B**: GET 用に別の認証チェックを設ける。→ 二重実装・付け忘れリスク。不採用。

[Answer]: A — 既存 `handle_admin`（AuthGuard → ディスパッチ）に `GET /admin/`（UI）・`/admin/progress`・`/admin/winrates`・`/admin/export` を追加。認証の追加実装なし。補足: DP-U4a-01 のディスパッチ表拡張のみ（U3-NFR-01 の設計化）。

### Q2【秘匿/データ保護】エクスポート秘匿の「構造で守る」強制点
- **★A（推奨）**:
  - **(a) no-store＝共通レスポンスヘルパ**: エクスポート（および管理 API）応答を**共通ヘルパ経由**で生成し `Cache-Control: no-store` を必ず付与（U2 DP-U2-04 と同型）。ダウンロードは `Content-Disposition: attachment` も同ヘルパで。
  - **(b) body 非含有＝型で排除**: エクスポート型（`ExportItem` 等）に **`body` フィールドを持たせない**（`ExportItem = {item_id, layer}`）。ViewSerializer 相当の写像（domain→export 型）を 1 箇所に集約し、`body` を構造的に落とす（U2 DP-U2-02 と同型＝出自/本文を型で守る）。
  - **(c) トークン非ログ＝AdminLog 再利用**: 管理操作ログは U4a AdminLog（許可フィールド限定）を通す。トークン生値・本文を出さない。エクスポート応答本体は実トークンを含む（認証背後・正当）。
- **B**: 各呼び出し側の規律に委ねる。→ 漏出・付け忘れの温床。不採用。

[Answer]: A — (a) no-store 共通レスポンスヘルパ + Content-Disposition / (b) **body 非含有＝型で排除**（`ExportItem={item_id,layer}`・写像を 1 箇所に集約, DP-U2-02 と同型）/ (c) トークン非ログ＝AdminLog 再利用。応答本体は実トークンを含む（認証背後・正当）。

### Q3【純粋ロジック】集計と整形の分離
- **★A（推奨）**:
  - **集計は Repository の読み取りメソッド**（`progress_counts` / `provisional_winrates` / `export_rows`）に集約。**練習除外（`pairs.is_practice=0`）を SQL に埋め込み**、パラメータ化クエリ（DP-U3 秘匿/SQLi）。
  - **整形は純関数**: `ProgressView`/`WinrateRow[]`/`ExportBundle` 組立・**CSV 直列化**を副作用なしの関数として `src/backend/admin/` に置く（example ベース単体テスト可能）。ExportBundle 自己完結（judgments の item ⊆ items）は PU3-3 で PBT。
  - AdminService/ExportService は「Repository 呼び出し → 純関数整形 → レスポンスヘルパ」の薄いオーケストレーション。
- **B**: サービス層が D1 を直接触る/整形に副作用。→ I/O 境界一貫（LC-03）・テスト容易性に反する。

[Answer]: A — エンドポイント 1 本 = 集計クエリ 1 本（`read_progress()` / `read_winrates()` / `read_export_rows(entity)`）。パラメータ化・練習除外は SQL 内（出力段保証, BR-U3-03）。整形は純関数。補足: 共通クエリビルダ（B）は規模に不適。LC-03 の一貫適用。

### Q4【エラー契約】管理 API の統一エラー封筒
- **★A（推奨）**: **U4a=DP-U4a-07 と同水準**。認証失敗のみ **401 + `WWW-Authenticate`**。業務エラー（未知の `entity`/`format` 等）は簡素な統一封筒（`{ok:false, error}`）。正常時は各ビュー/バンドル（JSON）またはファイル（CSV/JSON attachment）。エクスポートは大きくなり得るが小規模ゆえストリーミング不要（一括レスポンス）。
- **B**: エンティティごとに個別 HTTP ステータス。→ 一貫性が崩れる。

[Answer]: A — U4a=DP-U4a-07 と同水準。認証失敗のみ 401 + WWW-Authenticate、業務エラーは `{ok:false,error}`、正常は各ビュー/バンドル or ファイル（attachment）。小規模ゆえストリーミング不要（一括）。補足: CSV エスケープ（カンマ・引用符・改行）が U3 唯一の間違えうる整形ロジックゆえ単体テストを集中。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-design-patterns.md`（DP-U3-NN）/ `logical-components.md`（LC-U3-NN + 依存方向）を生成 → 標準 2 択（Request Changes / Continue → **Infrastructure Design〈U3〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
