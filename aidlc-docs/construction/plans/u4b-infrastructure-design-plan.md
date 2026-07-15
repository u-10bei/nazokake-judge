# U4b Infrastructure Design Plan — BT 集計スクリプト（bt_aggregate・最終ユニット）

**ユニット**: U4b。LC-U4b（aggregate / connected_components / restrict_to_component / fit_bt / calibrate / assemble_result + 薄い CLI）を実インフラにマップする。
**前提（既決・U1/U4a/U2/U3 で確定）**: 案 A′（Python Workers + D1, raw workers API, **src/ レイアウト F-8**）。**共有インフラ（D1 + schema/）は U1 所有**（`shared-infrastructure.md`）。同一 Worker・実験用サブドメイン一本・CI デプロイ（`deploy.yml`, U4a 機能化済み）・Basic 認証境界（`ADMIN_BASIC_*`, U4a 導入済み）。**U4a CLI（token_issue/pool_ingest）が確立した「scripts/ 配下の非デプロイ pure-Python」パターン**を踏襲。

**方針**: U4b は**オフライン pure-Python CLI**（`schema/` のみ依存, BR-U4b-13）。新規インフラは**実質ゼロ**——差分は **`scripts/bt_aggregate` と `src/schema/bt.py` のファイル追加のみ**。**Worker/D1/デプロイ/migration/シークレット/CORS/Static Assets すべて無関係・無変更**。入力は U3 エクスポート（curl 経路 = U3 Infra からの申し送り）、出力は BTResult JSON + 人間可読テーブル（ローカル保管＝運用責任, U4b-NFR-13）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `construction/u4b/infrastructure-design/infrastructure-design.md`（差分中心）を生成します（共有分は既存 `shared-infrastructure.md` を参照）。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-15, 全 4 問 ★A）
- [x] `construction/u4b/infrastructure-design/infrastructure-design.md`（LC-U4b→インフラ差分＝実質ゼロ: scripts/ 追加のみ・非デプロイ・入力 curl 取得〈U3 申し送り〉・schema_version 検証・出力ローカル保管・token 非参照〈U4b-NFR-12〉・**α 適用位置の不変条件を Code Gen へ申し送り**・実行/動作確認方針）

---

## インフラカテゴリ適用性評価（U4b・差分のみ）
| カテゴリ | 適用 | 判断根拠 |
|---|---|---|
| **Compute** | N/A（Worker 無関係） | U4b はローカル/CI 実行の pure-Python CLI。**Worker にルート追加なし**（オフライン, U4b-NFR-12）。U4a CLI と同型（`scripts/` 非デプロイ）。→ Q1 |
| **Storage** | N/A（D1 非依存） | 入力はファイル（U3 エクスポート JSON）・出力はファイル（BTResult JSON）。**D1 バインディング不使用・migration なし**（DDL 変更なし, LC-U4b `bt.py` は DDL 非関与）。 |
| **Networking** | N/A | オフライン（ネットワーク不要, U4b-NFR-12）。**API 公開面なし**（U4b-NFR-13）。CORS 無関係。 |
| **Secrets** | N/A（差分なし） | token 非参照（U4b-NFR-12）＝認証情報不要。入力取得の curl（U3 申し送り）は既存 `ADMIN_BASIC_*` を運用者が手元利用するのみ＝**U4b 自体は新規シークレットなし**。→ Q2 |
| **CI/CD** | 流用（無変更） | `deploy.yml` は無変更（test〈unit+PBT〉→ migrations apply〈0001〜0003, 追加なし〉→ deploy）。U4b の追加テスト（PU4b-1〜6 + unit）は**前置テストゲートに自動的に載る**。**bt_aggregate はデプロイ対象外**。→ Q3 |
| **Static Assets** | N/A | フロント無関係。`[assets]` 変更なし。 |
| **Monitoring** | N/A | 単発オフライン CLI。stdout に人間可読テーブル + warnings（DP-U4b-03）。 |
| **Messaging / Scalability / Resiliency** | N/A | 単発・小規模・純計算・外部依存なし（DP-U4b 非採用表）。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Compute / 実行環境】bt_aggregate のホスティング
- **★A（推奨）**: `scripts/bt_aggregate`（`python -m scripts.bt_aggregate export.json`）を **U4a CLI（token_issue/pool_ingest）と同じ「`scripts/` 配下・非デプロイ pure-Python」**として置く。**Worker にルート追加なし**（オフライン, U4b-NFR-12）。`scripts/_bootstrap` で `src` 解決（U4a と同型）。実行はローカル/CI。`src/schema/bt.py`（新規, Pydantic v2）を追加するが **DDL 変更なし・D1 非依存**。
- **B**: Worker エンドポイント化（`/admin/bt` 等）。→ 重い数値反復を Worker CPU 制限（F-4 の教訓）に載せる過剰設計。token を Worker 経路に引き込むリスク（U4b-NFR-12 に反する）。不採用。

