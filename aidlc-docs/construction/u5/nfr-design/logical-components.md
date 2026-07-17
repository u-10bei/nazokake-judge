# U5 Logical Components — 出題停止（item retirement）

**方針**: U5 は**新規コンポーネントを最小限にし、既存の分割と集約で要件を満たす**。新規 LC は 5 件（Repository 3・サービス 1・API 1）+ CLI 1 + migration 1。**U3/U4b の LC は一切変更しない**。層の逆流禁止（`scripts` → `admin API` → `Repository` → D1 / `participant service` → `Repository` + `domain`）。

---

## 論理コンポーネント一覧

### LC-U5-01: `Repository.list_active_items`（新設・★DP-U5-01 の実体）
- **役割**: `list_active_items() -> list[Item]`。`SELECT item_id, layer, body, body_ref FROM items **WHERE retired_at IS NULL**`。
- **🔒 対になる凍結**: **`Repository.list_items()` は SELECT 列・WHERE ともに一切変更しない**（全件を返し続ける）。
- **❌ 禁止**: `list_items()` への active フィルタ追加／`active_only` 引数の新設（BR-U5-02・DP-U5-01）。**これを踏むと要件の両輪が同時に壊れる**（PU5-2 と PU5-4 が同時に落ちる）。
- **依存**: D1（`DB` バインディング）。

### LC-U5-02: `Repository.retire_items` / `unretire_items`（新設）
- **役割**: 冪等な廃止・復活（DP-U5-03）。
  - `retire_items(item_ids, now_iso) -> RetireResult`: 事前 SELECT で分類 → `UPDATE items SET retired_at = ? WHERE item_id IN (...) **AND retired_at IS NULL**`。
  - `unretire_items(item_ids) -> RetireResult`: `UPDATE items SET retired_at = NULL WHERE item_id IN (...) AND retired_at IS NOT NULL`。
- **冪等性は SQL が保証**（既に廃止済みは no-op ＝**初回時刻を保持**）。分類（`retired`/`already_retired`/`not_found`）は**報告用**（窓があっても実害なし, DP-U5-03）。
- **🔒 凍結ガードと分離**: `insert_items` の参照済みガードは**無改修**。本 LC は**その経路を通らない**（DP-U5-04）＝参照済み item でも廃止できる。
- **全パラメータ化**: `IN (...)` は件数分の `?` をバインド（U5-NFR-12）。
- **依存**: D1。

### LC-U5-03: `get_likert_targets`（新設・★単一アクセサ / DP-U5-02）
- **役割**: `get_likert_targets(repo, token, params) -> list[str]`。**Likert ターゲットの唯一の取得経路**。
  ```
  stored = (await repo.get_session(token)).likert_targets
  if stored is not None: return stored                              # U5 以降のセッション
  return select_likert_targets(await repo.list_items(), seed, params)  # 旧セッション（全件・従来挙動を再現）
  ```
- **配置**: `backend/participant/session.py`（**参加者サービス層**）。Repository（I/O）と domain（純粋選定）の**橋渡し**ゆえサービス層が正しい置き場。
- **🔴 集約が必須**: 現在導出が散在する **3 箇所すべてを本 LC 経由に統一**する:

  | 呼び出し元 | 用途 | 集約前の危険 |
  |---|---|---|
  | `build_view` | 画面に**表示**するターゲット | 表示=保存値 |
  | `check_complete` | 完了判定 | 判定基準のずれ |
  | `submit_likert`（`survey.py`） | `target_ref` の**検証** | 検証=導出値 → **表示されたターゲットの送信が拒否される** |

- **依存**: `Repository`（LC-U5-01 の凍結された `list_items()` / `get_session`）、`domain/likert.select_likert_targets`（**無改修**）。
- **層の逆流なし**: `domain/likert.py` は repo に依存しない（純粋関数のまま）。

