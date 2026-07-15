# U4b Infrastructure Design — BT 集計スクリプト（bt_aggregate・最終ユニット）

**ユニット**: U4b。**U1 の共有インフラ（D1 + `schema/` + CI デプロイ）を流用**し、差分のみを定義する。共有分は `shared-infrastructure.md`、実装規約（F-1〜F-8）は U1 `infrastructure-design.md §2.1`、CI（`deploy.yml`）は U4a `§5`、**`scripts/` 配下の非デプロイ CLI パターン**は U4a `§1/§6` を参照。
**方針**: U4b は**オフライン pure-Python CLI**（`schema/` のみ依存, BR-U4b-13）。**新規インフラは実質ゼロ**——差分は **`scripts/bt_aggregate` と `src/schema/bt.py` のファイル追加のみ**。**Worker/D1/デプロイ/migration/シークレット/CORS/Static Assets すべて無関係・無変更**。入力は U3 エクスポート（curl 経路 = U3 Infra 申し送り）、出力は BTResult JSON + 人間可読テーブル（ローカル保管＝運用責任, U4b-NFR-13）。

---

## 1. LC-U4b → インフラ マッピング（差分）

| 論理コンポーネント | インフラ | 備考 |
|---|---|---|
| **LC-U4b-01〜06（6 純関数）** aggregate / connected_components / restrict_to_component / fit_bt / calibrate / assemble_result | **副作用なし pure-Python**（インフラ非依存） | `schema/` の型のみ import。Worker/D1 非依存。 |
| **LC-U4b-07 bt_aggregate CLI** | **手元/CI の pure-Python**（Worker 外・**非デプロイ**, Q1=A） | `python -m scripts.bt_aggregate export.json`。`scripts/_bootstrap` で src 解決（U4a と同型）。追加依存なし（標準ライブラリのみ, BR-U4b-13） |
| **DataContract `src/schema/bt.py`（新規）** | **既存 `schema/`（U1 所有）にファイル追加** | `BTResult`/`BTItemScore`/`Calibration`（Pydantic v2）。`schema/__init__` に公開。**DDL 変更なし・D1 非依存**（U4b-NFR-13） |
| 入力 `export.json` | **ファイル**（U3 `/admin/export?format=json` を curl 取得, Q2） | 既存 `ADMIN_BASIC_*` を運用者が手元で使用＝**U4b 自体は新規シークレットなし** |
| 出力 `BTResult`（JSON + テーブル） | **ファイル + stdout**（ローカル保管＝運用責任, U4b-NFR-13） | リポジトリ管理外。公開面を作らない |

---

## 2. Compute / Networking（Q1）
- U4b は **Worker にルート追加なし**。重い数値反復（MM 反復）を Worker CPU 制限（F-4 の教訓）に載せず、**ローカル/CI の pure-Python** で実行。
- **オフライン**（ネットワーク不要, U4b-NFR-12）。**API 公開面なし**（U4b-NFR-13）＝CORS 無関係。
- U4a CLI（token_issue/pool_ingest）と同型: `scripts/` 配下・非デプロイ・`_bootstrap` で src 解決。

## 3. Secrets（差分なし）
- **新規シークレットなし**。U4b は **token 非参照**（U4b-NFR-12）＝計算経路に認証情報を一切持たない。
- 入力取得の curl は既存 `ADMIN_BASIC_*`（U4a 導入・手元 `wrangler secret put`）を**運用者が手元で使うのみ**。bt_aggregate 自体は取得済みファイルを読むだけ（**取得と推定の分離**, Q2）。

## 4. Storage（D1 非依存・migration なし）
- 入力・出力ともに**ファイル**。**D1 バインディング不使用・migration 追加なし**（0001〜0003 のまま）。
- `src/schema/bt.py` は型定義のみで **DDL に非関与**（`BTResult` は D1 テーブルに対応しない・入力 `ExportBundle` は U3 で定義済みを消費）。

## 5. 入力取得経路（Q2・U3 Infra 申し送りの受領）
- **curl 経路が正**（同一認証境界）:
  ```
  curl -u $ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD \
       -o export.json "https://<host>/admin/export?format=json"
  ```
- **取得と推定の分離**: CLI は取得済み `export.json` を読むだけ。→ 同一 `export.json` に対する再実行は常に同一 BTResult（U4b-NFR-01/02）＝**スナップショットの監査単位がファイルで閉じ、反復判定装置の複数スナップショット突合運用と噛み合う**。
- 読み込み時に **`schema_version` vs `EXPORT_FORMAT_VERSION` を検証**（不一致は既定エラー / `--allow-version-mismatch` で warnings 続行, BR-U4b-11）。

