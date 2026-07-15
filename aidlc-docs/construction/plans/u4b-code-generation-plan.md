# U4b Code Generation Plan — BT 集計スクリプト（bt_aggregate・最終ユニット）

**ユニット**: U4b（`scripts/bt_aggregate` + `src/schema/bt.py`）。**実装ストーリー US-R04**（新作のプロ水準に対する相対位置を BT 尺度で確認）。
**前段**: Functional Design / NFR Requirements / NFR Design / Infrastructure Design — すべて承認済み（2026-07-15）。
**目的**: LC-U4b-01〜07（6 純関数 + 薄い CLI）を実コードに落とす。**オフライン pure-Python・追加依存なし**（標準ライブラリのみ, BR-U4b-13）。`schema/`（ExportBundle 入力・BTResult 出力）のみ import。**Worker/D1 非依存・migration なし**。

> 実装規約: `scripts/` 配下・**非デプロイ**・`scripts/_bootstrap` で src 解決（U4a `token_issue`/`pool_ingest` と同型）。Pydantic v2（`src/schema/bt.py`）。統計ロジックは副作用なし純関数、副作用（I/O・終了コード）は CLI に集約（DP-U4b-02/03）。

このドキュメントは **Part 1（Plan + 決定点）**。承認後 Part 2 で本計画を**単一の真実**として生成する。

---

## 1. ユニット・コンテキスト

| 項目 | 内容 |
|---|---|
| **実装ストーリー** | US-R04（BT 集計で新作の相対位置を確認）。判定装置の一巡クローズ: 投入(U4a)→発行(U4a)→参加(U2)→進捗/エクスポート(U3)→**BT 集計(U4b)**→新作の位置確認。 |
| **依存** | U1（`schema/`・`EXPORT_FORMAT_VERSION`）、U3（`ExportBundle`/`ExportItem`/`ExportJudgment`/`ExportLikert` = `src/schema/admin_views.py`, 入力の正本を消費・再定義しない）。層の逆流禁止（`scripts`→`schema` の一方向）。 |
| **所有エンティティ** | 出力 `BTResult`/`BTItemScore`/`Calibration`（`src/schema/bt.py` 新規）。**DDL 変更なし・D1 非依存**。 |
| **サービス境界** | 6 純関数（aggregate / connected_components / restrict_to_component / fit_bt / calibrate / assemble_result）+ 薄い CLI。 |

**スコープ外**: 参加者フロー（U2）・管理 API/UI（U3）・トークン発行/プール投入（U4a）。**変更しないもの**: `migrations/`・`wrangler.toml`・`deploy.yml`・`frontend/`・`src/backend/`（Worker）・`src/schema/admin_views.py`（消費のみ）。

---

## 2. 生成ステップ（番号付き・Part 2 の単一の真実）

