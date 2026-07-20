# U6 Tech Stack Decisions — 層拡張 + 事前生成割当

**方針**: **既存スタックの範囲内で完結**（案 A′ = Python Workers + D1 + raw workers API + Pydantic v2, src/ レイアウト F-8）。**新規ライブラリ・新規サービスはゼロ**。U6 の技術判断は「**割当を実行時から設計時へ移す**」ための構造選択に集約される。

---

| ID | 決定 | 根拠 |
|---|---|---|
| **TSD-U6-01（migration 0005 は子行退避方式）** | `pairs_bak` に子行を退避 → `items` 再構築 → 列を明示して復元 → `pairs_bak` 破棄。**`PRAGMA` による FK 無効化は採らない**（`foreign_keys=OFF` / `defer_foreign_keys=ON` とも **D1 の migration 実行環境では効かないことを実測**）。 | U6-NFR-01 |
| **TSD-U6-02（層値は enum 拡張 + `POOL_LAYERS` 明示定数）** | `Layer` に `ANCHOR`/`PRACTICE` を追加し、**充足判定は `for layer in Layer` の走査をやめ `POOL_LAYERS = (PRO, AI, EDIT, RULE, ANCHOR)` の明示定数**に対して行う。**層値を足すたびに「非空」要求が自動で増える構造を断つ**（`practice` を足すと「practice 非空」まで要求する誤動作になる）。 | BR-U6-05 |
| **TSD-U6-03（プラン格納は D1・新規 2 テーブル）** | `assignment_plan`（`plan_set`+`plan_index`+`idx` を PK）/ `assignment_plan_meta`（`seed`・`is_active` 等）。**JSON ファイルで持たない**（D1 が正の設計に反する・配布経路が増える）。 | BR-U6-09/12 |
| **TSD-U6-04（プラン生成はオフライン CLI・pure-Python）** | `scripts/plan_generate.py`（`scripts/` 配下・**非デプロイ**・`_bootstrap` で src 解決・**追加依存なし**）。**正則グラフ構成 + スロット分割は標準ライブラリのみ**（`random.Random(seed)` で決定論）。U4a/U5 の CLI と同型。 | BR-U6-11 / TSD-U5-05 流用 |
| **TSD-U6-05（投入・activate は管理 API 経由）** | `POST /admin/plan` / `POST /admin/plan/activate` を**既存 AuthGuard 背後**に追加（raw workers API + `on_fetch` 手動ディスパッチ）。**ルート名で操作を明示**（ブール引数で意味を変えない、TSD-U5-04 と同流儀）。**D1 直投入は採らない**（証跡が残らない）。 | U6-NFR-17 |
| **TSD-U6-06（証跡はプラン内容のハッシュで取る）** | `admin_log` に **`seed` + プラン内容ハッシュ**（標準 `hashlib`）を記録する。**`plan_set` 名だけでは改竄・取り違えを検出できない**ため、**内容に紐づく識別子**を残す。 | U6-NFR-18 |
| **TSD-U6-07（`plan_index` は `tokens` の NULL 許容列）** | `ALTER TABLE tokens ADD COLUMN plan_index INTEGER`（**NULL 許容ゆえテーブル再構築は不要**）。**NULL = 従来どおりオンライン生成にフォールバック**（U5 の `likert_targets IS NULL` と同型のイディオム）。 | U6-NFR-14 |
| **TSD-U6-08（割当の置換は `session.py:53` の 1 箇所）** | `generate_pairs` の呼び出しは**その 1 箇所のみ**（実装確認済み）。**`save_pair_sequence` 以降の原子保存・`likert_targets` の同一 batch 保存（U5 DP-U5-02）は一切変更しない**。**`generate_pairs` 自体は削除しない**（既存 PBT・将来の選択肢を残す, BR-U6-17）。 | BR-U6-17 / 事実 #5 |
| **TSD-U6-09（Likert はパラメータ値の変更のみ）** | `AssignmentParams.likert_fixed_targets` に **10 件全指名**。`select_likert_targets` は固定アンカーを最優先で採用し want 件で即 return するため、**ラウンドロビンは走らず実装変更ゼロ**。 | BR-U6-06 |
| **TSD-U6-10（テスト振り分け）** | **PBT**: PU6-1〜7（露出 gap=0 / 全体連結 / k≤3 / 同一ペア 0 / 層間 ≥0.65 / 決定論 / **ブロック連結**）。ジェネレータは **n・E・J を振る**（U6-NFR-10）。**失敗系**（正則不能・分割総和≠J）も検証。<br>**unit**: `POOL_LAYERS` フィルタ / `plan_index` 引き当て / 補充トークン / `admin_log`。<br>**integration（実 D1）**: **0005 をデータがある状態で適用** + U2/U3/U4a/U5 回帰。 | U6-NFR-09〜13 |

---

## 既存スタックからの差分サマリ

| 項目 | 差分 |
|---|---|
| ライブラリ / 依存 | **なし**（標準 `random` / `hashlib` / `json` のみ） |
| D1 | **migration 0005**（`items` 再構築 + `assignment_plan` / `assignment_plan_meta` 新規 + `tokens.plan_index` 追加） |
| Worker ルート | `/admin/plan` / `/admin/plan/activate` **追加**（既存 Basic 認証背後） |
| `scripts/` | **`plan_generate.py` 追加**（非デプロイ） |
| `src/backend/domain` | `POOL_LAYERS` 定数追加・`pool_sufficiency` の走査を置換。**`assignment.py` は無改修** |
| `src/backend/participant` | `session.py:53` の割当をプラン引き当てに置換（**フォールバック経路は残す**） |
| 型契約（`schema/`） | `Layer` に 2 値追加・`AssignmentPlanRow`/`AssignmentPlanMeta`/`PlanVerification` 追加。**`Item`/`ExportItem`/`EXPORT_FORMAT_VERSION` は不変** |
| `wrangler.toml` / `deploy.yml` / `frontend/` | **すべて無変更** |
| U3 / U4b | **すべて無変更**（テストも無改修で緑を維持＝形式不変の証拠） |