## 6. CI/CD（`deploy.yml` 無変更, Q3）
- **`deploy.yml` は無変更**。既存フロー `uv sync → test（unit+PBT）→ d1 migrations apply --remote（0001〜0003, 追加なし＝no-op）→ deploy`。
- **bt_aggregate はデプロイ対象外**（Worker バンドルに含めない, U4a scripts と同様）。
- ただし **U4b の追加テスト（PU4b-1〜6 + unit: CLI・版検証・終了コード契約・U3 突合）は前置テストゲートに自動的に載る**＝**回帰時は Worker デプロイをブロック**。`schema/` を共有する以上、**`bt.py` の型破壊が Worker 側へ波及しないことをゲートで保証**する意味がある。

## 7. Static Assets / Monitoring（無関係）
- フロント無関係＝`[assets]` 変更なし。
- 単発オフライン CLI。stdout に**人間可読テーブル + warnings**（DP-U4b-03 の二重表示: `BTResult.warnings`=機械可読 / テーブル冒頭=日本語）。

## 8. 実行手順（U4b）
```
1. 入力取得（運用者・手元）:
   curl -u $ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD -o export.json \
        "https://<host>/admin/export?format=json"
2. 集計実行（ローカル/CI・非デプロイ）:
   python -m scripts.bt_aggregate export.json --out bt_result.json
     [--alpha .. --max-iter .. --tol .. --allow-version-mismatch]
3. 確認: stdout の人間可読テーブル + warnings / bt_result.json（ローカル保管＝運用責任）
```

## 9. 動作確認方針（Q4）
- **実機デプロイ確認は対象外**（公開面を作らない非デプロイ CLI, U4b-NFR-13）。正しさの検証は **PBT + unit で完結**:
  - **PBT**: PU4b-1（単調性）/ PU4b-2（決定論+置換不変性〈judgments シャッフル + 左右反転〉）/ PU4b-3（Σθ=0）/ PU4b-4（非連結→最大成分・純関数合成 `connected_components→restrict_to_component→fit_bt`）/ PU4b-5（較正係数復元）/ **PU4b-6（U3 winrate 突合）**。
  - **unit**: CLI・版検証・**終了コード契約**（DP-U4b-03: 非0=版不一致/ファイル不在/JSON パース不能/検証失敗、0=正常+warnings）・U3 突合。
- **PBT-02（ラウンドトリップ）は非該当**（U4b は入力→出力の一方向変換, U4b-NFR-08）。

## 10. トレーサビリティ
| 項目 | 対応 |
|---|---|
| scripts/ 非デプロイ pure-Python・Worker 無関係 | Q1 / U4b-NFR-12 / LC-U4b-07 |
| 新規シークレットなし・token 非参照・取得と推定の分離 | Q2 / U4b-NFR-12 / DP-U4b（オフライン） |
| deploy.yml 無変更・テスト前置ゲートに自動搭載 | Q3 / U4a §5 流用 |
| migration なし（D1 非依存・DDL 非関与） | Storage / U4b-NFR-13 |
| PBT+unit で検証完結・実機確認対象なし | Q4 / U4b-NFR-08/13 |
| curl 経路（U3 申し送りの受領）・schema_version 検証 | Q2 / BR-U4b-11 / U3 Infra §7 |

## 11. 後続申し送り（Code Generation〈U4b・最終ユニット〉）
- **生成対象**: `scripts/bt_aggregate`（LC-U4b-01〜07）、`src/schema/bt.py`（`BTResult`/`BTItemScore`/`Calibration`・`schema/__init__` 公開）、PBT（PU4b-1〜6・連結/非連結 + 左右反転ジェネレータ）+ unit（CLI・版検証・終了コード・U3 突合）。
- **migration・wrangler.toml・deploy.yml の変更なし**（差分は scripts/ + schema/ のファイル追加のみ）。
- **★ α 適用位置の不変条件（Step 記述に一行固定）**: 「**aggregate=生カウント、α 適用は fit_bt 内部のみ、BTResult の matches/wins は生**」。DP/LC からは `fit_bt` シグネチャの `alpha` として含意されるが明文がなかった箇所。**BR-U4b-08 / PU4b-6（U3 winrate 突合）の成立条件**——α を `aggregate` 側に混ぜると matches/wins に擬似分が乗り U3 の winrate 定義と食い違う。PU4b-6 は検出網として残る二重防御だが、MM 式の教訓（テストで検出しにくい仕様も明文で固定）に従い plan/Step で固定する。
- **入力取得は curl 経路**（Basic 認証・既存 `ADMIN_BASIC_*`）を自動化の正とし、`schema_version` を検証して読む（BR-U4b-11）。
