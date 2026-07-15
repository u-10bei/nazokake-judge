# U3 Code Generation Summary — 研究者・管理（admin）

**生成日**: 2026-07-15。plan（`construction/plans/u3-code-generation-plan.md`, 全 4 決定点★A）を単一の真実として全 10 ステップを生成。**読み取り専用**（migration/wrangler.toml/deploy.yml **変更なし**）。

---

## 生成・変更ファイル

### schema/（ビュー/バンドル型）
- **新規** `src/schema/admin_views.py`: `ProgressView` / `WinrateRow` / **`ExportBundle`**（U4b 入力契約の正本 BR-U3-07）/ `ExportItem`（**body なし**）/ `ExportJudgment`（pair_index 込み）/ `ExportLikert` / `ExportSurvey`。
- **変更** `src/schema/__init__.py`: 上記を公開。

### backend/（admin 拡張・読み取り専用）
- **変更** `src/backend/repo/repository.py`: `read_progress()` / `read_winrates()`（judgments×pairs UNION 展開・is_practice=0）/ `read_export_rows(entity)`（本番のみ・pair_index=`idx`）。**全パラメータ化・練習除外は SQL の WHERE 句**。
- **新規** `src/backend/admin/format.py`: 純粋整形。`to_csv`（**標準 csv モジュール・RFC4180**）/ `build_progress` / `build_winrates`（winrate=wins/matches, matches=0→0）/ `build_export_bundle`。
- **新規** `src/backend/admin/service.py`: `get_progress` / `get_winrates` / `export(format, entity, exported_at)`（JSON=bundle / CSV=entity 別・`ExportRequestError`）。
- **新規** `src/backend/admin/ui.py`: 管理ダッシュボード HTML/JS/CSS のモジュール定数（**assets 非配置** BR-U3-02・data-testid・非BT 注記・デスクトップ主）。
- **変更** `src/backend/admin/api.py`: `handle_admin` に **GET 配線**（`/admin/`〈UI〉・`/admin/progress`・`/admin/winrates`・`/admin/export`）。既存 AuthGuard 背後・**no-store 共通ヘルパ**・エクスポートは `Content-Disposition: attachment`（filename の ts=exported_at）。`admin_log` 秘匿。

### テスト
- **新規 unit** `tests/unit/u3/test_format.py`（CSV エスケープ境界・winrate 定義・ExportBundle 構造/自己完結）。
- **新規 PBT** `tests/pbt/test_export_selfcontained.py`（PU3-3: judgments の item ⊆ items）。
- **新規 integration** `tests/integration/drive_u3.py`（`/admin/*` 越し PU3-1/2/4/5 + CSV/UI/401）。

---

## API 一覧（管理系・すべて Basic 認証背後・no-store）
| メソッド パス | 用途 | レスポンス |
|---|---|---|
| `GET /admin/` | 管理 UI（HTML） | text/html |
| `GET /admin/progress` | 進捗 | ProgressView |
| `GET /admin/winrates` | 暫定勝率（非BT） | list[WinrateRow] |
| `GET /admin/export?format=json` | エクスポート正本（U4b 入力） | ExportBundle（attachment） |
| `GET /admin/export?format=csv&entity=<items\|judgments\|likert\|surveys>` | CSV（目視） | text/csv（attachment） |

エクスポートの CLI 取得（U4b 自動化の正）: `curl -u $ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD -o export.json "https://<host>/admin/export?format=json"`。

---

## テスト実行実績
- **unit + PBT: 39 passed**（ci プロファイル 200 examples）。U1/U2/U4a 回帰緑 + U3 追加（format 5 + PU3-3）。
- **integration（実 D1/miniflare）: 全 8 項目 PASS**（`result-u3-integration.json`）:
  PU3-5 認証 401（progress/winrates/export/ui）/ PU3-4 進捗整合（issued≥started≥completed=1・judgments_total=40 本番のみ）/ **PU3-1 練習除外の出力段保証（export=40==progress=40）** / **PU3-3 自己完結・body なし（items=95）** / **PU3-2 winrate 定義整合（総試合=80=40×2）** / CSV judgments（41 行）/ CSV entity 未指定 400 / UI HTML 200。
- **変更なしの確認**: `migrations/`・`wrangler.toml`・`deploy.yml`・`frontend/`（参加者 assets）に変更なし。

## Build & Test の軽微修正（2026-07-15・非ブロッキング観察 2 点）
1. **filename のコロン除去**: `_now_iso()` は `2026-07-15T05:37:40Z` 形式でコロンを含み、Windows で DL 時に自動置換され「filename の ts = exported_at」の監査整合が崩れる。→ **filename 側だけ `exported_at.replace(":", "")`**（`service.export`）。**bundle 内の `exported_at` は ISO8601 のまま維持**。実機で `Content-Disposition: filename="export-bundle-2026-07-15T053740Z.json"`（コロンなし）を確認。U4b の正経路は `curl -o export.json` ゆえ実害なし。
2. **暫定勝率の未出場行**: `read_winrates` は `items LEFT JOIN` で全 items を返すため、本番未出場（練習専用含む）の item が `matches=0 / winrate=0.0` で並ぶ。**露出監視に有用ゆえ設計整合として維持**。UI 注記に「対戦数 0 は未出場」を明示（誤読防止）。U4b の BT 集計は judgments 起点ゆえ影響なし。

## 決定点の実装対応
| 決定点 | 実装 |
|---|---|
| Q1 judgments×pairs 単一クエリ・is_practice=0・UNION 展開 | `read_winrates`/`read_export_rows`（SQL） |
| Q2 admin_views.py 分離 | `src/schema/admin_views.py` |
| Q3 標準 csv・no-store+attachment・filename ts=exported_at | `format.to_csv`/`api._download`/`service.export` |
| Q4 回帰全緑ブロッキング | unit+PBT 39 緑で確認済み |
