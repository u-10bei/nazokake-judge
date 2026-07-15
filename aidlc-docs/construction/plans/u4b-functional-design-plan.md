# U4b Functional Design Plan — BT 集計スクリプト（bt_aggregate）

**ユニット**: U4b（`C-SCRIPT-BT`）。**最終ユニット**。
**目的**: US-R04（オフライン BT 集計）の業務ロジックを設計する。U3 が固定した **ExportBundle（JSON 正本, BR-U3-07）を入力**に、全作品の **Bradley–Terry 尺度上の推定位置（品質スコア）** を算出し、新作のプロ水準に対する相対位置を確認可能にする。ブリッジ Likert を較正アンカーとして解釈に利用する。
**前提（既決）**: `scripts/` 配下・**オフライン pure-Python**（Worker 非依存＝F-4 の起動 CPU 制限・D1 接続の対象外。ローカル/CI で実行）。入力は U3 エクスポート（`schema_version` で整合確認）。**判定装置の一巡**（投入→発行→参加→エクスポート→BT 集計→新作の位置確認）を閉じる。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `business-logic-model.md` / `business-rules.md` / `domain-entities.md` を生成します（**UI なし** = CLI・scripts のため frontend-components は N/A）。

---

## 中核論点（このユニットの肝）

U4b は**統計推定**が本体。BT 推定の正しさが「新作の位置確認」という装置の目的に直結する。肝は 3 点:

1. **BT 推定手法と依存**（最重要）。ペア比較（winner/loser）から各作品の BT 強度パラメータを最尤推定する。手法は **MM（minorization–maximization）純 Python**（依存ゼロ・BT の定番反復法）か scipy 最適化か。offline scripts ゆえ numpy/scipy を足せるが、依存最小の価値もある。→ **Q1**。
2. **識別可能性（比較グラフの連結性）**。BT は比較グラフが連結でないとコンポーネント間のスコアが比較不能・尺度が非同定。疎データ（新作は対戦数が少ない）での安定化（正則化/事前分布）も要る。→ **Q2**。
3. **Likert 較正アンカーの使い方**。BT 尺度は位置・スケール任意（相対値）。ブリッジ Likert（一部作品の絶対評定）を**アンカー**に、BT スコアを解釈可能な尺度へ写像する。→ **Q3**。

**U4b が入力として前提するもの**（U3 が固定済み・再設計しない）:
- `ExportBundle = {schema_version, exported_at, items[{item_id,layer}], judgments[{token,pair_id,pair_index,item_left,item_right,choice,created_at}], likert[{token,target_ref,rating,created_at}], surveys[...]}`。
- **判定は本番のみ**（練習は U3 が出力段で除外済み）。`choice=A`→item_left 勝ち。items で層を自己完結取得可能。

## スコープ境界
- **U4b に含む**: `scripts/bt_aggregate`（CLI: エクスポート JSON を読み BT 推定 → 結果出力）、BT 推定の純ロジック、Likert 較正、識別可能性チェック、出力（BTResult）。
- **U4b に含まない**: 参加者/管理 API（U2/U3）、エクスポート生成（U3）、トークン発行/プール投入（U4a）。**アプリ本体（Worker）とは分離**（`scripts/`）。
- **依存**: `schema/`（`ExportBundle` 型・`EXPORT_FORMAT_VERSION`）のみ import。Worker・D1 に依存しない。

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【最重要・BT 推定手法と依存】
- **★A（推奨）**: **MM アルゴリズム（minorization–maximization）を純 Python で実装**（依存ゼロ）。BT の最尤推定の定番反復法（各 item の強度 πᵢ を `π'ᵢ = wᵢ / Σⱼ (nᵢⱼ/(πᵢ+πⱼ))` で反復更新、収束まで）。数値的に安定・実装が短く監査可能・追加依存なし。**スコアは log スケール（θᵢ = log πᵢ）で出力**（BT 尺度上の位置）。反復回数・収束閾値はパラメータ化。
- **B**: `scipy.optimize` で負の対数尤度を最小化。→ scipy 依存を足す価値がこの規模では薄い（MM で十分・再現性も高い）。ただし将来必要なら差し替え可能な構造にする。
- **C**: numpy ベースのロジスティック回帰として解く。→ numpy 依存。MM の pure-Python で足りる。

[Answer]:

