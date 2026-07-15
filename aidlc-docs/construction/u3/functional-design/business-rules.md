# U3 Business Rules — 研究者・管理（admin）

U1（BR-01〜12）・U4a（BR-U4a-01〜12）・U2（BR-U2-01〜30）を前提に、U3 固有の規則を **BR-U3-NN** で番号付けする。集計・出力は**本番のみ**（練習除外）で一貫させる。

---

## 認証・境界

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U3-01（認証一本化）** | 管理 UI（`GET /admin/`）・管理 API（`/admin/progress`・`/admin/winrates`・`/admin/export`）は**すべて既存 Basic 認証チョークポイント（`/admin/*`, DP-U4a-01）の背後**。認証なし/誤りは 401 + `WWW-Authenticate: Basic`。「一般の評価者トークンでは開けない」（US-R01）を構造的に担保。 | US-R01 / DP-U4a-01 / XC-03 |
| **BR-U3-02（管理 HTML の assets 非配置・必須）** | **管理 HTML を `frontend/`（Static Assets）に置いてはならない**。assets は公開配信のため、置いた瞬間に認証境界の外へ漏れる（UI シェル公開）。Workers は実行時にファイルを読めないため、**管理 HTML/JS は `src/backend/admin/` 配下の埋め込み文字列（モジュール）として保持し、Worker が Basic 認証背後で返す**。小 HTML ゆえ F-4（起動 CPU 制限）への影響は無視できる。 | Q4 補足 |

## 集計の意味論（練習除外・本番のみ）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U3-03（練習除外の出力段保証）** | エクスポート・進捗・勝率の**すべての集計は本番判定のみ**（`pairs.is_practice=0`）。**練習の除外を出力段（SQL）で保証**し、下流（U4b）にフィルタ責務を残さない。エクスポートの judgments に練習由来の行が混入してはならない。 | US-P02 / Q1 |
| **BR-U3-04（進捗の内訳）** | `ProgressView = { tokens_issued, tokens_started, tokens_completed, judgments_total（本番のみ）, likert_total, survey_total }`。`tokens_issued ≥ tokens_started ≥ tokens_completed`。開始 = status ∈ {in_progress, completed}、完了 = status=completed。 | US-R01 / Q2 |
| **BR-U3-05（暫定勝率・非 BT 明示）** | `WinrateRow = { item_id, layer, matches, wins, winrate }`。matches = item が現れた本番比較数、wins = 選ばれた回数（`choice=A`→item_left 勝ち / `B`→item_right 勝ち）、`winrate = wins/matches`（matches=0 は 0）。**「簡易表示であり正式 BT 推定ではない」旨を UI に明示**。軽量単一集計に留める。 | US-R03 / Q3 |

## エクスポート契約（U4b 入力の固定）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U3-06（配信形式）** | `format=json`（既定）= 単一 `ExportBundle`（**U4b の正本**）。`format=csv&entity=<items\|judgments\|likert\|surveys>` = 当該エンティティのみ CSV（目視用途）。いずれも `Content-Disposition: attachment`。 | US-R02 / Q5 |
| **BR-U3-07（ExportBundle 契約・自己完結・版管理）** | `ExportBundle = { schema_version, exported_at, items, judgments, likert, surveys }`（domain-entities 正本）。**judgments に現れる item_id は必ず items に存在**（U4b が層を自己完結取得＝投入 JSON を第二入力にしない）。`schema_version = EXPORT_FORMAT_VERSION`。**形式変更は `EXPORT_FORMAT_VERSION` の版上げを伴い、影響ユニット（U4b）を明記**する。**body は含めない**（未公表刺激, NFR-08）。トークン単位で紐付く（評価者相対性, US-R02）。 | US-R02 / US-R04 / Q1 |
| **BR-U3-08（トークン秘匿ログ）** | 管理操作ログ（AdminLog 再利用）に**トークン生値・本文を出力しない**。エクスポート内容自体（トークン含む）は Basic 認証背後で研究者にのみ返す。 | XC-03 / U4a-NFR-03 |

## 実装位置・UI

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U3-09（集計の Repository 集約）** | 集計 SQL（進捗カウント・勝率・エクスポート join）は **Repository 読み取りメソッド**に集約（I/O 境界一貫・パラメータ化クエリ, XC-03）。AdminService/ExportService は結果をビュー/バンドル型へ整形する**薄い層**（純粋部分は関数化し単体テスト可能に）。 | LC-03 / Q6 |
| **BR-U3-10（管理 UI・XC-04 からの意識的逸脱）** | 管理 UI は**デスクトップ主・日本語**（研究者 P-RSCH は PC 利用）。XC-04（モバイルファースト）の本旨は参加者向けであり、管理 UI は「閲覧・操作できれば可」に留める＝**XC-04 からの意識的逸脱として明示記録**。対話要素に `data-testid`。 | XC-04 / Q7 |

---

## 検証・エラー処理サマリ

| 状況 | 挙動 |
|---|---|
| Basic 認証なし/誤り | 401 + `WWW-Authenticate`（UI・全 API, BR-U3-01） |
| 練習判定の混入 | 集計・出力から SQL で除外（BR-U3-03） |
| matches=0 の item | winrate=0（BR-U3-05） |
| 未知の `entity`/`format` | 400 相当（既定 json / 不正は簡素なエラー） |
| エクスポートの item 欠落 | 起きない（items は全 items 行を出力、judgments の item は必ず含む, BR-U3-07） |
