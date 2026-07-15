# U3 NFR Design Patterns — 研究者・管理（admin）

U3-NFR-01〜11 を設計パターン **DP-U3-NN** に落とす。U1（DP-01〜08）・U4a（DP-U4a-01〜07）・U2（DP-U2-01〜07）を前提に、U3 固有分のみ。**既存 DP の再利用が大半**。案 A′（raw workers API, F-5, src/ レイアウト F-8）。

---

## DP-U3-01: 認証ルートの相乗り（チョークポイント再利用）
- 既存 `handle_admin` 入口の **AuthGuard（`check_basic`, DP-U4a-01）をそのまま通し**、U3 の GET ルート（`/admin/`・`/admin/progress`・`/admin/winrates`・`/admin/export`）を**同じディスパッチに追加**。GET/POST とも単一の認証点を必ず通る（`/admin/*` 全体が Basic 認証背後）。**認証漏れの GET を構造的に作れない**。新規認証・新規資格なし。
- 対応: U3-NFR-01/04, BR-U3-01, Q1。

## DP-U3-02: エクスポート秘匿の強制点（3 点を構造で守る）
- **(a) no-store＝共通レスポンスヘルパ**: 管理 API/エクスポート応答を**共通ヘルパ経由**で生成し `Cache-Control: no-store` を必ず付与。ダウンロードは `Content-Disposition: attachment` も同ヘルパで（付け忘れ防止, U2 DP-U2-04 と同型）。
- **(b) body 非含有＝型で排除**: エクスポート型に **`body` フィールドを持たせない**（`ExportItem = {item_id, layer}`）。domain→export 型の写像を **1 箇所に集約**し `body` を構造的に落とす（U2 DP-U2-02 と同型＝本文/出自を型システムで守る）。**未公表刺激をエクスポート経路に出せない**。
- **(c) トークン非ログ＝AdminLog 再利用**: 管理操作ログは U4a AdminLog（許可フィールド限定）を通し、トークン生値・本文を排除。**エクスポート応答本体は実トークンを含む**（評価者相対性のため・認証背後の正当な受領）。
- 対応: U3-NFR-02/03/08, BR-U3-02/08, Q2。

## DP-U3-03: 集計の Repository 集約 + 練習除外の出力段保証
- 集計 SQL は **Repository の読み取りメソッドに集約**（エンドポイント 1 本 = クエリ 1 本: `read_progress()` / `read_winrates()` / `read_export_rows(entity)`）。**すべてパラメータ化クエリ**（SQLi 対策）。
- **練習除外（`pairs.is_practice=0`）を SQL の WHERE 句に埋め込む**（出力段保証＝Python 側フィルタを持たない, BR-U3-03）。下流（U4b）にフィルタ責務を残さない。
- 対応: U3-NFR-05/07, BR-U3-03/09, Q3。

## DP-U3-04: 純粋整形（CSV / ビュー / バンドル組立）
- **整形は副作用なしの純関数**: `rows → csv_text`（**カンマ・引用符・改行のエスケープ**）、`ProgressView`/`WinrateRow[]`/`ExportBundle` の組立。`src/backend/admin/` に配置し **example ベース単体テスト**。
- **ExportBundle 自己完結**（judgments に現れる item_id ⊆ items）は **PU3-3 で PBT**（生成データで包含関係を反例探索）。
- AdminService/ExportService は「Repository → 純関数整形 → レスポンスヘルパ」の薄いオーケストレーション。
- 対応: U3-NFR-09/10, BR-U3-05/07, Q4。

## DP-U3-05: 統一エラー封筒
- **U4a=DP-U4a-07 と同水準**。認証失敗のみ **401 + `WWW-Authenticate`**。業務エラー（未知の `entity`/`format`）は `{ok:false, error}`。正常時は各ビュー/バンドル（JSON）またはファイル（CSV/JSON attachment）。小規模ゆえ**ストリーミング不要**（一括レスポンス）。
- 対応: U3-NFR-01, Q4。

---

## 管理 UI 配信パターン（DP-U3-02 の付随）
- **管理 HTML/JS/CSS は `src/backend/admin/ui.py` のモジュール定数（一体の文字列）**として保持し、`handle_admin` が `GET /admin/` で `text/html` を返す（**Static Assets に置かない** BR-U3-02）。**ビルドステップは導入しない**（UI は 1 ファイル・数百行、文字列 import の F-4 影響は実質ゼロ）。

## 導入しない設計部品（意図的な非採用・U1/U2/U4a と同方針）
| 部品 | 非採用理由 |
|---|---|
| キャッシュ | 集計は小規模で瞬時（U3-NFR-06）。 |
| キュー | 同期・小規模。 |
| サーキットブレーカ / リトライ基盤 | 外部依存の連鎖なし。 |
| 分散ロック | **読み取り専用**（書き込み競合なし）。 |
| ページング / ストリーミング | 判定 ≈ 2,000 行 + items 95。一括で十分。 |