- [x] **Step 1 — schema `bt.py`**: `src/schema/bt.py`（新規, Pydantic v2）に `Calibration{n_anchors, slope, intercept, anchor_item_ids}`・`BTItemScore{item_id, layer, bt_score|null, calibrated_score|null, component, rank|null, matches, wins}`・`BTResult{source{schema_version, exported_at}, n_items, n_comparisons, n_components, estimated_component_size, converged, iterations, alpha, items[BTItemScore], calibration|null, warnings[str]}`。`src/schema/__init__.py` に公開。DDL 非関与（domain-entities §2/§5）。
- [x] **Step 2 — aggregate（LC-U4b-01・正準集計 3 点セット）**: `scripts/bt_aggregate/…`（配置は Q1）に `aggregate(judgments) -> (wins, pair_counts)`。ペアキー `sorted((i,j))` 正規化で `n_ij` を数え、勝敗は item 単位（`w_i`）で向き非依存に集計（`choice=A`→item_left 勝ち）。**返す wins/pair_counts は生の観測カウント**（α を混ぜない・§Q2 の不変条件）。純粋。
- [x] **Step 3 — connected_components / restrict_to_component（LC-U4b-02/03）**: `connected_components(pair_counts) -> list[component]`（観測ペアを辺とする無向グラフの BFS/DFS）+ `restrict_to_component(wins, pair_counts, component) -> (wins, pair_counts)`（最大連結成分へ制限する独立純関数）。→ PU4b-4 を純関数合成で検証可能に。純粋。
- [x] **Step 4 — fit_bt（LC-U4b-04・MM 擬似データ・成分非依存）**: `fit_bt(wins, pair_counts, alpha, max_iter, tol) -> (theta, converged, iterations)`。**α 適用は本関数内部のみ**: `w̃_ij=w_ij+α/2, ñ_ij=n_ij+α`（観測ペア限定, BR-U4b-03）→ 素の Hunter 更新 `π_i ← w̃_i / Σ_j ñ_ij/(π_i+π_j)`（分母は観測ペアのみ和）。固定初期値 π=1、item_id 昇順で Σ 加算順固定（DP-U4b-01）、`θ=log π`、**成分内 Σθ=0** 正規化（BR-U4b-04）。**分子一律 α 加算の別式は不採用**（BR-U4b-01 注記）。渡された連結な集計を推定するだけ（成分非依存）。純粋。
- [x] **Step 5 — calibrate（LC-U4b-05）**: `calibrate(theta, likert, items) -> Calibration|None`。`target_ref=item_id` で Likert 平均を結合、アンカー={推定対象 ∩ Likert 平均あり ∩ `target_ref∈items`}（`target_ref∉items` は除外+警告, BR-U4b-05）。(平均 Likert, θ) を単回帰（閉形式）。スキップ条件（アンカー<2 / θ 分散 0 / slope≈0）で None（BR-U4b-06）。純粋。
- [x] **Step 6 — assemble_result（LC-U4b-06）**: `assemble_result(...) -> BTResult`。全 item（除外分は `bt_score=null`+`component` で可視化, BR-U4b-07）・`matches`/`wins`（**U3 と同一定義・生カウント**, BR-U4b-08）・`layer`（BR-U4b-10）・`rank`（推定対象内・除外は null）・`calibrated_score=(θ−intercept)/slope`・`source` エコーバック（BR-U4b-09）・`warnings`。純粋。
  - **rank 同値処理（明文固定）**: rank は**スコア（θ）降順、θ 同値は `item_id` 昇順で安定順位付け**（`sorted(key=(-θ, item_id))` の enumerate）。対戦構造が対称な場合 θ が厳密一致しうるため、順位付け規則自体を仕様で固定する（PU4b-2 の決定論は「同一実装の再実行一致」しか保証せず、規則未規定だと Part 2 生成時の実装依存になる＝MM 式・α 適用位置と同系の「テストで固定しきれない仕様は明文化」）。
