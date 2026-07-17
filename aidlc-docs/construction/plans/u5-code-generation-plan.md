# U5 Code Generation Plan — 出題停止（item retirement）

**ユニット**: U5（著作権配慮による出題停止）。
**前段**: Functional Design / NFR Requirements / NFR Design / Infrastructure Design — すべて承認済み（2026-07-17）。
**目的**: LC-U5-01〜07 を実コードに落とす。**要件の両輪（新規のみ反映 / それまでの結果は有効）を構造で守る**。

> 実装規約: raw workers API + Pydantic v2 / module-level `on_fetch` / **src/ レイアウト**（F-8）/ トップレベル import 最小限（F-4）/ `scripts/` は非デプロイ・`_bootstrap` で src 解決。

このドキュメントは **Part 1（Plan + 決定点）**。承認後 Part 2 で本計画を**単一の真実**として生成する。

---

## 1. ユニット・コンテキスト

| 項目 | 内容 |
|---|---|
| **背景** | **著作権上の配慮**で投入済み作品の一部を今後出題しない必要が発生。要件 = **物理削除は不要 / それまでの判定結果は有効のまま / 進行中セッションへの反映は不要（新規セッションのみ）** |
| **依存** | U1（`schema`・`Repository`・`domain/likert`・`domain/assignment`）、U4a（`handle_admin`・`AuthGuard`・`admin_log`・`scripts/_client`）、U2（`session`・`survey`） |
| **所有 D1 エンティティ** | **migration 0004**（`items.retired_at` / `sessions.likert_targets`・NULL 許容 ×2） |

**スコープ外・変更しないもの**: `wrangler.toml` / `deploy.yml` / `frontend/` / **`Item`** / **`ExportItem`** / **`EXPORT_FORMAT_VERSION`（1.0.0）** / **U3・U4b のコードとテスト**（書き換えたら形式を変えた証拠＝設計違反のシグナル, U5-NFR-04）。

---

## 2. 生成ステップ（番号付き・Part 2 の単一の真実）

- [x] **Step 1 — migration 0004**: `migrations/0004_item_retire.sql`。`ALTER TABLE items ADD COLUMN retired_at TEXT` / `ALTER TABLE sessions ADD COLUMN likert_targets TEXT`。**いずれも NULL 許容**＝テーブル再構築・データ移送とも不要（**安全な no-op 移行**）。インデックスなし。
- [x] **Step 2 — schema ペイロード型**: `src/schema/payloads.py` に `ItemRetireRequest{item_ids: list[str]}` / `RetireResult{ok, retired: int, already_retired: list[str], not_found: list[str]}`。`schema/__init__` に公開。**🔒 `Item` は不変**（`retired_at` を持たせない＝投入経路から廃止が構造的に不可能, BR-U5-12 / DP-U5-04）。
- [x] **Step 3 — `list_active_items` 新設（★DP-U5-01）**: `Repository.list_active_items()` = `SELECT item_id, layer, body, body_ref FROM items **WHERE retired_at IS NULL**`。
  - **🔒 禁止（Step の一行固定）**: **`list_items()` に active フィルタを足さない**（`active_only` 引数の新設も禁止）。`list_items()` は SELECT 列・WHERE ともに**一切変更しない**。踏むと **export 縮小→PU3-3 違反→U4b 破壊** と **フォールバック導出変化→「新規のみ反映」破れ** の**両輪が同時に壊れる**（BR-U5-02）。
