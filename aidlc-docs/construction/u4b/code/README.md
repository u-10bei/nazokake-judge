# U4b Code — bt_aggregate（BT 集計スクリプト・最終ユニット）

**ストーリー**: US-R04（新作のプロ水準に対する相対位置を BT 尺度で確認）。
**位置づけ**: 判定装置の一巡クローズ — 投入(U4a)→発行(U4a)→参加(U2)→進捗/エクスポート(U3)→**BT 集計(U4b)**→新作の位置確認。
**性質**: オフライン pure-Python・**追加依存なし**（標準ライブラリのみ, BR-U4b-13）・非デプロイ。`schema/`（ExportBundle 入力・BTResult 出力）のみ依存。**Worker/D1 非依存・migration なし**。

---

## 構成（LC-U4b とファイル一対一, Q1=A）

| ファイル | LC | 役割 |
|---|---|---|
| `scripts/bt_aggregate/aggregate.py` | LC-01 | 正準集計 3 点セット（`aggregate` / `match_counts`）。**生カウント返却** |
| `scripts/bt_aggregate/graph.py` | LC-02/03 | `connected_components` / `largest_component` / `restrict_to_component` |
| `scripts/bt_aggregate/mm.py` | LC-04 | `fit_bt`（MM 擬似データ・成分非依存・**α は本関数内部のみ**） |
| `scripts/bt_aggregate/calibrate.py` | LC-05 | `calibrate`（target_ref=item_id 単回帰・スキップ条件） |
| `scripts/bt_aggregate/assemble.py` | LC-06 | `assemble_result`（除外可視化・rank・source エコーバック） |
| `scripts/bt_aggregate/__main__.py` | LC-07 | CLI（版検証・オーケストレーション `aggregate_bundle`・終了コード・出力整形） |
| `src/schema/bt.py` | — | 出力契約 `BTResult`/`BTItemScore`/`Calibration`/`BTSource`（Pydantic v2） |

---

## 使い方

```bash
# 1) 入力取得（U3 エクスポート・Basic 認証・curl 経路が正）
curl -u $ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD \
     -o export.json "https://<host>/admin/export?format=json"

# 2) BT 集計（既定 α=1.0 / max-iter=10000 / tol=1e-10）
uv run python -m scripts.bt_aggregate export.json --out bt_result.json

# 感度チェック推奨（実データ適用時）:
#   α=1.0 は観測 1 回のペアで擬似データが実データと同量＝比較的強い縮小。
#   α∈{0.5, 1.0, 2.0} で再実行し順位の頑健性を確認する（BTResult.alpha で使用値追跡）。
#   → EMNLP 付録の再現性・頑健性記述にそのまま流用可。
uv run python -m scripts.bt_aggregate export.json --alpha 0.5 --out bt_a0.5.json
uv run python -m scripts.bt_aggregate export.json --alpha 2.0 --out bt_a2.0.json
```

### 出力（DP-U4b-03・二重表示）
- `--out` 指定時: **JSON→ファイル**、**人間可読テーブル→stdout**。
- `--out` 省略時: **JSON→stdout**（パイプ可能）、**人間可読テーブル→stderr**（stdout を汚さない）。
- warnings は `BTResult.warnings`（機械可読・CI）とテーブル冒頭（日本語・対話運用）に二重表示。

### 終了コード契約（U4b-NFR-11 / DP-U4b-03）
| コード | 条件 |
|---|---|
| **1（失敗）** | 入力ファイル不在・JSON パース不能・ExportBundle 検証失敗・版不一致（既定, BR-U4b-11）・**パラメータ不正**（`--alpha ≤ 0` / `--max-iter < 1` / `--tol ≤ 0`） |
| **0（成功）** | 正常 + warnings 系（非連結・較正スキップ・未収束・版不一致緩和・除外 item） |

**パラメータ検証**（DP-U4b-03: 純関数の前提条件は CLI 境界で強制）: `mm.fit_bt` は α>0 のとき
w̃_i>0＝log/除算が有限（BR-U4b-03）。README の α 感度チェックで境界値を試す運用経路から
`--alpha 0`（math domain error）や `--alpha -1`（θ 全 0 の無意味な結果）に到達しうるため、
CLI 境界で `--alpha>0` / `--max-iter≥1` / `--tol>0` を強制し、違反は非0終了に写す。

---

## 設計上の不変条件（テストで固定しきれない仕様の明文化）

1. **α 適用位置**（Infra Design §11 / Q2）: `aggregate`=**生カウント**、α（`w̃_ij=w_ij+α/2, ñ_ij=n_ij+α`）は **`fit_bt` 内部のみ**、`BTResult.matches/wins` は**生**。→ U3 winrate（BR-U4b-08）と突合可能（PU4b-6）。`aggregate.py`/`mm.py`/`assemble.py` の 3 箇所 + PU4b-6 で二重防御。
2. **MM 定式化**（BR-U4b-01）: 擬似データ拡張版（分子一律 α 加算の別式は不採用）。単調性 PU4b-1 は両式で通るため定式化を `mm.py` のコメントで固定。
3. **rank 同値処理**（Step 6）: スコア（θ）降順・**θ 同値は item_id 昇順で安定順位付け**。対称構造で θ 厳密一致しうるため規則自体を固定（PU4b-2 の決定論は再実行一致しか保証しない）。
4. **単調性の適用範囲**（PU4b-1）: 正則化 ON で保証されるのは**次数対称な完全総当たり**での単調性。不規則グラフは α が疎 item を非対称に縮め順位が入れ替わりうる（BR-U4b-01「疎な新作ほど強く縮む」）。PBT ジェネレータは完全総当たりに限定して堅牢な条件のみ検証。

---

## テスト（PU4b・PBT-03 が主, PBT-02 非該当）

- **PBT**（`tests/pbt/test_bt_properties.py` + `bt_generators.py`）: PU4b-1 単調性（完全総当たり）/ PU4b-2 決定論+置換不変性（左右反転+シャッフル）/ PU4b-3 成分内 Σθ=0 / PU4b-4 識別可能性（非連結→最大成分・純関数合成）/ PU4b-5 較正係数復元。ジェネレータは連結/非連結を両生成（U4b-NFR-07）。
- **unit**（`tests/unit/u4b/test_bt.py`）: PU4b-6 U3 突合（matches/wins 一致・α 未混入）/ PU4b-7 版検証 / 終了コード契約 / rank 同値 / 較正閉形式・スキップ・target_ref∉items 除外。
- **結果**: unit+PBT **57 件全緑**（U1/U2/U3/U4a 回帰含む, ci profile）。**migration/wrangler.toml/deploy.yml/src/backend 変更なし**。

## 動作確認（非デプロイ・実機確認対象なし）
検証は PBT+unit で完結（公開面を作らないオフライン CLI ゆえ, U4b-NFR-13）。実データ 5 判定・非連結/較正/除外 item を含むサンプルで CLI 一巡を確認（pro→rank1・新作→最下位・孤立 item は bt_score=null・Σθ=0・calibrated が Likert 尺度へ写像）。