- [x] **Step 7 — bt_aggregate CLI（LC-U4b-07・薄い I/O 境界）**: argparse（入力パス・`--out`/`--alpha`/`--max-iter`/`--tol`/`--allow-version-mismatch`）・`_bootstrap` で src 解決・ファイル読込・**版検証**（`schema_version` vs `EXPORT_FORMAT_VERSION`, BR-U4b-11）・純関数群のオーケストレーション・**終了コード決定**（DP-U4b-03: 非0=ファイル不在/JSON パース不能/検証失敗/版不一致既定、0=正常+warnings 系）・JSON 出力（`--out` or stdout）+ **人間可読テーブル**（層別・スコア降順 + warnings 冒頭二重表示, Q3）。空 judgments は warnings + 空/生返却。
- [x] **Step 8 — PBT（PU4b-1〜5）**: `tests/pbt/test_bt_*.py`。ジェネレータは**連結/非連結グラフを両方生成**（U4b-NFR-07）+ **左右反転（item_left/item_right 交換時 choice も A↔B 反転）+ judgments シャッフル**。PU4b-1 単調性（A 常勝→θ_A>θ_B・α ON でも保存）/ PU4b-2 決定論+置換不変性（同一 BTResult）/ PU4b-3 成分内 Σθ=0 / PU4b-4 識別可能性（`connected_components→restrict_to_component→fit_bt` の純合成で非連結→最大成分）/ PU4b-5 較正係数復元（既知線形データ）。**PBT-02 非該当**（U4b-NFR-08）。
- [x] **Step 9 — unit（PU4b-6/7 + CLI）**: `tests/unit/u4b/`。**PU4b-6 U3 突合**（同一エクスポートで matches/wins が U3 winrate 定義と一致＝α 未混入の生カウント確証）/ **PU4b-7 版検証**（不一致→既定エラー終了 / `--allow-version-mismatch`→warnings 続行）/ **終了コード契約**（DP-U4b-03 の各ケース）/ CLI 入出力・JSON 構造・人間可読テーブル・較正の閉形式 example。
- [x] **Step 10 — 回帰 + Documentation**: 既存 unit+PBT（U1/U2/U3/U4a）を緑に保つ（`schema/bt.py` 追加が既存に影響なしを確認, Q4）。`aidlc-docs/construction/u4b/code/README.md` にサマリ・CLI 使用例（curl 取得→集計）・PU4b 対応・α 適用位置の不変条件・rank 同値規則・判定装置一巡クローズを記載。**α 感度チェック注記**（Q3）: CLI 使用例に「実データ適用時は α∈{0.5, 1.0, 2.0} の感度チェックを推奨（BTResult.alpha で使用値追跡・EMNLP 付録の頑健性記述に流用可）」を一行添える。

---

## 3. Part 1 決定点（★推奨デフォルト付き。回答は各 [Answer] に記入）

### Q1【コード配置】bt_aggregate のモジュール構成
- **★A（推奨）**: `scripts/bt_aggregate/` を**パッケージ**にし、`__init__.py`・`aggregate.py`（LC-01）・`graph.py`（LC-02/03）・`mm.py`（LC-04 fit_bt）・`calibrate.py`（LC-05）・`assemble.py`（LC-06）・`__main__.py`（LC-07 CLI）に分ける。`python -m scripts.bt_aggregate export.json` で起動。純関数をファイル分割し PBT の import 単位を明確に。`scripts/_bootstrap` 流用。
- **B**: 単一ファイル `scripts/bt_aggregate.py`（U4a token_issue と同じ粒度）。→ 6 純関数 + CLI で 1 ファイルが肥大。純関数ごとの見通し・テスト import が劣る。

[Answer]: A — パッケージ分割（`aggregate.py`/`graph.py`/`mm.py`/`calibrate.py`/`assemble.py`/`__main__.py`）。**LC-U4b-01〜07 とファイルが一対一対応**し、PBT の import 単位が LC 単位と一致＝**DP-U4b-02 の分離をディレクトリ構造で物理的に強制**する形。U4a token_issue との粒度差は「単機能 CLI vs 6 純関数の合成」という責務の差で正当化。B の単一ファイルは PU4b-4 の純合成テスト（graph→mm）の import が濁るため不採用。

### Q2【α 適用位置の不変条件】aggregate=生カウント / α は fit_bt 内部のみ
- **★A（推奨・Infra Design §11 申し送りの実装固定）**: `aggregate` が返す `wins`/`pair_counts` は**生の観測カウント**。擬似データ α（`w̃_ij=w_ij+α/2, ñ_ij=n_ij+α`）は **`fit_bt` の内部でのみ**適用。`BTResult.matches`/`wins`（=assemble が aggregate 由来を載せる）は**生カウント**（BR-U4b-08 の U3 winrate 突合の成立条件）。→ Step 2/4/6 と PU4b-6 で二重に固定。
- **B**: aggregate 段で α 加算済みのカウントを返す。→ matches/wins に擬似分が乗り U3 winrate 定義と食い違う（PU4b-6 が捕捉するが仕様として不正）。不採用。

