# U3 Code Generation Plan — 研究者・管理（admin）

**ユニット**: U3（C-FE-ADMIN / C-SVC-ADMIN / C-SVC-EXPORT / C-AUTH〈再利用〉/ C-API〈管理系〉）
**前段**: Functional Design / NFR Requirements / NFR Design / Infrastructure Design — すべて承認済み（2026-07-15）。
**目的**: LC-U3（AdminApi 拡張 / AdminService / ExportService / 純粋整形 / Repository 集計拡張 / AdminUI）を実コードに落とす。**既存 `/admin/*` 境界（Basic 認証・handle_admin）と Repository を拡張**する。**読み取り専用**（migration なし）。

> 実装規約（G-1/F-8 確定）: raw workers API + Pydantic v2 / module-level `on_fetch` / **src/ レイアウト**（新規 backend は `src/backend/admin/` 配下）/ トップレベル import 最小限（F-4）。

このドキュメントは **Part 1（Plan + 決定点）**。承認後 Part 2 で本計画を**単一の真実**として生成する。

---

## 1. ユニット・コンテキスト

| 項目 | 内容 |
|---|---|
| **実装ストーリー** | US-R01（進捗モニタリング）/ US-R02（エクスポート CSV/JSON）/ US-R03（暫定勝率テーブル）。横断 XC-03（Basic 認証・SQLi）・XC-04 波及（管理 UI・意識的逸脱 BR-U3-10）。 |
| **依存** | U1 公開面（schema・Repository・`EXPORT_FORMAT_VERSION`）、U4a（`check_basic`/`unauthorized`・`handle_admin`・`admin_log` 再利用）、U2 の蓄積データ（judgments/pairs/likert/survey/tokens/items）。層の逆流禁止。 |
| **所有 D1 エンティティ** | なし（読み取り専用）。**migration なし・DDL 変更なし**。 |
| **サービス境界** | 集計は Repository、整形は純関数、UI は Worker 埋め込み配信。 |

**スコープ外**: `bt_aggregate`（U4b）、参加者フロー（U2）、トークン発行・プール投入（U4a）。**変更しないもの**: `migrations/`・`wrangler.toml`・`deploy.yml`・`frontend/`（参加者 assets）。

---

## 2. 生成ステップ（番号付き・Part 2 の単一の真実）

- [x] **Step 1 — schema ビュー/バンドル型**: `src/schema/admin_views.py`（新規）に `ProgressView`・`WinrateRow`・`ExportBundle`・`ExportItem`（`{item_id, layer}`＝**body なし**）・`ExportJudgment`（`{token, pair_id, pair_index, item_left, item_right, choice, created_at}`）・`ExportLikert`・`ExportSurvey`。`ExportBundle = {schema_version, exported_at, items, judgments, likert, surveys}`。`src/schema/__init__.py` に公開。
- [x] **Step 2 — Repository 集計拡張**: `src/backend/repo/repository.py` に `read_progress()`（tokens 状態カウント + 本番 judgments/likert/survey 数）・`read_winrates()`（judgments×pairs, `is_practice=0`, item ごと matches/wins + layer）・`read_export_rows(entity)`（items / judgments〈pairs join・本番のみ・`idx AS pair_index`〉/ likert / surveys）。**全パラメータ化・練習除外は SQL の WHERE 句**（BR-U3-03）。読み取りのみ。
- [x] **Step 3 — 純粋整形（CSV/ビュー/バンドル）**: `src/backend/admin/format.py`（新規）に `to_csv(headers, rows) -> str`（**標準 `csv` モジュール `io.StringIO + csv.writer` による RFC4180 準拠出力**。手書きエスケープはしない, U3 CG Q3 確定）、`build_progress(row) -> ProgressView`、`build_winrates(rows) -> list[WinrateRow]`、`build_export_bundle(rows, now) -> ExportBundle`。副作用なし。
- [x] **Step 4 — AdminService / ExportService**: `src/backend/admin/service.py`（新規）に `get_progress(repo)`・`get_winrates(repo)`・`export(repo, format, entity, now)`（JSON=ExportBundle / CSV=エンティティ別）。Repository → 純関数整形の薄いオーケストレーション。
- [x] **Step 5 — AdminUI 埋め込み**: `src/backend/admin/ui.py`（新規）に管理 HTML/JS/CSS 一体の**モジュール定数**（進捗サマリ + 暫定勝率テーブル〈非BT 注記〉 + エクスポート DL）。`data-testid` 付与（`admin-refresh-button`/`admin-export-json-button`/`admin-export-csv-<entity>-button`/`winrate-table`）。デスクトップ主・日本語。
- [x] **Step 6 — handle_admin GET 配線**: `src/backend/admin/api.py` の `handle_admin` に GET ディスパッチ追加（既存 AuthGuard の背後）: `GET /admin/`（`ui.py` の HTML を `text/html` で返す）・`/admin/progress`・`/admin/winrates`・`/admin/export`。**共通レスポンスヘルパで `no-store`**、エクスポートは `Content-Disposition: attachment`（DP-U3-02/05）。`admin_log` で秘匿ログ（トークン・本文非出力）。未知 GET は既存 404。
- [x] **Step 7 — unit テスト**: `tests/unit/u3/` に純粋整形の example テスト（**CSV エスケープの境界**: カンマ/引用符/改行/日本語、ProgressView/WinrateRow 変換、ExportBundle 組立の構造・自己完結性）。
- [x] **Step 8 — PBT（PU3-3）**: `tests/pbt/test_export_selfcontained.py`（**ExportBundle 自己完結**: judgments に現れる item_id ⊆ items を生成データで反例探索）。他 PBT 強制は U3 非該当（U3-NFR-10）。
- [x] **Step 9 — integration**: `tests/integration/drive_u3.py`（`/admin/*` 越し PU3-1 練習除外の出力段保証 / PU3-2 winrate 定義整合 / PU3-4 進捗カウント整合 / PU3-5 認証 401）。ハーネス流用（`src/` 同期・Basic 認証）。実行実績提示。
- [x] **Step 10 — U1/U2/U4a 回帰 + Documentation**: 既存 unit+PBT を緑に保つ（schema 追加は独立ゆえ影響なしの想定を確認）。`aidlc-docs/construction/u3/code/README.md` にサマリ・API 一覧・PU3 対応・curl 例。README のディレクトリ構成に `backend/admin`（U3 拡張）反映。

