# U4b Logical Components — BT 集計スクリプト（bt_aggregate）

**方針**: U4b は `schema/`（ExportBundle 入力・BTResult 出力）のみに依存する**オフライン pure-Python CLI**。統計ロジックを**6 純関数**に分け、CLI は薄い I/O 境界。専用インフラ部品（queue/cache/CB/lock）は導入しない（DP-U4b 非採用表）。Worker/D1 非依存・**新規 backend は `scripts/` 配下**（アプリ本体と分離）。層の逆流禁止（`scripts` → `schema` の一方向）。

---

## 論理コンポーネント一覧

### LC-U4b-01: aggregate（純・正準集計）
- **役割**: `aggregate(judgments) -> (wins, pair_counts)`。**正準集計の 3 点セット**（DP-U4b-01）: ペアキー `sorted((i,j))` 正規化で `n_ij` を数え、勝敗は item 単位（`w_i`）で向き非依存に集計。**正準化の通過必須点**。
- **α 適用位置の不変条件（明文固定）**: `aggregate` が返す `wins`/`pair_counts` は**生の観測カウント**であり、擬似データ α（`w̃_ij=w_ij+α/2, ñ_ij=n_ij+α`）は **`fit_bt` の内部でのみ**適用する。**`BTResult.matches`/`wins` は生カウント**（BR-U4b-08 の U3 突合＝winrate 定義一致の成立条件）。α を `aggregate` 側に混ぜると matches/wins に擬似分が乗り U3 の winrate 定義と食い違う。PU4b-6（U3 突合）が捕捉するが、MM 式の教訓（テストで検出されない仕様も明文で固定）に従い一行で固定する。
- **依存**: `schema`（ExportJudgment）。純粋。

### LC-U4b-02: connected_components（純）
- **役割**: `connected_components(pair_counts) -> list[component]`。観測ペアを辺とする無向グラフの連結成分（BFS/DFS）。最大成分の特定。
- **依存**: なし（集計データのみ）。純粋。

### LC-U4b-03: restrict_to_component（純・成分制限の切り出し）
- **役割**: `restrict_to_component(wins, pair_counts, component) -> (wins, pair_counts)`。推定対象（最大連結成分）へ集計を制限する**独立純関数**（DP-U4b-02）。→ PU4b-4 を純関数合成で検証可能に。
- **依存**: なし。純粋。

### LC-U4b-04: fit_bt（純・成分非依存 MM）
- **役割**: `fit_bt(wins, pair_counts, alpha, max_iter, tol) -> (theta, converged, iterations)`。**渡された連結な集計を推定するだけ**（成分非依存）。MM 擬似データ正則化（`w̃_ij=w_ij+α/2, ñ_ij=n_ij+α`, `π_i←w̃_i/Σ ñ_ij/(π_i+π_j)`）、θ=log π、**成分内 Σθ=0** 正規化、Σ 加算順固定（DP-U4b-01/04）。
- **依存**: なし。純粋。PBT: PU4b-1（単調性）/PU4b-2（決定論+置換不変性）/PU4b-3（Σθ=0）。

### LC-U4b-05: calibrate（純）
- **役割**: `calibrate(theta, likert, items) -> Calibration | None`。`target_ref=item_id` で Likert 平均を結合、アンカーの (平均 Likert, θ) を単回帰（閉形式）。スキップ条件（アンカー<2 / θ 分散 0 / slope≈0）で None（BR-U4b-05/06）。
- **依存**: `schema`（ExportLikert）。純粋。PBT: PU4b-5（係数復元）。

### LC-U4b-06: assemble_result（純）
- **役割**: `assemble_result(...) -> BTResult`。全 item（除外分は `bt_score=null`+`component` で可視化, BR-U4b-07）・matches/wins（U3 と同一, BR-U4b-08）・layer・rank・source エコーバック（BR-U4b-09）・warnings を組む。
- **依存**: `schema`（BTResult/BTItemScore/Calibration）。純粋。

### LC-U4b-07: bt_aggregate CLI（薄い I/O 境界）
- **役割**: 引数解析（argparse: パス・`--out`/`--alpha`/`--max-iter`/`--tol`/`--allow-version-mismatch`）・ファイル読込・**版検証**（`schema_version` vs `EXPORT_FORMAT_VERSION`, BR-U4b-11）・純関数群のオーケストレーション・**終了コード決定**（DP-U4b-03）・JSON+人間可読テーブル出力。`scripts/_bootstrap` で src 解決（U4a と同型）。
- **依存**: LC-U4b-01〜06、`schema`。副作用（I/O・終了コード）は本コンポーネントに集約。

### DataContract 追加（`src/schema/`, U4b 波及）
- **`src/schema/bt.py`（新規）**: `BTResult` / `BTItemScore` / `Calibration`。`BTResult.source={schema_version, exported_at}`。`schema/__init__` に公開。**DDL 変更なし**（D1 非依存）。入力 `ExportBundle`（U3）を消費。

---

## 依存方向（層の逆流禁止）

```
[ CLI: python -m scripts.bt_aggregate export.json ]
                │ (argparse・ファイルI/O・版検証・終了コード = LC-U4b-07)
                ▼
   ┌──────── 純関数合成（副作用なし） ────────┐
   │ LC-01 aggregate(正準集計 3点セット)        │
   │   → LC-02 connected_components             │
   │   → LC-03 restrict_to_component            │   ← PU4b-4 = 01→02→03→04 の純合成で検証
   │   → LC-04 fit_bt(成分非依存 MM)            │
   │   → LC-05 calibrate                        │
   │   → LC-06 assemble_result → BTResult       │
   └───────────────────┬───────────────────────┘
                       │ import（型のみ）
              ┌────────▼─────────┐
              │ schema/（bt.py 追加・ExportBundle 消費）│ ← DDL 変更なし
              └──────────────────┘
```

- **一方向依存**: CLI → 純関数群 → `schema`。**Worker/D1・上位ユニットへの依存なし**。全統計ロジックは純粋（副作用は CLI に集約）。
- **正準化は LC-U4b-01 に一点集約**（通過必須, DP-U4b-01）。**成分制限は LC-U4b-03 に切り出し**（PU4b-4 の純合成検証, DP-U4b-02）。

---

## 後続への申し送り（Infrastructure Design / Code Generation）
- **Infrastructure Design（U4b）**: **`scripts/` にファイル追加のみ**（Worker/D1/デプロイ/migration/シークレット無関係）＝差分ほぼゼロ。実行はローカル/CI、入力は U3 から curl 取得（Infra 申し送り）。
- **Code Generation**: `scripts/bt_aggregate`（LC-U4b-01〜07）、`src/schema/bt.py`、PBT（PU4b-1〜5・連結/非連結 + 左右反転ジェネレータ）+ unit（CLI・版検証・終了コード・U3 突合）。
  - **Step 記述に一行固定**（LC-U4b-01 の不変条件）: 「**aggregate=生カウント、α 適用は fit_bt 内部のみ、BTResult の matches/wins は生**」。U3 突合（BR-U4b-08/PU4b-6）の winrate 定義一致の成立条件。