[Answer]: A — Infra Design §11 申し送りの実装固定。Step 2（aggregate=生）・Step 4（α は fit_bt 内部のみ）・Step 6（matches/wins=生）の 3 箇所 + PU4b-6 の検出網で、**仕様明文とテストの二重防御**が完成。B は不採用。

### Q3【既定パラメータ】α / max_iter / tol の既定値
- **★A（推奨）**: `--alpha` 既定=**1.0**（各観測ペアに仮想引き分け 1 件＝発散防止の最小限）、`--max-iter` 既定=**10000**、`--tol` 既定=**1e-10**（θ の最大変化量）。**使用値は BTResult に記録**（`alpha`・`iterations`・`converged`＝監査、DP-U4b-04）。未収束は `converged=false`+warnings で結果出力（exit 0, BR-U4b-01/U4b-NFR-03）。値は CLI 引数で上書き可。
- **B**: 別の既定（例: α=0.5, tol=1e-8）。→ 妥当だが根拠は同等。数値は上書き可ゆえ既定は保守的な A を採る。

[Answer]: A — α=1.0 は **FD Q2-A で確定した「各観測ペアに仮想引き分け 1 件」の文字どおりの値**ゆえ既定として設計と自己整合。max_iter=10000・tol=1e-10 も本規模（items 約 95）の MM の線形収束に十分保守的。使用値の BTResult 記録 + CLI 上書き可で監査・感度分析を両立。**運用注記（実装変更なし）**: α=1.0 は観測 1 回のペアで擬似データが実データと同量＝比較的強い縮小のため、実データ適用時は **α∈{0.5, 1.0, 2.0} の感度チェック**を推奨手順として README の CLI 使用例に一行添える（EMNLP 付録の再現性・頑健性記述に流用可能）。→ Step 10 で README に反映。

### Q4【回帰の扱い】既存テストの完了基準
- **★A（推奨）**: `src/schema/bt.py` 追加・`scripts/` 追加が既存を壊さないことを確認し、**既存 unit+PBT（U1/U2/U3/U4a）+ U4b 追加分（PU4b-1〜7）をすべて緑**にしてから完了（ブロッキング）。U4b は Worker/D1 非依存ゆえ回帰面は小さいが、`schema/__init__` へのエクスポート追加が既存 import を壊さないことを確認。
- **B**: U4b 追加分のみ検証。→ `schema/__init__` 変更の回帰見落としリスク。不採用。

[Answer]: A — 回帰面は `schema/__init__` のエクスポート追加に局在するが、そこが **Worker バンドルの import 経路上（F-4 のトップレベル import 最小限と接する）**以上、全緑ブロッキングが正しい基準。

---

## 4. 完了基準
- [x] 全 Step `[x]`。`schema/bt.py`・6 純関数・CLI が生成。US-R04 `[x]`。
- [x] **U1/U2/U3/U4a 回帰含め全テスト緑**（PBT: PU4b-1〜5 追加 / unit: PU4b-6/7 + 終了コード契約）。
- [x] **migration/wrangler.toml/deploy.yml/src/backend の変更なし**を確認（差分は `scripts/` + `src/schema/bt.py` のみ）。
- [x] **α 適用位置の不変条件**（aggregate=生カウント / α は fit_bt 内部のみ / matches/wins は生）が Step 2/4/6 + PU4b-6 で固定されていること。
- [x] `aidlc-docs/construction/u4b/code/README.md` サマリ。標準 2 択（Request Changes / Continue → Build & Test〈U4b〉→ **U4b 完了 = 全ユニット完了**）。

---

**Part 2 生成時の運用**: 各 Step を順に生成し完了ごとに `[x]`、US-R04 も `[x]`。**本 plan の [Answer] 欄を記入**（監査証跡の自己完結）。テスト実行実績（unit+PBT 全緑）を提示。U4b は非デプロイ・実機確認対象なしゆえ検証は PBT+unit で完結。
