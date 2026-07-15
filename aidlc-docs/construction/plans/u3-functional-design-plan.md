# U3 Functional Design Plan — 研究者・管理（admin）

**ユニット**: U3（`C-FE-ADMIN` / `C-SVC-ADMIN` / `C-SVC-EXPORT` / `C-AUTH`〈再利用〉/ `C-API`〈管理系〉）
**目的**: 研究者の管理機能（進捗モニタリング US-R01 / 回答データエクスポート US-R02 / 暫定勝率テーブル US-R03）の業務ロジックを設計する。横断 XC-03（Basic 認証・SQLi）、波及 XC-04（管理 UI のモバイル/日本語）。
**前提（既決）**: U1（schema・Repository・`EXPORT_FORMAT_VERSION=1.0.0`）、U4a（**Basic 認証チョークポイント `/admin/*`**・AdminApi・AdminLog を先行導入済み）、U2（参加者データが `judgments`/`likert_responses`/`survey_responses`/`sessions`/`pairs` に蓄積）。**U3 は既存の Basic 認証境界を再利用**して管理エンドポイントを追加する。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `business-logic-model.md` / `business-rules.md` / `domain-entities.md` / `frontend-components.md`（UI ありのため生成）を作成します。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-15）
- [x] `construction/u3/functional-design/business-logic-model.md`（進捗/暫定勝率/エクスポートの各フロー・集計の Repository 集約・Testable Properties PU3-1〜5・U4b 申し送り）
- [x] `construction/u3/functional-design/business-rules.md`（BR-U3-01〜: 認証一本化・管理 HTML の assets 非配置・練習除外の出力段保証・エクスポート契約の版管理・非BT 明示・XC-04 逸脱）
- [x] `construction/u3/functional-design/domain-entities.md`（**ExportBundle 正本**〈items/pair_index/exported_at 追加〉・ProgressView・WinrateRow・U4b 入力契約）
- [x] `construction/u3/functional-design/frontend-components.md`（管理画面 = 進捗 + 暫定勝率 + エクスポート、Worker 配信・Basic 認証背後・デスクトップ主）

**回答サマリ**: Q1=X（★A + items{item_id,layer} / pair_index / exported_at を契約に追加）、Q2〜Q7=A。Q4 補足=管理 HTML は assets 非配置（src/ 埋め込み）、Q7 補足=XC-04 からの意識的逸脱を記録。

---

## 中核論点（このユニットの肝）

U1/U4a が土台（データ契約・I/O 境界・**Basic 認証チョークポイント**・エクスポート形式版）を提供済み。U3 の肝は 3 点:

1. **エクスポート契約の確定（最重要）**。US-R02 は「**エクスポート形式を US-R04（BT 集計 = U4b）の入力仕様と一致させ、この整合を本ストーリーで固定**する」と規定。U4b は未実装のため、**U3 のエクスポートが BT 集計の入力契約を定義**する。BT 推定に必要な情報（各比較の 2 項目と勝者、練習除外、トークン紐付け）を過不足なく含めることが核。→ **Q1 が最重要**。
2. **管理 UI の配信・認証境界**。既存 Basic 認証チョークポイント（DP-U4a-01, `/admin/*`）を管理 UI・管理 API にどう及ぼすか。参加者系（`/api/*` トークン=資格）とは別境界。→ **Q4**。
3. **進捗・暫定勝率の集計意味論**。練習除外（本番のみ）、非 BT の簡易勝率、トークン status カウント。→ **Q2/Q3**。

**U1/U4a が既に提供し U3 で再設計しないもの**（前提固定）:
- Basic 認証チョークポイント（`check_basic` / `unauthorized`, `backend/admin/auth.py`）と `/admin/*` ディスパッチ（`handle_admin`）。
- AdminLog（秘匿ログ）、Repository（読み取り群）、`EXPORT_FORMAT_VERSION`、schema モデル。
- F-8（`src/` レイアウト）: **U3 の新規 backend コードも `src/backend/admin/` 配下**に置く。