- [x] **Step 4 — retire/unretire（★DP-U5-03）**: `Repository.retire_items(item_ids, now_iso)` / `unretire_items(item_ids)`。**冪等性は SQL の WHERE 句で作る**: `UPDATE items SET retired_at=? WHERE item_id IN (...) **AND retired_at IS NULL**`（既に廃止済みは no-op＝**初回時刻を保持**）/ 復活は `SET retired_at=NULL WHERE ... AND retired_at IS NOT NULL`。分類は UPDATE 直前の SELECT（Q2）。**全パラメータ化**（件数分の `?` をバインド）。**`insert_items` の凍結ガードは無改修**（この経路を通らない, DP-U5-04）。
- [x] **Step 5 — Session 保存経路の拡張（★DP-U5-02 原子性）**: `Session.likert_targets: list[str] | None = None` を追加（**`exposure_snapshot` と同じイディオム**）。`save_pair_sequence` の sessions INSERT 列に `likert_targets` を追加し **同一 batch で原子保存**（`json.dumps`）→「ペア列は保存されたが Likert 未保存」の中間状態が**原理的に生じない**。`get_session` の SELECT 列に追加し `json.loads`（NULL→`None`）。**別経路で保存しない**。
- [x] **Step 6 — `get_likert_targets` 単一アクセサ + 3 箇所集約（★BR-U5-04）**: `backend/participant/session.py` に `get_likert_targets(repo, token, params) -> list[str]`（保存値があればそれ / なければ **`list_items()`（全件）から導出**＝旧セッションのフォールバック）。
  - **🔴 3 箇所すべてを本アクセサ経由に統一**: `build_view`（表示）/ `check_complete`（完了判定）/ `survey.submit_likert`（**検証**）。**一部だけ切り替えると「表示されたターゲットを送信すると拒否される」**（表示=保存値・検証=導出値のずれ）。
  - `domain/likert.select_likert_targets` は**無改修**（層の逆流を作らない）。
- [x] **Step 7 — 新規セッションで active を使う**: `session.start_or_resume` の新規分岐で `pool = await repo.list_active_items()` に変更し、`generate_pairs(pool, ...)` と `select_likert_targets(pool, seed, params)` の**両方**を active プールで確定 → `save_pair_sequence` の同一 batch で保存（Step 5）。**練習ペアは同一呼び出し由来ゆえ自動的に効く**（BR-U5-02b・追加対応なし）。**`build_view` の `bodies` は `list_items()`（全件）のまま**（進行中の既存ペア列を解決するため必須）。
- [x] **Step 8 — RetireApi**: `src/backend/admin/api.py` の `handle_admin` に **POST ルート 2 本**追加（`/admin/items/retire`・`/admin/items/unretire`, 既存 AuthGuard 背後）。`ItemRetireRequest` で検証 → Step 4 呼び出し → `RetireResult` を返す。**`admin_log("item_retire"/"item_unretire")`**（対象 `item_id` 列挙・件数・結果。**本文は出さない**）＝**廃止履歴の正**（U5-NFR-09）。
- [x] **Step 9 — 充足判定を active 母数に（BR-U5-09）**: `admin/api.py` の `pool_sufficiency` 呼び出し **2 箇所**（ingest の warn / issue のゲート）を `list_active_items()` に変更。**ingest はマージ後評価**（`list_active_items()` ∪ 入力・入力は常に active）。
- [x] **Step 10 — `pool_retire` CLI**: `scripts/pool_retire.py`（U4a `token_issue` と同型: `_bootstrap` → `scripts/_client` の `post_json`/`base_url` 流用・追加依存なし・**非デプロイ**）。`--unretire` で復活。結果を **`retired`/`already_retired`/`not_found` に分類表示**。**終了コード**: 正常（`already_retired`・`not_found` を含む）= **0**、認証/通信/入力不正 = 非 0。**`not_found` は失敗にしない**が **stderr に警告**（U5-NFR-11）。
- [x] **Step 11 — PBT（PU5-1〜4 + PBT-02）**: `tests/pbt/`。**ジェネレータは廃止済み/現役の混在プールを生成**（U5-NFR-06。「廃止ゼロ件だけを引くジェネレータでは反例探索が空回り」＝U4b の教訓）。
  - **PU5-1**: 廃止済み X → 新規セッションの**ペア列・練習・Likert のいずれにも X が現れない**。
  - **PU5-2**（**「新規のみ反映」の網**）: `likert_targets IS NULL` のセッションで**廃止の前後で Likert ターゲットが一致**。
  - **PU5-3**: retire/unretire の冪等（複数回適用で状態同一・再廃止で**初回 `retired_at` 保持**）。
  - **PU5-4**（**「結果は有効」の網・BR-U5-02 の直接の検出網**）: 廃止の前後で **export の `items` 集合が不変**・**judgments の item ⊆ items** が保たれる。
  - **PBT-02**: `likert_targets` の JSON ラウンドトリップ（**順序を含めて一致**, U5-NFR-07）。
