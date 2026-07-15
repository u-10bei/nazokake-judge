# U4b NFR Design Plan — BT 集計スクリプト（bt_aggregate）

**ユニット**: U4b。NFR Requirements（U4b-NFR-01〜13）を設計パターン（DP-U4b）と論理コンポーネント（LC-U4b）に落とす。U4b は**オフライン pure-Python・純関数中心**ゆえ、DP は「正しさと再現性を構造で守る」点に集約。
**前提（既決）**: MM 擬似データ正則化（BR-U4b-01/03）／行順序不問決定論=item_id 正準ソート（U4b-NFR-01）／未収束 exit0（03）／終了コード網羅（11）／token 非参照（12）／pure-Python 標準ライブラリのみ（13）／PBT 中心・PBT-02 非該当（06/08）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-design-patterns.md`（DP-U4b-NN）/ `logical-components.md`（LC-U4b-NN + 依存方向）を生成します。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-15）
- [x] `construction/u4b/nfr-design/nfr-design-patterns.md`（DP-U4b-01〜04: 正準集計 3 点セット・純関数分離/成分制限の切り出し・終了コード契約・非採用部品表）
- [x] `construction/u4b/nfr-design/logical-components.md`（LC-U4b-01〜07: 6 純関数〈aggregate/connected_components/restrict_to_component/fit_bt/calibrate/assemble〉+ CLI・依存方向）

**回答サマリ**: 全 4 問 A。Q1=正準集計 3 点セット（DP-U4b-01・PBT は左右反転ジェネレータ）。**Q2 精緻化=`restrict_to_component` を独立純関数に切り出し fit_bt を成分非依存に（PU4b-4 を純関数合成で検証）＝LC 6 純関数 + CLI**。Q3=終了コード決定を CLI に集約。

---

## 設計パターン適用性評価（U4b）
| 論点 | 適用 | 方針 |
|---|---|---|
| **正準集計（決定論 + 集計の正しさ）** | **適用（最重要・U4b 固有）** | ペアキー正準化 + item 列ソート + Σ 加算順固定の 3 点セット。→ Q1 |
| **純ドメインロジックの分離** | **適用** | aggregate/連結成分/MM/較正/組立を純関数に分け、CLI は薄い I/O 境界。→ Q2 |
| **エラー処理/終了コード契約** | **適用** | 失敗（非0）と warnings（0）の明確な分離。→ Q3 |
| **識別可能性の可視化** | **適用** | 非連結→最大成分推定・除外 item を bt_score=null+component で残す。→ Q2 |
| キャッシュ/キュー/CB/ロック/スケール | **N/A** | 単発オフライン・小規模・純計算（U1〜U3 と同方針）。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【最重要・正準集計】決定論と集計の正しさを「構造で守る」3 点セット
行順序不問決定論（U4b-NFR-01）は**ソート順**の問題であると同時に**集計の正しさ**の問題。`(i,j)` と `(j,i)` を別キーで数えると `n_ij` が分裂し**擬似データ α 配分も二重**になる（ExportBundle の judgments は pair_id 単位で向き固定だが、同じ item 組が別セッションで逆向き出現は割当上普通に起きる）。
- **★A（推奨）**: **正準集計を 3 点セットで強制**する（DP-U4b-01）:
  1. **ペアキー正準化**: 無順序ペア `(i,j)` を **`sorted((i,j))` の tuple** に正規化してから `n_ij` を数える。**勝敗は item 単位**（`w_i`= その item が勝った回数）で数え、向きに依存しない。→ `n_ij` 分裂・α 二重配分を排除。
  2. **item 列の正準ソート**: 推定対象 item を `item_id` で昇順固定（初期値・反復・Σ の対象順を固定）。
  3. **Σ 加算順の固定**: MM 更新の分母 Σ・θ 正規化の Σ を**ソート済み順**で加算（浮動小数の加算順依存を除去）。
  - **集計を 1 箇所の純関数に集約**（呼び出し側の規律に依存しない）。**PU4b-2 の置換不変性 PBT はジェネレータに「judgments シャッフル + 左右反転（choice も対応して反転）」を含め**、3 点まとめて反例探索する。
- **B**: ソートは item 列のみ・ペアキー正準化なし。→ `n_ij` 分裂・α 二重で BT 推定が歪む（テストで気づきにくい）。不採用。

[Answer]: A — 3 点セット（ペアキー正準化 sorted((i,j))・item 列昇順固定・Σ 加算順固定）を DP-U4b-01 として構造化。要諦は**集計を 1 箇所の純関数に集約＝正準化を規約でなく通過必須の関数化**（Code Gen での劣化経路＝呼び出し側の生 dict 集計を塞ぐ）。PBT ジェネレータは**シャッフル + 左右反転（item_left/item_right 交換時 choice も A↔B 反転）**で 3 点まとめて反例探索。補足: B の n_ij 分裂は「両向きに α が乗り疎ペアほど正則化が倍効き＝新作（疎）のスコアが系統的に歪む」＝装置の目的に直撃する誤りゆえ不採用が正しい。

### Q2【純ロジック分離】LC 配置
- **★A（推奨）**: `scripts/bt_aggregate` を**薄い CLI 境界**（引数解析・ファイル I/O・版検証・終了コード）とし、以下を**純関数**に分ける（副作用なし・PBT 可能）:
  - `aggregate(judgments) -> (wins, pair_counts)`（正準集計・3 点セット, DP-U4b-01）
  - `connected_components(pair_counts) -> components`（BFS/DFS）
  - `fit_bt(wins, pair_counts, alpha, max_iter, tol) -> (theta, converged, iterations)`（MM 擬似データ）
  - `calibrate(theta, likert, items) -> Calibration|None`（単回帰・スキップ条件）
  - `assemble_result(...) -> BTResult`（除外 item 可視化・source エコーバック・matches/wins）
  - すべて `schema/`（ExportBundle/BTResult 型）のみに依存。Worker/D1 非依存・層の逆流禁止。
- **B**: 単一の巨大関数。→ PBT の単位が取れず、不変条件の反例探索が弱い。

[Answer]: A ＋ 配置明確化: **最大連結成分への制限を独立純関数 `restrict_to_component(wins, pair_counts, component) -> (wins, pair_counts)` として切り出す**（CLI インラインにしない）。これにより `fit_bt` は「渡された**連結な**集計を推定するだけ」の**成分非依存関数**になり、**PU4b-4（非連結→最大成分のみ）は純関数合成（`connected_components → restrict → fit_bt`）で直接検証**でき、`fit_bt` の PBT（PU4b-1/2/3）は連結入力前提で単純化される。**LC = 6 純関数（aggregate / connected_components / restrict_to_component / fit_bt / calibrate / assemble）+ 薄い CLI**。

### Q3【エラー処理/終了コード契約】
- **★A（推奨）**: **失敗（非0 終了）** = 入力ファイル不在・JSON パース不能・ExportBundle 検証失敗・版不一致（既定）。**成功（0 終了）** = 正常 + warnings 系（非連結・較正スキップ・未収束・除外 item・版不一致緩和）。warnings は BTResult.warnings（機械可読）+ 人間可読テーブル冒頭（日本語）に**必ず表示**。**例外は CLI 境界で捕捉して終了コードに写す**（純関数はデータ or 例外を返し、終了コード決定は CLI に集約）。
- **B**: 全異常を例外で落とす。→ 非連結・未収束のような「結果は出るが注意」を失敗扱いにすると研究運用（CI 含む）で誤検知。

[Answer]: A — 「純関数はデータ or 例外を返し、**終了コード決定は CLI に集約**」の分離が肝。これで終了コード契約（U4b-NFR-11）のテストが CLI unit 1 箇所に閉じる。warnings の二重表示（BTResult.warnings=機械可読 + テーブル冒頭=人間可読）で CI と対話運用の両方をカバー。

### Q4【適用性評価の確認】
- **★A（推奨）**: キャッシュ/キュー/サーキットブレーカ/ロック/スケール = **N/A**（単発オフライン・純計算・小規模）。numpy/scipy 不使用（標準ライブラリのみ, BR-U4b-13）。意図的な非採用として記録。
- **B**: いずれか導入。→ 規模・性質に対し過剰。

[Answer]: A — cache/queue/CB/lock/scale = N/A（単発オフライン・純計算・小規模）。numpy/scipy 不使用（標準ライブラリのみ, BR-U4b-13）。意図的な非採用として記録。U1〜U3 と同流儀で一貫。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-design-patterns.md`（DP-U4b-NN）/ `logical-components.md`（LC-U4b-NN + 依存方向）を生成 → 標準 2 択（Request Changes / Continue → **Infrastructure Design〈U4b〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