## スコープ境界
- **U3 に含む**: 管理エンドポイント（`GET /admin/progress`・`/admin/winrates`・`/admin/export`）を既存 `handle_admin` に追加、AdminService（進捗・暫定勝率の集計）、ExportService（CSV/JSON・形式版付与）、管理 UI（`frontend/` の管理画面）、Repository への集計読み取り追加、schema へのビュー/エクスポート型追加。
- **U3 に含まない**: `bt_aggregate`（U4b・オフライン BT 推定）、参加者フロー（U2）、トークン発行・プール投入（U4a 実装済み）。
- **依存**: U1 公開面・U4a 認証境界のみ。層の逆流禁止。

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【最重要・エクスポート契約】ExportBundle の形式（US-R04/U4b BT 入力の固定）
BT 集計に必要な「各比較の 2 項目と勝者」をどう表現するか。判定行（`judgments`）は `pair_id` のみで item を持たないため、`pairs` と join が必要。
- **★A（推奨）**: **`ExportBundle = { schema_version, judgments, likert, surveys }`**。
  - `judgments`: `pairs` と join し **本番のみ（練習除外）**、各行 `{ token, pair_id, item_left, item_right, choice, created_at }`（`choice=A`→item_left 勝ち）。→ U4b は変換なしで winner/loser を導出可能。
  - `likert`: `{ token, target_ref, rating, created_at }`。
  - `surveys`: `{ token, answers, created_at }`。
  - **トークン単位で紐付く**（評価者相対性分析, US-R02）。`schema_version = EXPORT_FORMAT_VERSION`（1.0.0）を付与。
  - **練習は除外**（`is_practice=1` をサーバが弾く。US-P02「集計対象外」を出力段で保証。U4b にフィルタ責務を残さない）。
- **B**: judgments を pair_id のみで出し、item 解決を U4b に委ねる。→ 「変換なしで読み込める」（US-R02）に反する。
- **C**: 判定を winner/loser の 2 列に正規化して出す。→ 位置情報（left/right）が失われ、位置バイアス分析ができない。A の item_left/item_right + choice が上位互換。

[Answer]: X — ★A をベースに 3 点追加して確定。**確定形**:
```
ExportBundle = {
  schema_version,   # EXPORT_FORMAT_VERSION (1.0.0)
  exported_at,      # ISO 8601（スナップショット時点・追加③）
  items:     [{ item_id, layer }],                                   # 追加①（body は含めない）
  judgments: [{ token, pair_id, pair_index, item_left, item_right,   # pair_index 追加②
                choice, created_at }],  # 本番のみ（練習は出力段で除外）
  likert:    [{ token, target_ref, rating, created_at }],
  surveys:   [{ token, answers, created_at }],
}
```
理由: ①**items{item_id,layer}** で U4b が層情報を自己完結取得（US-R04「プロ水準に対する相対位置」に必須。投入 JSON を第二入力にしない＝「変換なしで読み込める」US-R02 を守る。body は未公表刺激ゆえ非格納）。②**pair_index**（`pairs.idx` join 1 列）で順序効果分析（U1 FD 追加規則 2 の系譜）。③**exported_at** で反復エクスポート運用のスナップショット自己記述。★A 維持: item_left/item_right+choice の位置情報保存、練習除外の出力段保証（U4b にフィルタ責務を残さない）。

### Q2【進捗の集計意味論】ProgressView の内訳（US-R01）
- **★A（推奨）**: `ProgressView = { tokens_issued, tokens_started, tokens_completed, judgments_total, likert_total, survey_total }`。
  - `tokens_issued` = 全 tokens 行数、`tokens_started` = status ∈ {in_progress, completed}、`tokens_completed` = status=completed。
  - `judgments_total` = **本番判定のみ**（練習除外, 集計の一貫性）。`likert_total`/`survey_total` は補助。
  - 「発行/開始/完了数と総回答数」（US-R01 受入基準）を満たす。
- **B**: 総回答数に練習も含める。→ 進捗の意味が曖昧（練習は集計対象外なのに数に混ぜる）。

[Answer]: A — `ProgressView = { tokens_issued, tokens_started, tokens_completed, judgments_total（本番のみ）, likert_total, survey_total }`。

### Q3【暫定勝率の算出】WinrateRow（US-R03・簡易・非 BT）
- **★A（推奨）**: `judgments`（本番のみ）を `pairs` と join し、各 item について **`matches`（出現した本番比較数）・`wins`（選ばれた回数）・`winrate = wins/matches`** を算出。`choice=A`→item_left の勝ち。`WinrateRow = { item_id, layer, matches, wins, winrate }`。**「簡易表示であり正式 BT ではない」旨を UI に明示**（US-R03）。matches=0 の item は winrate=0 または非表示（決定は frontend）。軽量な単一集計クエリ（US-R03「実装は軽量」）。
- **B**: 対戦相手ごとの詳細行列。→ US-R03 の「簡易・軽量」を超える。

[Answer]: A — `WinrateRow = { item_id, layer, matches, wins, winrate }`（本番のみ・非 BT の明示・軽量単一集計）。

