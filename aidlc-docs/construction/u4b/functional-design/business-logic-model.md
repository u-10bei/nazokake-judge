# U4b Business Logic Model — BT 集計スクリプト（bt_aggregate）

**ユニット**: U4b（最終ユニット）。`scripts/bt_aggregate`（**オフライン pure-Python CLI・Worker 非依存**）が U3 の **ExportBundle（JSON 正本）を入力**に、Bradley–Terry 尺度上の品質スコアを推定し、Likert で較正し、新作のプロ水準に対する相対位置を出力する。これで**判定装置の一巡**が閉じる。

**設計原理**: 統計推定が本体＝**純関数中心**（副作用は CLI の I/O のみ）。BT=MM 反復、較正=単回帰、いずれも**標準ライブラリのみ**（追加依存なし）。研究コードとして**再現性・監査可能性が最優先**。

---

## 1. 構成要素（責務境界）

| 要素 | 配置 | 役割 |
|---|---|---|
| `bt_aggregate` CLI | `scripts/` | エクスポート JSON 読込 → 版検証 → BT 推定 → 較正 → BTResult 出力 |
| BT 推定（純） | `scripts/`（純関数） | 比較集計・連結成分・MM 反復・正則化・正規化 |
| Likert 較正（純） | `scripts/`（純関数） | アンカー抽出・単回帰・較正スコア |
| BTResult 組立（純） | `scripts/`（純関数） | JSON + 人間可読テーブル |

- **依存**: `schema/`（`ExportBundle` 型・`EXPORT_FORMAT_VERSION`）のみ import。Worker・D1 に非依存。層の逆流禁止。

---

## 2. bt_aggregate フロー（US-R04）

```
1. CLI: エクスポート JSON ファイルパスを引数で受ける（--out で出力先, --allow-version-mismatch）
2. 読込・版検証: bundle.schema_version と EXPORT_FORMAT_VERSION を比較
     不一致 → 既定エラーで終了（BR-U4b-07）。--allow-version-mismatch 時のみ warnings 記録で続行
3. 比較集計: judgments（本番のみ・U3 保証）から
     各 (winner, loser) を集計。choice=A→item_left 勝ち / B→item_right 勝ち（BR-U3-05 と同一）
     w[i] = item i の勝ち数、n[i][j] = i,j 間の対戦数（観測ペアのみ）
4. 連結成分検出: 観測ペアを辺とする無向グラフの連結成分を求める（BR-U4b-02）
     非連結 → warnings に記録。**最大連結成分のみを推定対象**とする
5. MM 推定（最大成分内）: Hunter 2004 の反復（BR-U4b-01）
     π_i を初期 1 → π'_i = (w_i + α) / Σ_j n_ij/(π_i+π_j)  を収束まで反復（正則化 α）
     **スムージングは観測ペアのみに適用**（全ペアには張らない, BR-U4b-03）
     θ_i = log π_i。**最大連結成分内で Σθ=0 に正規化**（BR-U4b-04）
6. Likert 較正: likert を target_ref(=item_id, BR-U4b-05) で各 item の平均 rating に集計
     アンカー = (推定対象 item かつ Likert 平均あり)。target_ref ∉ items は除外+警告
     アンカー ≥ 2 かつ θ 分散 > 0 なら (平均Likert, θ) を単回帰: θ = a + b·L → 逆写像で
       calibrated_i = (θ_i − a)/b （解釈可能 = Likert 相当尺度）。満たさねば較正スキップ+警告
7. BTResult 組立: items 全件（除外分は bt_score=null + component）、source エコーバック、
     matches/wins（U3 と同一定義）、layer、rank、calibration、warnings、収束情報
8. 出力: JSON（--out or stdout）+ 人間可読テーブル（層別・スコア降順）
```

- **判定装置の一巡クローズ**: 投入(U4a)→発行(U4a)→参加(U2)→進捗/エクスポート(U3)→**BT 集計(U4b)**→新作の位置確認。

## 3. MM アルゴリズム（BR-U4b-01, Hunter 2004）

- BT モデル: P(i beats j) = π_i / (π_i + π_j)。対数尤度を MM で単調増加させる標準反復。
- 更新式（正則化付き）: `π_i ← (w_i + α) / Σ_{j≠i} n_ij / (π_i + π_j)`（分母は観測ペアのみ和）。
- 収束: θ の最大変化 < 閾値、または最大反復到達。**決定論**（初期値・反復固定 → 同一入力同一出力, P-6）。
- 正則化 α（既定小さな値）で完全勝ち/完全負けの item も有限スコアに収まる。

## 4. Likert 較正（BR-U4b-05）

- `target_ref = item_id`（U2 確認）で likert を item に結合し平均 rating を得る。
- アンカー集合 = {推定対象 item ∩ Likert 平均あり ∩ target_ref ∈ items}。
- 単回帰（閉形式）: slope b, intercept a を最小二乗。`calibrated = (θ − a)/b`。
- スキップ条件（生 θ のみ + 警告）: アンカー < 2 / θ 分散 = 0 / b ≈ 0。

## 5. Testable Properties（U4b Code Generation / Build & Test で検証）

| ID | プロパティ | 対応 |
|---|---|---|
| **PU4b-1（単調性）** | item A が B に常に勝つデータ → `θ_A > θ_B`（正則化 ON でも保存, PBT-03） | BR-U4b-01/03 |
| **PU4b-2（決定論・収束）** | 同一入力 → 同一 BTResult（初期値・反復固定） | P-6 |
| **PU4b-3（正規化）** | **最大連結成分内で Σθ = 0**（Q2 と整合） | BR-U4b-04 |
| **PU4b-4（識別可能性）** | 非連結グラフ → warnings + 最大成分のみ推定・除外 item は bt_score=null+component | BR-U4b-02 |
| **PU4b-5（較正整合）** | 既知の線形 (Likert, θ) データで単回帰係数を復元（example + PBT） | BR-U4b-05 |
| **PU4b-6（U3 突合）** | matches/wins が U3 winrate 定義と一致（同一エクスポートで U3 と同値） | BR-U4b-06 |
| **PU4b-7（版検証）** | schema_version 不一致 → 既定エラー終了 / --allow-version-mismatch で warnings 続行 | BR-U4b-07 |

- 純関数中心ゆえ PBT（Hypothesis）適用が自然（U4b は PBT-03 が主）。CLI 入出力・版検証・出力形式は example。

## 6. 判定装置の一巡・後続
- 本ユニット完成で **5 ユニット（U1/U2/U3/U4a/U4b）が揃い、判定装置の一巡が閉じる**。
- 運用: U3 から `curl` でエクスポート取得（Infra 申し送り）→ `bt_aggregate export.json` → 新作の層別相対位置を確認。反復判定は複数スナップショットを回し、`source.exported_at` で識別。
