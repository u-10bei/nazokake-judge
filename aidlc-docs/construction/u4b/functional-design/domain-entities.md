# U4b Domain Entities — BT 集計スクリプト（bt_aggregate）

**ユニット**: U4b。入力は U3 の `ExportBundle`（正本・再定義しない）。U4b が定義するのは**出力の `BTResult`**（+ 構成要素）。型は `schema/`（`src/schema/`）に追加し、`scripts/bt_aggregate` が生成する。UI なし（CLI）。

---

## 1. 入力（U3 が固定・消費するのみ）

`ExportBundle`（BR-U3-07, `src/schema/admin_views.py`）:
- `schema_version` / `exported_at` / `items[{item_id, layer}]` / `judgments[{token, pair_id, pair_index, item_left, item_right, choice, created_at}]`（本番のみ） / `likert[{token, target_ref, rating, created_at}]` / `surveys[...]`。
- U4b は judgments（比較）・items（層）・likert（較正, `target_ref=item_id`）を使う。surveys は本ユニットでは未使用（将来の統制分析用）。

---

## 2. 出力：BTResult（U4b が定義・正本）

```
BTResult = {
  source:        { schema_version, exported_at },   # 入力スナップショットのエコーバック（BR-U4b-09）
  n_items:       int,
  n_comparisons: int,                               # 本番判定数
  n_components:  int,                               # 比較グラフの連結成分数
  estimated_component_size: int,                    # 推定対象（最大連結成分）の item 数
  converged:     bool,
  iterations:    int,
  alpha:         float,                             # 正則化（観測ペア限定, BR-U4b-03）
  items:         list[BTItemScore],                 # 全 item（除外分も残す, BR-U4b-07）
  calibration:   Calibration | null,                # 較正（スキップ時 null, BR-U4b-06）
  warnings:      list[str],
}
```

| 型 | フィールド | 備考 |
|---|---|---|
| **BTItemScore** | `item_id, layer, bt_score(θ) \| null, calibrated_score \| null, component, rank \| null, matches, wins` | 除外 item は `bt_score=null`・`component` で可視化（BR-U4b-07）。`matches/wins` は U3 と同一定義（BR-U4b-08）。`rank` は推定対象内の順位 |
| **Calibration** | `n_anchors, slope, intercept, anchor_item_ids` | (平均 Likert, θ) の単回帰（BR-U4b-05）。スキップ時は BTResult.calibration=null |

- `bt_score(θ)` は BT 尺度上の位置（`log π`）、**最大連結成分内で Σθ=0**（BR-U4b-04）。
- `calibrated_score` は Likert 相当尺度への写像 `(θ−a)/b`（アンカーありのとき）。

---

## 3. 出力チャネル
- **JSON**（`--out` or stdout）: `BTResult`（機械可読・監査）。
- **人間可読テーブル**（stdout）: 層別・スコア降順（`item_id / layer / θ / calibrated / rank / matches / wins`）。新作は layer で判別、プロ水準（layer=pro の分布）との相対位置を層別サマリで表示。

---

## 4. 関係図（データフロー・判定装置の一巡クローズ）
```
[U3 GET /admin/export?format=json]  ──curl -o export.json──►  export.json（ExportBundle）
                                                                    │
                                                                    ▼
                        [ scripts/bt_aggregate (pure-Python, offline) ]
                          版検証 → 比較集計 → 連結成分 → MM 推定(観測ペア正則化) →
                          Σθ=0 正規化(最大成分) → Likert 較正(target_ref=item_id) → BTResult 組立
                                                                    │
                                                    ┌───────────────┴───────────────┐
                                                    ▼                               ▼
                                            BTResult(JSON, --out)           人間可読テーブル(stdout)
                                            └─ source.exported_at で       └─ 層別・新作の相対位置
                                               スナップショット識別

判定装置の一巡: 投入(U4a)→発行(U4a)→参加(U2)→進捗/エクスポート(U3)→**BT 集計(U4b)**→新作の位置確認 ✅
```

---

## 5. schema/ への追加
- **`src/schema/bt.py`（新規）**: `BTResult` / `BTItemScore` / `Calibration`（Pydantic v2）。`schema/__init__` に公開。
- **DDL 変更なし**（U4b は D1 非依存・ファイル入出力のみ）。