[Answer]: A — U4a CLI で確立済みの「`scripts/` 配下・非デプロイ pure-Python・`_bootstrap` で src 解決」パターンの踏襲が正解。B の Worker エンドポイント化は F-4（起動 CPU 制限）の教訓に反するだけでなく、token 付きエクスポートを Worker 経路に往復させ **U4b-NFR-12「計算経路の token 非参照」を構造ごと壊す**ため不採用が正しい。`src/schema/bt.py` 追加は型の置き場としての `schema/` 共有（U1 所有）の範囲内・DDL 非関与も明記どおり。

### Q2【Secrets / 入力取得経路】U3 エクスポートの受け取り
- **★A（推奨）**: U4b の入力（`export.json`）取得は **U3 Infra 申し送りの curl 経路が正**: `curl -u $ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD -o export.json "https://<host>/admin/export?format=json"`。**認証は既存 `ADMIN_BASIC_*` を運用者が手元で使うのみ＝U4b 自体は新規シークレットを一切持たず、コード上も token 非参照**（U4b-NFR-12）。CLI は取得済みファイルを読むだけ（取得と推定を分離）。読み込み時に **`schema_version` vs `EXPORT_FORMAT_VERSION` を検証**（不一致は既定エラー / `--allow-version-mismatch` で warnings 続行, BR-U4b-11）。
- **B**: bt_aggregate 内から HTTP 取得（Basic 認証を CLI に内蔵）。→ token/認証情報を計算経路に引き込み、オフライン性（U4b-NFR-12）と「取得と推定の分離」を壊す。不採用。

[Answer]: A — 「**取得（curl+既存 `ADMIN_BASIC_*`）と推定（ファイル読込のみ）の分離**」が要諦。U4b 自体が新規シークレットゼロ・ネットワークゼロを保つ。**再現性にも効く**——入力がファイルとして固定されるので同一 `export.json` に対する再実行が常に同一 BTResult（U4b-NFR-01/02）＝**スナップショットの監査単位がファイルで閉じる**。B の HTTP 内蔵は認証情報を計算経路に引き込む上「実行のたびに入力が変わりうる」ツールになり、反復判定装置のスナップショット比較運用と噛み合わないため不採用。

### Q3【CI/CD】デプロイ対象と deploy.yml・テストゲート
- **★A（推奨）**: **`deploy.yml` は無変更**。U4b は**デプロイ対象外**（`scripts/bt_aggregate` は Worker バンドルに含めない、U4a scripts と同様）。ただし U4b の**テスト（PU4b-1〜6 + unit: CLI・版検証・終了コード・U3 突合）は既存の前置テストゲート（`uv sync → test → migrations → deploy`）に自動的に載る**＝回帰時はデプロイをブロック。migration 追加なし（0001〜0003 のまま no-op）。
- **B**: bt_aggregate を CI で定期実行するジョブを追加。→ 入力（研究者エクスポート）が随時変わる単発分析ツールに定期ジョブは不整合。運用者が必要時に手元/CI 手動実行。不採用。

[Answer]: A — `deploy.yml` 無変更・デプロイ対象外、かつ **U4b テストが前置ゲートに自動的に載る＝U4b の回帰が Worker デプロイをブロックする構造**は意図どおり。`schema/` を共有する以上、**`bt.py` の型破壊が Worker 側に波及しないことをゲートで保証する意味がある**。B の定期実行ジョブは、入力が研究者の手動エクスポートである以上トリガーが存在せず不整合ゆえ不採用。

### Q4【動作確認 / 出力の扱い】検証方針とローカル保管
- **★A（推奨）**: 正しさの検証は **PBT（PU4b-1 単調性 / PU4b-2 決定論+置換不変性〈シャッフル+左右反転〉/ PU4b-3 Σθ=0 / PU4b-4 非連結→最大成分 / PU4b-5 較正係数復元 / PU4b-6 U3 突合）+ unit（CLI・版検証・終了コード契約・U3 winrate 突合）**に集約（オフライン純関数ゆえテストで完結・実機デプロイ確認は不要）。出力は **BTResult JSON（`--out`）+ stdout 人間可読テーブル + warnings 二重表示**（DP-U4b-03）。**入力エクスポート・出力 BTResult のローカル保管は運用責任**（リポジトリ管理外, U4b-NFR-13）。**Code Gen 申し送り**: LC-U4b-01 の不変条件「**aggregate=生カウント、α 適用は fit_bt 内部のみ、BTResult の matches/wins は生**」を Code Gen plan の Step 記述に一行固定（BR-U4b-08/PU4b-6 U3 突合の成立条件）。
- **B**: デプロイ後の実機動作確認を要求。→ U4b は公開面を作らない非デプロイ CLI（U4b-NFR-13）ゆえ実機確認対象が存在しない。不採用。

[Answer]: A — **実機確認対象が存在しない（公開面なし）ため PBT+unit で検証が完結**、という整理は正確。Code Gen 申し送り「**aggregate=生カウント、α 適用は fit_bt 内部のみ、BTResult の matches/wins は生**」が明文で入ったことを確認——MM 式のときと同様、テストで検出しにくい仕様を plan 側で固定（PU4b-6 は検出網として残る二重防御）。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `construction/u4b/infrastructure-design/infrastructure-design.md`（差分中心・共有分は `shared-infrastructure.md` 参照）を生成 → 標準 2 択（Request Changes / Continue → **Code Generation〈U4b・最終ユニット〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