- [x] **Step 12 — unit（example）**: `tests/unit/u5/`。参照済み item の廃止が**成功**（凍結ガードを通らない, BR-U5-05）／`pool_ingest` 再投入で **`retired_at` 不変**（BR-U5-08）／`not_found`・`already_retired` の分類／**充足を割ったら `token_issue` 拒否**（BR-U5-09）／`admin_log` の出力内容（body 非出力）。
- [x] **Step 13 — integration（実 D1）**: `tests/integration/`（既存ハーネス流用）。**0004 適用後に U2/U3 の既存シナリオが緑**（回帰）+ **U5 シナリオ**（参照済み廃止が成功 → 新規セッションに出ない → **進行中セッションには出続ける** → **export の items は縮まない** → 充足割れで発行拒否）。
- [x] **Step 14 — 回帰 + Documentation**: **U1/U2/U3/U4a/U4b の既存 unit+PBT を全緑**（Q4）。`aidlc-docs/construction/u5/code/README.md`（サマリ・CLI 使用例・PU5 対応・**禁止事項**・rank... ではなく**参照先の分離表**）。**運用文書 3 冊に廃止手順を追記**（`runbook.md` の手順・`manual-p-rsch.md` の運用注意）。

---

## 3. Part 1 決定点（★推奨デフォルト付き。回答は各 [Answer] に記入）

### Q1【`get_likert_targets` の実装方式】追加クエリを許容するか
**調査事実**: `build_view` は **`get_session` を呼んでいない**（seed は `seed_from_token(token)` でトークンから導出）。保存値を読むには `get_session` が要る。

- **★A（推奨）**: **`get_likert_targets(repo, token, params)` が内部で `get_session` を呼ぶ**。→ `build_view` / `check_complete` / `submit_likert` それぞれで **D1 クエリが 1 本増える**が、**単純な PK 参照**でありプール約 95 件・参加者は逐次操作の規模では**無視できる**。**呼び出し側のシグネチャが変わらず 3 箇所集約が最も素直に書ける**（＝BR-U5-04 の集約が確実に完遂される）。
- **B**: 呼び出し側で `get_session` して `session` を引き回す（`get_likert_targets(repo, session, params)`）。→ クエリは増えないが、**3 箇所すべての呼び出し側を書き換える必要**があり、集約の意図がシグネチャに現れず**「一部だけ導出のまま」の劣化に気づきにくい**。
- **C**: `Session` に載せず narrow な `get_likert_targets_raw(token)` を追加。→ NFR Design Q1=A（`Session` に載せる・原子保存）と矛盾。不採用。

[Answer]:A

### Q2【分類と冪等の実装】`retired`/`already_retired`/`not_found` の判定
- **★A（推奨）**: **UPDATE 直前に SELECT 1 回**（`SELECT item_id, retired_at FROM items WHERE item_id IN (...)`）で現状を取得 → 分類を確定 → **WHERE 付き UPDATE**（冪等は SQL が保証）。取得は **batch 直前・ロックなし**（U4a 凍結ガードと同じ窓最小化方針）。
  - **窓は報告用にしか影響しない**: 冪等性は `AND retired_at IS NULL` が保証しており、**分類がずれても実害はない**（DP-U5-03）。
  - `not_found` = SELECT に現れなかった `item_id`。
- **B**: UPDATE の結果件数（`meta.changes`）だけで判定。→ `already_retired` と `not_found` が**区別できない**（どちらも 0 件）。運用者が「タイポなのか既に済んでいるのか」を判別できず不採用。

[Answer]:A

### Q3【CLI の入力形式】
- **★A（推奨）**: **引数で `item_id` を列挙**（`python -m scripts.pool_retire i001 i002 i003 [--unretire]`）。廃止は**数件〜十数件**の想定（著作権配慮による個別対応）ゆえファイル入力は過剰。`pool_ingest`（ファイル入力）とは入力の性質が異なる。
- **B**: ファイル入力（`pool_ingest` と統一）。→ 数件のために中間ファイルを作らせるのは運用の摩擦。
- **C**: 両対応（引数 + `--from-file`）。→ 使われない経路を作る。必要になってから足す。

[Answer]:A

