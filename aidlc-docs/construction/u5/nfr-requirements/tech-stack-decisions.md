# U5 Tech Stack Decisions — 出題停止（item retirement）

**方針**: **既存スタックの範囲内で完結**（案 A′ = Python Workers + D1 + raw workers API + Pydantic v2, src/ レイアウト F-8）。**新規ライブラリ・新規サービス・新規公開面はゼロ**。U5 の技術判断は「既存のどの部品をどう分割するか」に尽きる。

---

| ID | 決定 | 根拠 |
|---|---|---|
| **TSD-U5-01（論理削除の表現）** | **`items.retired_at TEXT`**（NULL=現役 / ISO8601=廃止時刻）。真偽フラグ（`is_active`）ではなく**時刻**を採る＝「いつ止めたか」が DB に残る（著作権対応の経緯）。別テーブル（`retired_items`）は JOIN が全経路に増える割に利点が薄く不採用。 | FD Q1=A / BR-U5-01 |
| **TSD-U5-02（読み取り経路の分割・★中心）** | **`list_items()` は全件のまま凍結**（シグネチャ・挙動を変更しない）+ **`list_active_items()` を新設**（`WHERE retired_at IS NULL`）。**引数フラグ（`active_only=True`）による分岐は採らない**——既定値の反転や呼び出し漏れで**要件の両輪が同時に壊れる**（export 縮小→PU3-3 違反→U4b 破壊 / フォールバック導出変化→「新規のみ反映」破れ）。**関数名で用途を分離**し、劣化経路を構造的に塞ぐ。 | FD Q2/Q5/Q6=A / BR-U5-02 |
| **TSD-U5-03（Likert ターゲットの保存）** | **`sessions.likert_targets TEXT`（JSON 配列）** に開始時確定・保存（ペア列と同じ「開始時確定」原則）。**読み取りは単一アクセサ `get_likert_targets` に集約**（現状 `build_view` / `check_complete` / `submit_likert` の 3 箇所に導出が散在＝一部だけ切替で「**表示されたターゲットの送信が拒否される**」不整合）。JSON は標準 `json` モジュール（追加依存なし）。**順序を保存**（提示順が意味を持つ, U5-NFR-07）。 | FD Q2=A / BR-U5-04 |
| **TSD-U5-04（廃止 API）** | **`POST /admin/items/retire` / `POST /admin/items/unretire`** の**対称な 2 ルート**。既存の **raw workers API + `on_fetch` 手動ディスパッチ**（F-4/F-5）に追加し、**既存 AuthGuard（Basic 認証）の背後**（U4a の単一チョークポイント）。ブール引数 1 本で意味が変わる単一ルートは採らず、**ルート名で操作を明示**＝`admin_log` のイベントも 1:1 に対応。 | FD Q4=A / U5-NFR-12 |
| **TSD-U5-05（CLI）** | **`scripts/pool_retire.py`**（U4a の `token_issue`/`pool_ingest` と同型: `scripts/` 配下・**非デプロイ**・`_bootstrap` で src 解決・**`scripts/_client.py` の `post_json`/`base_url` を流用**）。**追加依存なし**（標準 `urllib` のみ）。`--unretire` で復活。 | FD Q4=A / TSD-U4a-05 流用 |
| **TSD-U5-06（migration 0004）** | **`ALTER TABLE ... ADD COLUMN` ×2**（`items.retired_at` / `sessions.likert_targets`）。**いずれも NULL 許容**ゆえ **0002 のようなテーブル再構築は不要**・データ移送不要。`deploy.yml` は versioned 自動適用ゆえ**無変更**。**インデックスは張らない**（プール約 95 件・全走査で十分）。 | FD Q1=A / U5-NFR-01 |
| **TSD-U5-07（型契約の凍結）** | **`Item` / `ExportItem` / `EXPORT_FORMAT_VERSION`（1.0.0）はすべて不変**。`retired_at` は **`Item` に持たせない**＝`pool_ingest` の経路から廃止・復活が**構造的に不可能**（型でガードの穴を塞ぐ）。`likert_targets` も `Session` モデルには載せず **Repository が JSON を直接読み書き**（型契約を広げない・置き場の最終確定は NFR Design）。 | FD Q6=A / BR-U5-10/12 |
| **TSD-U5-08（テスト振り分け）** | **PBT（Hypothesis）**: PU5-1（新規から消える）/ PU5-2（旧セッション不変）/ PU5-3（冪等）/ **PU5-4（export が縮まない＝BR-U5-02 の検出網）**。ジェネレータは**廃止済み/現役の混在プール**を生成（PBT-07, U5-NFR-06）。**PBT-02 は U5 で新たに該当**（`likert_targets` の JSON ラウンドトリップ・順序保存）。**unit**: 凍結ガード非適用・再投入で `retired_at` 不変・分類・充足割れ拒否・`admin_log`。**回帰**: U1〜U4b 全緑ブロッキング（**PU3-3 緑 = BR-U5-02 非違反の証拠**）+ integration（実 D1・0004 適用後）。 | FD Q2/Q5=A / U5-NFR-05〜08/13 |

---

## 既存スタックからの差分サマリ

| 項目 | 差分 |
|---|---|
| ライブラリ / 依存 | **なし**（標準 `json` / `urllib` のみ） |
| Worker ルート | `/admin/items/retire` / `/admin/items/unretire` **追加**（既存 Basic 認証背後） |
| D1 | **migration 0004**（列追加 2 本・NULL 許容） |
| `scripts/` | **`pool_retire.py` 追加**（非デプロイ） |
| Repository | **`list_active_items()` 追加**（`list_items()` は凍結）・`get_likert_targets` 系・retire/unretire の更新関数 |
| 型契約（`schema/`） | **`ItemRetireRequest` / `RetireResult` 追加のみ**。`Item`/`ExportItem`/`EXPORT_FORMAT_VERSION` は**不変** |
| `wrangler.toml` / `deploy.yml` / `frontend/` | **すべて無変更** |
| U3 / U4b | **すべて無変更**（テストも無改修で緑を維持＝形式不変の証拠） |
