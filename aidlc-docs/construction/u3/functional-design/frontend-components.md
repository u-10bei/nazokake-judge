# U3 Frontend Components — 研究者・管理 UI（C-FE-ADMIN）

**ユニット**: U3 管理 UI。**単一 HTML + バニラ JS**（参加者 SPA と同方針・別ページ）。**Worker が Basic 認証背後で配信**（`GET /admin/`。Static Assets には置かない, BR-U3-02）。**デスクトップ主・日本語**（研究者 P-RSCH は PC 利用。XC-04 からの意識的逸脱 BR-U3-10）。

---

## 1. コンポーネント階層（単一画面・セクション構成）

```
AdminApp（Worker が /admin/ で返す HTML シェル）
├─ ProgressPanel     … 進捗サマリ（発行/開始/完了・本番判定/likert/survey）
├─ WinratePanel      … 暫定勝率テーブル（item_id / layer / matches / wins / winrate）
│                       └─ 非BT 注記（「簡易表示・正式 BT ではない」明示）
└─ ExportPanel       … エクスポート（JSON ダウンロード / CSV エンティティ別）
```

- 研究者向けの単一ダッシュボード。ページ全体が Basic 認証背後（初回に 1 度ダイアログ）。

---

## 2. 状態管理

| 状態 | 置き場所 | 備考 |
|---|---|---|
| progress | メモリ（起動時 fetch） | `GET /admin/progress` |
| winrates | メモリ（起動時 fetch） | `GET /admin/winrates` |
| （認証） | ブラウザの Basic 資格 | `/admin/*` で一度ダイアログ、以降のフェッチも同資格 |

- クライアント状態は最小（表示データのみ・保存しない）。手動リロード or 「更新」ボタンで再取得。

---

## 3. ユーザー操作フロー（US-R01/R02/R03）

```
起動: GET /admin/ （Basic 認証ダイアログ）→ HTML 表示
  → 並行して GET /admin/progress・GET /admin/winrates を fetch し描画
ProgressPanel: 6 指標を表示（更新ボタンで再取得）
WinratePanel:  勝率テーブル（layer・winrate でソート可）＋ 非BT 注記
ExportPanel:
  「JSON をダウンロード」→ GET /admin/export?format=json（attachment）
  「CSV: judgments / likert / surveys / items」→ GET /admin/export?format=csv&entity=<...>
```

---

## 4. API 結合点

| 画面 / 操作 | エンドポイント | 受け取り |
|---|---|---|
| 起動（シェル） | `GET /admin/` | HTML（Worker 配信） |
| 進捗 | `GET /admin/progress` | ProgressView |
| 暫定勝率 | `GET /admin/winrates` | list[WinrateRow] |
| エクスポート JSON | `GET /admin/export?format=json` | ExportBundle（attachment） |
| エクスポート CSV | `GET /admin/export?format=csv&entity=<items\|judgments\|likert\|surveys>` | CSV（attachment） |

- すべて Basic 認証背後（BR-U3-01）。ダウンロードは `Content-Disposition: attachment`。

---

## 5. 表示・UI 方針

| 要件 | 実装方針 |
|---|---|
| 非 BT 明示 | WinratePanel に常時注記（US-R03 / BR-U3-05） |
| 日本語 | 全 UI 文言・注記を日本語 |
| デスクトップ主 | テーブル中心のレイアウト（横幅活用）。モバイルは破綻しない程度（厳密なモバイル最適化は非目標, BR-U3-10） |
| 自動化属性 | 対話要素に `data-testid`（例 `admin-refresh-button`・`admin-export-json-button`・`admin-export-csv-judgments-button`・`winrate-table`） |

---

## 6. 実装メモ（Code Generation への申し送り）
- 管理 HTML/JS は **`src/backend/admin/` 配下の埋め込み文字列（モジュール）**として保持（assets 非配置, BR-U3-02）。`handle_admin` が `GET /admin/` で `text/html` を返す。
- トップレベル import は最小限（F-4）。HTML は小さく、埋め込みでも起動 CPU 影響は無視できる。
- 出力データにトークンが含まれる（評価者相対性）が、これは Basic 認証背後の研究者向け＝秘匿ログ（BR-U3-08）とは別（レスポンス本体は返す、ログには出さない）。
