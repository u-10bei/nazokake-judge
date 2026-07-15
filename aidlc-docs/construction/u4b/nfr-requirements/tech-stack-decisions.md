# U4b Tech Stack Decisions — BT 集計スクリプト（bt_aggregate）

U1 の TSD-01〜08 ほかを前提に、U4b 追加分を **TSD-U4b-NN** で定義する。U4b は `scripts/` 配下の**オフライン pure-Python CLI**（Worker/D1 非依存）。

---

## TSD-U4b-01: BT 推定（MM・擬似データ正則化）
- **MM アルゴリズム（Hunter 2004）を純 Python** で実装（BR-U4b-01）。**擬似データ拡張**で正則化: 各観測ペアに仮想引き分け α 件 → `w̃_ij=w_ij+α/2, ñ_ij=n_ij+α`、素の Hunter `π_i ← w̃_i/Σ_j ñ_ij/(π_i+π_j)`（`w̃_i=w_i+(α/2)·d_i`）。θ=log π、**最大連結成分内 Σθ=0** 正規化。反復上限・収束閾値パラメータ化。
- 根拠: BR-U4b-01/03/04, U4b-NFR-02/04。

## TSD-U4b-02: 行順序不問の決定論（正準ソート）
- 推定前に **items・観測ペア・judgments 集計を `item_id` で正準ソート**してから反復・Σ 加算する（浮動小数の加算順依存を除去）。**同一データ（行順序不問）→ 同一 BTResult**（U4b-NFR-01）。乱数不使用・固定初期値。
- 根拠: U4b-NFR-01/02, PU4b-2（置換不変性）。

## TSD-U4b-03: 依存管理（pure-Python 標準ライブラリのみ）
- **追加依存なし**。MM=手実装、較正=単回帰（閉形式・手実装）、連結成分=BFS/DFS（手実装）、JSON=標準 `json`、CLI=標準 `argparse`。numpy/scipy を足さない（BR-U4b-13, U4b-NFR-09）。
- `pyproject.toml` に U4b 用の新規依存を追加しない。
- 根拠: BR-U4b-13, Q6。

## TSD-U4b-04: CLI・入出力・終了コード
- `scripts/bt_aggregate`（`python -m scripts.bt_aggregate <export.json>` / 直接実行、U4a と同じ `_bootstrap` で src 解決）。オプション `--out`/`--alpha`/`--max-iter`/`--tol`/`--allow-version-mismatch`。
- 出力: **JSON（BTResult）+ 人間可読テーブル**（層別・スコア降順）。warnings を目立たせる（日本語）。
- **終了コード**: 非0=版不一致（既定）・入力ファイル不在・JSON パース不能・ExportBundle 検証失敗（U4b-NFR-11）。0=正常 + warnings 系（非連結・較正スキップ・未収束）。
- 版検証: `schema_version` vs `EXPORT_FORMAT_VERSION`、不一致は既定エラー（`--allow-version-mismatch` で warnings 続行, BR-U4b-11）。
- 根拠: U4b-NFR-10/11, BR-U4b-11。

## TSD-U4b-05: schema/ への型追加
- **`src/schema/bt.py`（新規）**: `BTResult` / `BTItemScore` / `Calibration`（Pydantic v2）。`schema/__init__` に公開。`BTResult.source={schema_version, exported_at}`（BR-U4b-09）。**DDL 変更なし**（D1 非依存）。
- 入力 `ExportBundle`（U3, `admin_views.py`）を消費（再定義しない）。
- 根拠: domain-entities.md, BR-U4b-09。

## TSD-U4b-06: テスト
- **PBT**（`tests/pbt/`）: PU4b-1（単調性）/PU4b-2（決定論+置換不変性）/PU4b-3（最大成分内 Σθ=0）/PU4b-4（識別可能性・非連結）/PU4b-5（較正係数復元）。ジェネレータは**連結/非連結を両方生成**（U4b-NFR-07）。PBT-03 が主、PBT-02 非該当明記（U4b-NFR-08）。
- **unit**（`tests/unit/u4b/`）: CLI 入出力・版検証（PU4b-7・終了コード）・U3 突合（PU4b-6・matches/wins 一致）・出力形式・較正の閉形式例。
- 根拠: U4b-NFR-06/07/08, Q2。

---

## 決定サマリ
| ID | 決定 |
|---|---|
| TSD-U4b-01 | MM（Hunter 2004）+ 擬似データ正則化（α/2 配分）・最大成分内 Σθ=0 |
| TSD-U4b-02 | item_id 正準ソートで行順序不問決定論 |
| TSD-U4b-03 | pure-Python 標準ライブラリのみ（追加依存なし） |
| TSD-U4b-04 | argparse CLI・JSON+テーブル・終了コード網羅・版検証 |
| TSD-U4b-05 | schema/bt.py（BTResult 等）・DDL 変更なし |
| TSD-U4b-06 | PBT（PU4b-1〜5・連結/非連結生成）+ unit（CLI/版/U3 突合） |

## 後続への申し送り
- **NFR Design**: MM/較正/連結成分の LC 配置（純関数）・正準ソートの強制点・CLI 境界・終了コード契約を DP/LC に落とす。
- **Infrastructure Design**: U4b は `scripts/` 追加のみ（Worker/D1/デプロイ無関係・migration なし・シークレットなし）＝差分ほぼゼロ。
- **Code Generation**: `scripts/bt_aggregate`（MM・較正・連結成分・CLI）、`src/schema/bt.py`、PBT/unit。