### LC-U5-04: `RetireApi`（既存 `handle_admin` の拡張）
- **役割**: **`POST /admin/items/retire` / `POST /admin/items/unretire`** の**対称な 2 ルート**を既存ディスパッチに追加。
- **既存 AuthGuard（Basic 認証）の背後**（U4a の単一チョークポイント）＝新規シークレット・新規公開面なし（U5-NFR-12）。
- **`admin_log` に `item_retire` / `item_unretire` を記録**（対象 `item_id` 列挙・件数・結果）＝**廃止履歴の正**（U5-NFR-09 / BR-U5-13）。**本文（`body`）は出さない**。
- **ルート名で操作を明示**（ブール引数 1 本で意味が変わる単一ルートは採らない）＝ログイベントと 1:1 対応。
- **依存**: LC-U5-02、既存 AuthGuard / `admin_log`。

### LC-U5-05: `pool_retire` CLI（新設）
- **役割**: `python -m scripts.pool_retire <item_id...> [--unretire]`。U4a の `token_issue`/`pool_ingest` と**同型**（`scripts/` 配下・**非デプロイ**・`_bootstrap` で src 解決・**`scripts/_client.py` の `post_json`/`base_url` を流用**・追加依存なし）。
- **出力**: `retired` / `already_retired` / `not_found` を**分類表示**。
- **終了コード**: 正常（`already_retired`・`not_found` を**含む**）= **0**。認証失敗・通信失敗・入力不正 = **非 0**（U4a CLI の既存規約）。**`not_found` は失敗にしない**（「既に存在しない＝目的は達成」・冪等な再実行を失敗扱いにすると運用が回らない）が **stderr に警告**（U5-NFR-11）。
- **依存**: LC-U5-04（HTTP 経由）、`scripts/_client`。

### LC-U5-06: `Session` モデル + 保存経路の拡張（既存改修・DP-U5-02）
- **`Session.likert_targets: list[str] | None = None`** を追加（**`exposure_snapshot` と同じ扱い** = JSON カラム ↔ 型付きフィールド）。
- **`save_pair_sequence(session, pairs)`**: sessions INSERT の列に `likert_targets` を追加し、**同一 batch で原子保存**（`json.dumps`）。→ 「ペア列は保存されたが Likert 未保存」の中間状態が**原理的に生じない**（★DP-U5-02 の本命）。
- **`get_session`**: SELECT 列に `likert_targets` を追加し `json.loads`（NULL → `None`）。`extra="forbid"` ゆえ列追加が必要（既存の明示列指定の流儀どおり）。
- **PBT-02（U5-NFR-07）**: 保存/復元が**順序を含めて一致**（Likert の提示順が意味を持つ）。**XC-02 の対象に自然に入る**。

### LC-U5-07: migration 0004（新設）
- `ALTER TABLE items ADD COLUMN retired_at TEXT` / `ALTER TABLE sessions ADD COLUMN likert_targets TEXT`。**いずれも NULL 許容**＝テーブル再構築・データ移送とも不要。**適用しただけでは何も変わらない**（安全な no-op 移行, U5-NFR-01）。
- **インデックスなし**（プール約 95 件・全走査で十分）。`deploy.yml` は versioned 自動適用ゆえ**無変更**。

### DataContract 追加（`src/schema/payloads.py`, U4a と同居）
- **`ItemRetireRequest`** = `{item_ids: list[str]}`（retire / unretire で共用）
- **`RetireResult`** = `{ok, retired: int, already_retired: list[str], not_found: list[str]}`
- **🔒 凍結**: **`Item` / `ExportItem` / `EXPORT_FORMAT_VERSION`（1.0.0）はすべて不変**（BR-U5-10/12・U5-NFR-04）。`Item` に `retired_at` を持たせない＝**投入経路から廃止が構造的に不可能**（DP-U5-04）。

---

## 呼び出し先の固定（★DP-U5-01 の LC 化）

