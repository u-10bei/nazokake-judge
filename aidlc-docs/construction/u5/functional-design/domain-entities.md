# U5 Domain Entities — 出題停止（item retirement）

**ユニット**: U5。既存エンティティへの**列追加 2 本のみ**（migration 0004）。**新規テーブルなし・型契約の変更なし**。
**方針**: 廃止状態は **D1 の列と専用 API だけ**が扱う。`Item`（投入契約）・`ExportItem`（エクスポート契約）・`EXPORT_FORMAT_VERSION` は**すべて不変**（BR-U5-10/12）。

---

## 1. スキーマ差分（migration 0004）

```sql
-- U5: 出題停止（item retirement）。著作権配慮で「今後出題しない」を論理削除で表す。
-- 物理削除しない: pairs.item_left/item_right は REFERENCES items(item_id) の FK を持ち、
-- かつ ExportBundle の自己完結性（BR-U3-07）に items 全件が必要（BR-U5-01）。
-- NULL 許容の列追加ゆえ ALTER で足せる（0002 のようなテーブル再構築は不要）。
-- 適用は「migration → deploy」の順（Infra §4）。

ALTER TABLE items ADD COLUMN retired_at TEXT;        -- NULL=現役 / ISO8601=廃止時刻

-- U5: Likert ターゲットをセッション開始時に確定・保存（ペア列と同じ「開始時確定」原則）。
-- 既存セッションは NULL のまま → 全 items から導出にフォールバック（後方互換・
-- 進行中セッションを壊さない, BR-U5-04）。
ALTER TABLE sessions ADD COLUMN likert_targets TEXT;  -- JSON 配列 / NULL=未保存（U5 以前のセッション）
```

**インデックス不要**: プール規模は約 95 件（既定運用）。`WHERE retired_at IS NULL` の全走査で十分。

### 差分後のテーブル

| テーブル | 列 | U5 差分 |
|---|---|---|
| **items** | `item_id` (PK) / `layer` / `body` / `body_ref` / **`retired_at`** | **`retired_at` 追加**（NULL 既定＝**既存行はすべて現役**・データ移送不要） |
| **sessions** | `token` (PK) / `phase` / `seed` / `exposure_snapshot` / `created_at` / **`likert_targets`** | **`likert_targets` 追加**（NULL 既定＝**既存セッションはフォールバック**） |
| pairs / judgments / likert_responses / tokens | — | **変更なし**（過去データは一切触らない） |

---

## 2. 型契約（`src/schema/`）

### 不変（★重要）

| 型 | 状態 | 理由 |
|---|---|---|
| **`Item`** | **変更なし**（`retired_at` を**持たせない**） | 投入経路から廃止・復活を**構造的に不可能**にする（BR-U5-12）。`pool_ingest` のペイロードに `retired_at` が現れない＝ガードの穴を作らない。フィルタは SQL 側で効かせる |
| **`ExportItem`** | **変更なし**（`item_id` + `layer`） | `retired_at` を出さない＝**`EXPORT_FORMAT_VERSION` 版上げ不要**（BR-U5-10）→ **U3/U4b 無変更** |
| **`EXPORT_FORMAT_VERSION`** | **1.0.0 据え置き** | 形式変更なし（BR-U3-07 の版上げ条件に該当しない） |
| `Session` | **変更なし**（`likert_targets` はモデルに載せない・Repository が JSON を直接読み書き） | セッション状態の型契約を広げない。ラウンドトリップ（XC-02）の対象も現状維持 |

> **設計判断**: `likert_targets` を `Session` モデルに載せるかは NFR Design（LC 設計）で決める。FD としては「**保存する**」ことのみを固定し、型の置き場は後段に委ねる。

### 新規（U4a 管理ペイロード）

```
ItemRetireRequest = { item_ids: list[str] }              # retire / unretire で共用
RetireResult      = {
  ok: bool,
  retired: int,                  # 今回 retired_at を設定/解除した件数
  already_retired: list[str],    # 既に廃止済み（no-op, BR-U5-06）※unretire では already_active
  not_found: list[str],          # items に存在しない item_id
}
```

- 置き場は `src/schema/payloads.py`（U4a の `ItemIngestRequest`/`IngestResult` と同居）が自然。**最終確定は NFR Design**。
- **`retired_at` の値そのものは API 応答に含めない**（件数と分類のみ）。状態は D1、履歴は `admin_log`（BR-U5-13）。

---

## 3. `retired_at` の意味論

| 値 | 意味 |
|---|---|
| `NULL` | **現役**。新規セッションで出題されうる |
| ISO8601 文字列 | **廃止済み**。新規セッションで出題されない。値は**初回の廃止時刻**（再廃止で上書きしない, BR-U5-06） |

- **現在状態を表す単一の値**であり、**履歴ではない**。復活（`NULL` へ戻す）で前回の廃止時刻は失われる。
- **履歴の正は `admin_log`**（`item_retire` / `item_unretire` の時系列, BR-U5-13）。役割分担: **`retired_at`=現在状態 / `admin_log`=履歴**。

---

## 4. データフロー（廃止 item の一生）

```
pool_ingest                    pool_retire                  新規セッション        エクスポート/BT
    │                              │                              │                    │
    ▼                              ▼                              ▼                    ▼
items 行作成               retired_at = <now>          list_active_items()     read_export_rows("items")
retired_at = NULL          （body/layer は不変）        → X は選ばれない         → X を含む（全件）
    │                              │                              │                    │
    │                              │                       進行中セッション            ▼
    │                              │                       → 既存ペア列のまま      BTResult に X が出る
    │                              │                          X が出題され続ける    （過去判定は有効）
    │                              │                          （BR-U5-03・受容済み）
    ▼                              ▼
再投入しても                 admin_log に記録
retired_at は不変            （履歴の正）
（BR-U5-08）
```

**不変条件**: 廃止は `items.retired_at` にしか触れない。**`pairs` / `judgments` / `likert_responses` は一切変更されない**＝「それまでの判定結果は有効のまま」がデータ構造で保証される。

---

## 5. 後続への申し送り（NFR Requirements / NFR Design / Code Generation）

- **NFR Requirements〈U5〉**: 冪等性（BR-U5-06/07）・後方互換（`likert_targets IS NULL` フォールバック）・監査ログの必須性・**PBT の対象**（廃止後の新規セッションに X が現れない不変条件 / 旧セッションの Likert 不変）。
- **NFR Design〈U5〉**: `list_items()` 凍結 + `list_active_items()` 新設を **LC レベルで固定**（BR-U5-02 の構造的担保）。`get_likert_targets` 単一アクセサの LC 化（3 箇所集約）。`likert_targets` の型の置き場（`Session` に載せるか Repository 内に留めるか）。
- **Code Generation〈U5〉**: migration 0004・`list_active_items()`・`get_likert_targets`・retire/unretire API + CLI・回帰（**U3 export の自己完結性 PU3-3 が緑のままであること＝BR-U5-02 の禁止事項を踏んでいない証拠**）。