### Q2【識別可能性・安定化】比較グラフの連結性と疎データ
- **★A（推奨）**: (i) **比較グラフの連結成分を検出**し、非連結なら **警告 + 最大連結成分のみで推定**（コンポーネント間は比較不能である旨を出力に明記）。(ii) 疎データ安定化として **弱い正則化（各ペアに仮想的な引き分け 1 件を加える Bayesian prior 相当＝スムージング）** を既定 ON（新作の対戦数が少なくても発散しない）。(iii) 完全勝ち/完全負けの item も正則化で有限スコアに収まる。強度は正規化（幾何平均 = 1 / Σθ = 0）して位置を固定。
- **B**: 連結性を見ず素朴に MM。→ 非連結・完全分離でスコアが発散/非同定。研究データの誤読を招く。

[Answer]:

### Q3【Likert 較正アンカー】BT 尺度の解釈
ブリッジ Likert（一部作品の 1–7 絶対評定）を較正アンカーに使う（US-R04 チェックリスト）。
- **★A（推奨）**: **アンカー作品（Likert 評定あり）について「平均 Likert」と「BT スコア θ」の対応から線形写像（θ → 解釈可能スコア）を最小二乗で当て**、全作品の BT スコアをその写像で**解釈可能尺度（Likert 相当）に較正**して併記。生の θ と較正後スコアの両方を出力。アンカーが 2 件未満なら較正はスキップ（生 θ のみ・警告）。**層（layer）を各作品に付与**し「新作のプロ水準に対する相対位置」を層別サマリで示す。
- **B**: Likert を推定に組み込む（BT + Likert の同時モデル）。→ モデルが複雑化。US-R04 は「較正アンカーとして**解釈に利用**」＝事後の写像で足りる。分離が明快。

[Answer]:

### Q4【出力形式】BTResult
- **★A（推奨）**: **`BTResult = { schema_version入力の確認, n_items, n_comparisons, n_components, converged, iterations, items: [{item_id, layer, bt_score(θ), calibrated_score|null, rank, matches, wins}], calibration: {anchors, slope, intercept}|null, warnings: [] }`**。出力は **JSON（機械可読）+ 人間可読テーブル**（層別・スコア降順、新作＝層ラベルで判別）。ファイル + stdout。
- **B**: スコアのみの CSV。→ 収束情報・較正・警告・層が失われ研究解釈に不足。

[Answer]:

### Q5【入力・CLI】エクスポート JSON の受け取り
- **★A（推奨）**: CLI 引数で **エクスポート JSON ファイルパス**（US-R04「US-R02 のエクスポートファイル」）。`schema_version` を読み **`EXPORT_FORMAT_VERSION` と一致を検証**（不一致は警告/エラー＝契約 BR-U3-07 の版管理と対応）。U3 からの取得は curl（Infra 申し送り）で別途。出力先はオプション（既定 stdout + `--out` でファイル）。**judgments は本番のみ前提**（U3 が保証済み・U4b で再フィルタしない）。
- **B**: 標準入力パイプのみ。→ ファイル入力の方が反復運用（複数スナップショット比較）に向く。

[Answer]:

### Q6【依存管理】scripts の依存
- **★A（推奨）**: **追加依存なし（pure-Python 標準ライブラリのみ）**。BT=MM・較正=最小二乗（手実装）・JSON 標準。`pyproject.toml` に U4b 用の新規依存を足さない（F-1 の依存制約は Worker 側の話だが、scripts も依存最小が保守上有利）。将来 numpy/scipy が必要になれば dev 依存で追加可能な構造。
- **B**: numpy/scipy を scripts 依存に追加。→ この規模（items 約 95・判定 数千）では pure-Python で十分高速。

[Answer]:

### Q7【Testable Properties】PBT/単体の対象
- **★A（推奨）**: **BT 推定の不変条件を PBT**（PBT-03 系, U4b は純粋関数中心ゆえ PBT 適用が自然）:
  - **単調性**: item A が B に常に勝つデータ → `θ_A > θ_B`。
  - **決定論・収束**: 同一入力 → 同一結果（固定初期値・反復）。
  - **スケール正規化**: `Σθ = 0`（or 幾何平均 1）。
  - **較正の整合**: アンカーの (平均 Likert, θ) に対する最小二乗写像が正しい（既知の線形データで係数復元）。
  - **識別可能性**: 非連結グラフ → 警告 + 最大成分のみ。
  単体（example）で CLI 入出力・schema_version 検証・出力形式。
- **B**: example ベースのみ。→ 推定の不変条件の反例探索が弱い。

[Answer]:

---

**回答後の流れ**: 回答の曖昧さを点検（曖昧なら追加質問）→ Part 2 で 3 成果物（business-logic-model / business-rules BR-U4b-xx / domain-entities: BTResult）を生成（frontend-components は N/A）→ 標準 2 択（Request Changes / Continue → **NFR Requirements〈U4b〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