| 呼ぶもの | 呼び出し元 | 理由 |
|---|---|---|
| **`list_active_items()`**（LC-U5-01） | `session.start_or_resume`（新規セッションのペア生成・Likert 選定）／`admin.api` の充足判定 2 箇所（ingest の warn / issue のゲート） | **これから出題するものを選ぶ** |
| **`list_items()`**（凍結・全件） | `build_view` の `bodies` 写像／`get_likert_targets` の旧セッション導出フォールバック | **既に配ったものを解決する** |
| **SQL 直参照**（全件・現状維持） | `read_export_rows("items")`／winrate 集計 | **既に起きたことの事実** |

- **ingest 時のマージ後評価**（BR-U4a-05）は **`list_active_items()` ∪ 入力**（入力は新規＝常に active）。
- **練習ペアは別経路を持たない**（BR-U5-02b）→ `generate_pairs` が同一プール・同一呼び出しで生成するため **active フィルタが自動的に効く**（追加対応なし）。

---

## 依存方向（層の逆流禁止）

```
[ CLI: python -m scripts.pool_retire X --unretire ]   ← LC-U5-05（非デプロイ）
                │ HTTPS + Basic（scripts/_client 流用）
                ▼
   ┌──────── Worker（既存 on_fetch 手動ディスパッチ）────────┐
   │  AuthGuard（既存・単一チョークポイント）                 │
   │      └─▶ RetireApi  /admin/items/retire|unretire        │ ← LC-U5-04
   │              └─▶ admin_log（履歴の正・body 非出力）      │
   └───────────────────────┬─────────────────────────────────┘
                           ▼
        ┌──────────── Repository（I/O 境界）────────────┐
        │ 🆕 list_active_items   （LC-U5-01）           │
        │ 🔒 list_items          （凍結・全件）          │
        │ 🆕 retire_items / unretire_items（LC-U5-02）  │
        │ 🔧 get_session / save_pair_sequence（LC-U5-06）│
        └───────────────────────┬───────────────────────┘
                                ▼
                          D1（migration 0004: LC-U5-07）

[ participant service: session.py ]
   get_likert_targets（LC-U5-03・単一アクセサ）
        ├─▶ Repository（get_session / list_items）      … I/O
        └─▶ domain/likert.select_likert_targets（無改修）… 純粋
   ▲ build_view / check_complete / survey.submit_likert の 3 箇所がここに集約
```

- **一方向依存**: `scripts` → `admin API` → `Repository` → D1 ／ `participant service` → `Repository` + `domain`。
- **`domain` は repo に依存しない**（`select_likert_targets` は純粋関数のまま無改修）。
- **U3（export / winrate）・U4b（BT 集計）の LC には一切触れない**。

---

## 後続への申し送り（Infrastructure Design / Code Generation）

- **Infrastructure Design〈U5〉**: 差分は **migration 0004 の追加のみ**（`/admin/*` は既存ルートへの追加・既存 Basic 認証背後）。**`wrangler.toml` / `deploy.yml` / `frontend/` / シークレット / CORS / assets はすべて無変更**。`deploy.yml` は versioned 自動適用ゆえ 0004 が自動で載る。**適用順は migration → deploy**（U5-NFR-02）。
- **Code Generation〈U5〉**:
  - **禁止事項の再掲**（Step 記述に一行固定）: **`list_items()` に active フィルタを足さない**（`active_only` 引数の新設も禁止）。**`list_active_items()` を新設して新規セッション系・充足判定のみが呼ぶ**（BR-U5-02 / DP-U5-01）。
  - **3 箇所集約の完遂**: `build_view` / `check_complete` / `submit_likert` の**すべて**を `get_likert_targets` 経由に。**一部だけ切り替えると「表示されたターゲットの送信が拒否される」**。
  - **原子保存**: `likert_targets` は `save_pair_sequence` の**同一 batch**で INSERT（別経路にしない）。
  - **回帰の意味づけ**: **PU3-3 が緑 = BR-U5-02 の禁止事項を踏んでいない証拠**。**U3/U4b のテストを書き換えたら形式を変えた証拠＝設計違反のシグナル**（U5-NFR-04）。
