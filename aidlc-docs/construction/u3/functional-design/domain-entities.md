# U3 Domain Entities — 研究者・管理（admin）

**ユニット**: U3。参加者データ（U1/U2 の永続テーブル）を集計・出力する**ビュー/バンドル型**を定義する。型は `schema/`（`src/schema/`）に追加し、Worker（`src/backend/admin/`）が返す。**`ExportBundle` は U4b（BT 集計 US-R04）の入力契約の正本**。

---

## 1. 再利用する永続テーブル（読み取りのみ・U3 は書き込まない）

| テーブル | U3 での利用 |
|---|---|
| `tokens`（status） | 進捗カウント（発行/開始/完了） |
| `judgments`（token, pair_id, choice, created_at） | 勝率・エクスポート（本番のみ） |
| `pairs`（token, pair_id, idx, item_left, item_right, is_practice） | judgments と join（item ペア・pair_index・練習除外） |
| `items`（item_id, layer） | エクスポート items セクション（**body は出さない**）・勝率の layer |
| `likert_responses`（token, target_ref, rating, created_at） | エクスポート likert |
| `survey_responses`（token, answers, created_at） | エクスポート surveys |

- U3 は**読み取り専用**（新規テーブル・DDL 変更なし＝migration なし）。

---

## 2. ビュー型（schema/ 追加・管理 API レスポンス契約）

### ProgressView（`GET /admin/progress`）
| フィールド | 型 | 意味 |
|---|---|---|
| `tokens_issued` | int | 発行済みトークン総数 |
| `tokens_started` | int | status ∈ {in_progress, completed} |
| `tokens_completed` | int | status = completed |
| `judgments_total` | int | **本番判定のみ**の総数（練習除外） |
| `likert_total` | int | Likert 回答総数 |
| `survey_total` | int | アンケート回答総数 |

### WinrateRow（`GET /admin/winrates` → `list[WinrateRow]`）
| フィールド | 型 | 意味 |
|---|---|---|
| `item_id` | str | 作品 |
| `layer` | str | 層（pro/ai/edit/rule） |
| `matches` | int | 本番比較での出現数 |
| `wins` | int | 選ばれた回数 |
| `winrate` | float | `wins/matches`（matches=0 は 0） |

- **非 BT の簡易表示**（UI に明示, BR-U3-05）。

---

## 3. ExportBundle 正本（US-R04/U4b 入力契約, BR-U3-07）

```
ExportBundle = {
  schema_version: str,     # = EXPORT_FORMAT_VERSION（"1.0.0"）
  exported_at:    str,     # ISO 8601（このスナップショットの時点）
  items:     list[ExportItem],
  judgments: list[ExportJudgment],   # 本番のみ（練習は出力段で除外）
  likert:    list[ExportLikert],
  surveys:   list[ExportSurvey],
}
```

| 型 | フィールド | 備考 |
|---|---|---|
| **ExportItem** | `item_id, layer` | **body は含めない**（未公表刺激, NFR-08）。U4b の層解決を自己完結させる |
| **ExportJudgment** | `token, pair_id, pair_index, item_left, item_right, choice, created_at` | `pair_index`=`pairs.idx`（順序効果分析）。`choice=A`→item_left 勝ち。**本番のみ** |
| **ExportLikert** | `token, target_ref, rating, created_at` | 較正アンカー |
| **ExportSurvey** | `token, answers, created_at` | `answers` は暫定 dict（U2 と同） |

**契約の性質**:
- **自己完結**: judgments に現れる全 `item_id` は `items` に存在（U4b は投入 JSON を第二入力にしない＝「変換なしで読み込める」US-R02）。
- **位置バイアス分析可能**: `item_left/item_right + choice`（winner/loser へは U4b が導出）。
- **順序効果分析可能**: `pair_index`。
- **評価者相対性分析可能**: 全レコードに `token`。
- **版管理**: 形式変更は `EXPORT_FORMAT_VERSION` の版上げ + 影響（U4b）明記（BR-U3-07）。

### CSV 形（`format=csv&entity=<...>`）
- エンティティ別（items / judgments / likert / surveys）に 1 リクエスト 1 CSV。ヘッダ行 + データ行。目視用途（BR-U3-06）。BT 集計の正本は JSON。

---

## 4. 関係図（データフロー・読み取り専用）
```
[ブラウザ 管理UI] --HTTPS + Basic--> GET /admin/{ , progress, winrates, export}
                                         │ (AuthGuard 再利用 = DP-U4a-01)
                                         ▼
           [ Worker src/backend/admin/ (handle_admin 拡張) ]
             ├─ AdminService   → ProgressView / list[WinrateRow]
             └─ ExportService  → ExportBundle(JSON 正本) / CSV(entity 別)
                                         │ Repository 集計読み取り（本番のみ・パラメータ化）
                                         ▼
      [ D1: tokens / judgments × pairs / items / likert_responses / survey_responses ]（読み取り専用）
                                         │
   [U4b bt_aggregate] ← ExportBundle(JSON) を変換なしで入力（schema_version で整合確認）
```

---

## 5. U4b への申し送り
- **本 `ExportBundle` が BT 集計の入力仕様の正本**。`schema_version` を検証してから読む。
- items（層）・pair_index（順序）・item_left/right+choice（位置）・token（評価者）で、BT 推定 + 層ラベル付け + 各種統制分析が bundle 単体で完結する。