---

## 3. Part 1 決定点（★推奨デフォルト付き。回答は各 [Answer] に記入）

### Q1【集計クエリの結合方針】winrate/export の judgments×pairs 結合
- **★A（推奨）**: `judgments j JOIN pairs p ON j.token=p.token AND j.pair_id=p.pair_id WHERE p.is_practice=0`。winrate は item_left/item_right を UNION 展開して item 単位に集計、export は行をそのまま出す（pair_index=`p.idx`）。単一クエリ・パラメータ化。
- **B**: アプリ側で judgments と pairs を突合。→ I/O 境界一貫（LC-03）・SQL 集約（BR-U3-09）に反する。

[Answer]: A — `judgments j JOIN pairs p ON j.token=p.token AND j.pair_id=p.pair_id WHERE p.is_practice=0` を正とし、winrate は item_left/item_right の UNION 展開で item 単位集計、export は `p.idx AS pair_index` で行をそのまま出力。単一クエリ・全パラメータ化。BR-U3-03/09・LC-03 に整合。B はメモリ突合で Workers CPU 制約と相性が悪く不採用。

### Q2【schema 型ファイルの配置】ビュー/バンドル型の置き場
- **★A（推奨）**: **`src/schema/admin_views.py`（新規）**に U3 の型をまとめ、`schema/__init__` で公開（U2 の `views.py` と対をなす命名）。単一データ契約（Worker が返し、将来 curl/U4b が読む）。
- **B**: 既存 `views.py` に相乗り。→ 参加者ビューと管理/エクスポートで責務が異なる。分離が明快。

[Answer]: A — `src/schema/admin_views.py` 新規、`schema/__init__` で公開。ExportBundle は BR-U3-07 で正本固定した契約＝U4b が入力の正として参照する型のため、参加者ビュー（views.py）と分離して契約の参照点を明確に保つ。

### Q3【エクスポート応答の生成】JSON/CSV の返し方
- **★A（推奨）**: JSON は `ExportBundle.model_dump_json()`、CSV は `to_csv` 純関数の出力。両者を**共通レスポンスヘルパ**（`no-store` + `Content-Disposition: attachment; filename=export-<entity>-<ts>.{json,csv}`）で返す。`entity` 既定は json 時 = 全部（bundle）、csv 時 = 必須（未指定は 400 相当）。
- **B**: 各所で個別に Response 生成。→ no-store 付け忘れリスク（DP-U3-02）。

[Answer]: A ＋ 一点修正: **`to_csv` は標準 csv モジュール（io.StringIO + csv.writer）で RFC4180 準拠出力**（手書きエスケープ不採用）。Step 3 の「カンマ・引用符・改行のエスケープ」は「標準 csv モジュールによる RFC4180 準拠出力」に読み替え（Step 7 のテスト観点は不変）。共通レスポンスヘルパ（no-store + `Content-Disposition: attachment; filename=export-<entity>-<ts>.{json,csv}`）、json 既定=bundle 全部、csv 時 entity 必須（未指定 400）。**filename の `<ts>` は exported_at と同一値**（監査証跡を揃える）。

### Q4【回帰の扱い】既存テストの完了基準
- **★A（推奨）**: schema 追加・Repository 読み取り追加・handle_admin GET 追加が既存を壊さないことを確認し、**既存 unit+PBT（U1/U2/U4a）+ U3 追加分をすべて緑**にしてから完了（ブロッキング）。integration は実 D1 実行実績を提示。
- **B**: U3 追加分のみ検証。→ 回帰見落としリスク。不採用。

[Answer]: A — handle_admin GET 追加は U4a の既存コードパスに触るため、U1/U2/U4a の unit+PBT 全緑をブロッキング条件とする。integration は実 D1 実行実績を提示。

---

## 4. 完了基準
- [x] 全 Step `[x]`。schema 型・Repository read_*・純粋整形・Service・ui.py・handle_admin GET 配線が生成。
- [x] **U1/U2/U4a 回帰含め全テスト緑**（unit+PBT: PU3-3 追加）、integration（`/admin/*` 越し PU3-1/2/4/5）実行実績。
- [x] **migration/wrangler.toml/deploy.yml の変更なし**を確認。
- [x] `aidlc-docs/construction/u3/code/README.md` サマリ。標準 2 択（Request Changes / Continue → Build & Test〈U3〉）。

---

**Part 2 生成時の運用**: 各 Step を順に生成し完了ごとに `[x]`、対応ストーリーも `[x]`。**本 plan の [Answer] 欄を記入**（監査証跡の自己完結）。integration のリモート実機部分はユーザー/エージェント環境の実行実績を提示。