### Q4【認証境界・管理 UI 配信】管理 UI と管理 API をどの境界に置くか
既存 Basic 認証チョークポイント（`/admin/*`, DP-U4a-01）の及ぼし方。
- **★A（推奨）**: **管理 UI（HTML）も管理 API も `/admin/*` に置き、既存 Basic 認証チョークポイントの背後に一本化**。`GET /admin/`（or `/admin/ui`）が管理画面 HTML を返し（Worker が返す。Static Assets の公開配信にはしない）、`GET /admin/progress`・`/admin/winrates`・`/admin/export` がデータを返す。ブラウザは `/admin/*` で一度 Basic 認証ダイアログを出し、以降のフェッチも同資格。**認証境界一本化**（DP-U4a-01 の思想）で「一般の評価者トークンでは開けない」（US-R01）を構造的に担保。
- **B**: 管理 UI を Static Assets（公開）にし、API のみ Basic 認証。→ UI シェルが公開されるうえ、ブラウザ fetch の Basic 資格管理が煩雑。
- **C**: 管理 UI を別 Worker/サブドメインに分離。→ 小規模に過剰（U4a NFR-02 と同方針で否決）。

[Answer]: A — 管理 UI（HTML）も管理 API も `/admin/*` に置き、既存 Basic 認証チョークポイントに一本化。**補足（business-rules 化）**: **管理 HTML を `frontend/`（Static Assets）に置いてはならない**（assets は公開配信＝置いた瞬間 B 案に化ける）。Workers は実行時にファイルを読めないため、**管理 HTML は `src/` 配下の埋め込み文字列（モジュール）として保持し Worker が返す**。小さな HTML ゆえ F-4（起動 CPU 制限）への影響は無視できる。

### Q5【エクスポート配信】CSV/JSON の返し方
- **★A（推奨）**: `GET /admin/export?format=json` は **単一 `ExportBundle`（JSON）** を返す（US-R04 が読む正本）。`format=csv` は **エンティティ別（judgments/likert/surveys）に分けた CSV** を返す（1 リクエスト 1 エンティティ: `?format=csv&entity=judgments` 等、または既定で judgments）。`Content-Disposition: attachment` でダウンロード。CSV は Excel 等での目視用途、**BT 集計の正本は JSON**（型・エスケープが安全）。
- **B**: CSV を 1 ファイルに全エンティティ混在。→ 異種スキーマの混在で扱いにくい。

[Answer]: A — JSON = 単一 ExportBundle（U4b の正本）／CSV = エンティティ別（目視用途）。`Content-Disposition: attachment` でダウンロード。

### Q6【集計の実装位置】AdminService/ExportService の純粋性と Repository 集計
- **★A（推奨）**: 集計 SQL（進捗カウント・勝率・エクスポート join）は **Repository の読み取りメソッド**に集約（I/O 境界一貫・パラメータ化クエリ, XC-03）。AdminService/ExportService は Repository の結果を **ビュー/バンドル型へ整形する薄い層**（CSV 直列化・形式版付与）。純粋に保てる整形部分は関数化して単体テスト可能に。
- **B**: サービス層が直接 D1 を触る。→ I/O 境界の一貫性（LC-03）に反する。

[Answer]: A — 集計 SQL は Repository 読み取りメソッドに集約、Service は整形の薄い層（純粋部分は関数化して単体テスト可能に）。

### Q7【管理 UI 構成】frontend（C-FE-ADMIN）
- **★A（推奨）**: **単一 HTML + バニラ JS**（参加者 SPA と同方針・別ページ）。画面: 進捗サマリ + 暫定勝率テーブル + エクスポート（JSON/CSV ダウンロードリンク）。**デスクトップ主・日本語**（研究者利用。XC-04 波及だが厳密なモバイルファーストは非目標＝閲覧できれば可）。対話要素に `data-testid`。Worker が `/admin/` で配信（Q4=A）。
- **B**: 参加者 SPA に管理画面を相乗り。→ 認証境界・責務が混ざる。不採用。

[Answer]: A — 単一 HTML + バニラ JS（参加者 SPA と別ページ・Worker 配信）。デスクトップ主・日本語。**補足（意識的逸脱の記録）**: 「デスクトップ主・閲覧できれば可」は XC-04（モバイルファースト）からの逸脱だが、XC-04 の本旨は参加者向けであり研究者は PC 利用（P-RSCH）のため妥当。逸脱として明示記録。

---

**回答後の流れ**: 回答の曖昧さを点検（曖昧なら追加質問）→ Part 2 で 4 成果物（business-logic-model / business-rules BR-U3-xx / domain-entities / frontend-components）を生成 → 標準 2 択（Request Changes / Continue → **NFR Requirements〈U3〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す（監査証跡の自己完結）。