### Q4【回帰の扱い】完了基準
- **★A（推奨）**: **U1/U2/U3/U4a/U4b の既存 unit+PBT + U5 追加分（PU5-1〜4 + PBT-02 + unit）をすべて緑**にしてから完了（ブロッキング）。
  - **★ 意味づけ**: **PU3-3（export 自己完結性）が緑 = BR-U5-02 の禁止事項を踏んでいない証拠**。
  - **★ U3/U4b のテストは無改修で緑を維持**する。**U5 のために書き換えたら、それは export 形式を変えた証拠＝設計違反のシグナル**（U5-NFR-04）。
  - integration は実 D1 で 0004 適用後の U2/U3 回帰 + U5 シナリオの実行実績を提示。
- **B**: U5 追加分のみ検証。→ 本ユニットは**既存の共有経路（`Repository` / `session` / `admin api`）を改修する**ため回帰リスクが最も高い。不採用。

[Answer]:A

---

## 4. 完了基準
- [x] 全 Step `[x]`。migration 0004・`list_active_items`・retire/unretire・`Session.likert_targets` 原子保存・`get_likert_targets` 3 箇所集約・RetireApi・充足 active 化・CLI が生成。
- [x] **U1/U2/U3/U4a/U4b 回帰含め全テスト緑**（PU5-1〜4 + PBT-02 追加）、integration（実 D1・0004 適用後）実行実績。
- [x] **🔒 `list_items()` が凍結されている**ことを確認（SELECT 列・WHERE とも無変更・`active_only` 引数なし）。
- [x] **🔴 3 箇所すべてが `get_likert_targets` 経由**であることを確認（`select_likert_targets` の直接呼び出しがサービス層に残っていない）。
- [x] **`wrangler.toml` / `deploy.yml` / `frontend/` / `Item` / `ExportItem` / `EXPORT_FORMAT_VERSION` / U3・U4b のコードとテストの変更なし**を確認。
- [x] `aidlc-docs/construction/u5/code/README.md` サマリ + **運用文書 3 冊への廃止手順の追記**。標準 2 択（Request Changes / Continue → Build & Test〈U5〉）。

---

**Part 2 生成時の運用**: 各 Step を順に生成し完了ごとに `[x]`。**本 plan の [Answer] 欄を記入**（監査証跡の自己完結）。テスト実行実績（全緑）を提示。integration の実 D1 部分は実行実績を提示。


---

## Part 2 実施記録（2026-07-17）

**テスト結果**: unit+PBT **76 緑**（既存 61 + U5 15・ci profile）/ integration（実 D1・miniflare・**migration 0004 適用後**）**37/37 PASS**（U5 13 + 回帰 U2 9 / U3 8 / U4a 7）。

**Part 1 からの逸脱（1 点・実装で判明）**: **PU5-3 / PU5-4 は PBT ではなく integration に配置**した。理由: 両者は **SQL の意味論**（retire の `AND retired_at IS NULL` / `read_export_rows` の SELECT）であり、in-memory ダブルで再現しても**ダブルを検証することにしかならない**。ダブル（`tests/fakes.py`）は**ワイヤリング検証専用**（PU5-1 / PU5-2）と責務を明記した。**PU5-4 は BR-U5-02 の検出網として実 D1 で機能している**（export の items 集合が縮まないことを実測）。

**実装中の発見 2 件**:
1. **D1 は Python `None` の bind を拒否**（既存コードが `_item_upsert_stmt` で明記）。`likert_targets=None` を bind すると失敗するため、**SQL リテラル `NULL` を使う既存イディオム**に合わせて `_session_insert_stmt` を分岐させた。
2. **PBT-02 が `[]` と `None` の区別を炙り出した**。`likert_targets=[]`（Likert 対象なしが確定）と `None`（旧セッション＝未保存）は**意味が違う**——`[]` を `None` に潰すと全件導出フォールバックが走り**本来ないはずの Likert 対象が生える**。`get_session` を truthy 判定から **`is not None`** に修正（偶然正しかったが意図が読めない状態だった）。

**実機で確証**: 「**参照済み item は body 更新を拒否されるが、廃止はできる**」（BR-U5-05 の整理）を実 D1 で確認。

**次**: 標準 2 択（Request Changes / Continue → Build & Test〈U5〉）。
