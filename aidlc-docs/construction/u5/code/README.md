# U5 Code — 出題停止（item retirement）

**背景**: **著作権上の配慮**で投入済み作品の一部を今後出題しない必要が発生。
**確定要件**: **物理削除は不要 / それまでの判定結果は有効のまま / 進行中セッションへの反映は不要（新規セッションのみ）**。
**結果**: 論理削除（`items.retired_at`）で実現。**U3/U4b は無変更**・**`EXPORT_FORMAT_VERSION` は 1.0.0 据え置き**＝要件「それまでの結果は有効」を**無改修で**満たす。

---

## 構成（LC-U5 との対応）

| ファイル | LC | 役割 |
|---|---|---|
| `migrations/0004_item_retire.sql` | LC-U5-07 | `items.retired_at` / `sessions.likert_targets`（NULL 許容 ×2・**安全な no-op 移行**） |
| `src/backend/repo/repository.py` | LC-U5-01/02/06 | **`list_active_items` 新設**（`list_items` は**凍結**）／`retire_items`・`unretire_items`／`Session` 保存経路の拡張 |
| `src/backend/participant/session.py` | LC-U5-03 | **`get_likert_targets`（単一アクセサ）**／新規セッションで `list_active_items` |
| `src/backend/admin/api.py` | LC-U5-04 | `POST /admin/items/retire`・`/unretire`／充足判定を active 母数に |
| `scripts/pool_retire.py` | LC-U5-05 | CLI（U4a と同型・**非デプロイ**） |
| `src/schema/payloads.py` | — | `ItemRetireRequest` / `RetireResult`（**`Item` は不変**） |

---

## 使い方

```bash
export ADMIN_API_BASE=https://<host>
export ADMIN_BASIC_USER=... ADMIN_BASIC_PASSWORD=...

# 出題停止（論理削除・物理削除ではない）
uv run python -m scripts.pool_retire i001 i002

# 復活（誤操作の回復）
uv run python -m scripts.pool_retire i001 --unretire
```

**反映範囲**:

| 対象 | 廃止後の挙動 |
|---|---|
| **新規セッション** | 廃止 item は**ペア列・練習・Likert のいずれにも出ない** |
| **進行中セッション** | **そのまま出題され続ける**（ペア列は開始時に確定済み・完了 or 非アクティブ 48h まで）。要件で受容済み |
| **エクスポート / BT 集計** | **従来どおり**（廃止 item も `items` に残る・過去の判定は有効） |
| **充足判定 / token_issue** | 母数から除かれる。割ったら**発行拒否**＝補充を促す |

**終了コード**: 正常（`already_retired`・`not_found` を含む）= **0**、認証/通信/入力不正 = 非 0。`not_found` は「既に存在しない＝目的は達成」ゆえ失敗にしないが **stderr に警告**。

---

## 設計上の不変条件（テストで検出しにくい仕様の明文化）

### 1. 🔒 読み取り経路の分割 —「関数名」で強制（BR-U5-02 / DP-U5-01）

**判別の原理**: **「これから出題するものを選ぶ」なら active / 「既に起きたこと・既に配ったものを解決する」なら全件。**

| 呼ぶもの | 呼び出し元 |
|---|---|
| **`list_active_items()`** | 新規セッションのペア生成・Likert 選定／充足判定（ingest の warn / issue のゲート） |
| **`list_items()`（凍結・全件）** | `build_view` の `bodies` 写像／`get_likert_targets` の旧セッション導出 |
| **SQL 直参照（全件）** | `read_export_rows("items")`／winrate 集計 |

**❌ 禁止**: `list_items()` に active フィルタを足すこと（`active_only` 引数の新設を含む）。踏むと**要件の両輪が同時に壊れる**:

- **「結果は有効」** → export の `items` が縮む → 自己完結性が破れる → **PU3-3 違反 → U4b 破壊**
- **「新規のみ反映」** → 旧セッションのフォールバック導出が変わる → 進行中セッションが壊れる

**引数フラグを採らない理由**: 既定値の反転・呼び出し漏れという**ありふれた変更**で両輪が壊れる。関数名で分ければ、劣化経路は「**凍結された関数を書き換える**」明白な違反にしか到達できない。

### 2. 🔴 Likert ターゲットは単一アクセサに集約（BR-U5-04 / DP-U5-02）

`select_likert_targets` の導出は**3 箇所に散在していた**（`build_view`=表示 / `check_complete`=完了判定 / `submit_likert`=検証）。**一部だけ保存値に切り替えると「表示されたターゲットを送信すると拒否される」**（表示=保存値・検証=導出値のずれ）。→ **3 箇所すべてを `get_likert_targets` 経由**に統一。

**原子性**: `likert_targets` は `save_pair_sequence` の**同一 batch**で保存する。同関数は既に Session + PairSequence を all-or-nothing 保存する設計ゆえ、**「ペア列は保存されたが Likert 未保存」の中間状態が原理的に生じない**。別経路にするとその窓を新設してしまう。

### 3. `[]` と `None` は意味が違う（PBT-02 が検出）

| 値 | 意味 | 挙動 |
|---|---|---|
| `[]` | **Likert 対象なしが確定済み** | フォールバック**しない**（空のまま） |
| `None` | **U5 以前の旧セッション**（未保存） | **全件から導出**にフォールバック |

`[]` を `None` に潰すと**本来ないはずの Likert 対象が生える**。`get_session` は truthy 判定ではなく **`is not None`** で厳密に分ける。

### 4. 凍結ガードとの関係（BR-U5-05 / DP-U5-04）

**廃止は凍結ガード（BR-U4a-03）の対象外**。`retired_at` は `body`/`layer` を変えず**過去判定の解釈を壊さない**ためガードの趣旨に反しない。**参照済み item でも廃止できる**（実 D1 で確証済み）が、**`body`/`layer` の UPDATE は引き続き拒否**。
**型で穴を塞ぐ**: `Item` に `retired_at` を持たせない＝`pool_ingest` の経路から廃止・復活が**構造的に不可能**。

### 5. `retired_at` = 現在状態 / `admin_log` = 履歴の正（BR-U5-13）

`unretire` は `NULL` に戻すため、**廃止→復活→再廃止の履歴はカラム単体に残らない**（最後の廃止時刻のみ）。**履歴の正は `admin_log`**（`item_retire` / `item_unretire` の時系列・`wrangler tail`）。

---

## テスト（PU5・責務の境界）

**責務の境界**: SQL の意味論は**ダブルで再現してもダブルを検証することにしかならない**ため、**実 D1 の integration が正**。

| 検証 | 場所 | 理由 |
|---|---|---|
| **PU5-1**（新規セッションから消える） | PBT | ワイヤリング（`start_or_resume` が `list_active_items` を使うか） |
| **PU5-2**（旧セッション不変・**「新規のみ反映」の網**） | PBT | フォールバックの導出元が全件か |
| **PBT-02**（`likert_targets` ラウンドトリップ・順序保存） | PBT | モデル + JSON の純粋な往復 |
| **PU5-3**（retire 冪等・初回時刻保持） | **integration（実 D1）** | `AND retired_at IS NULL` という **SQL の意味論** |
| **PU5-4**（export が縮まない・**BR-U5-02 の検出網**） | **integration（実 D1）** | `read_export_rows` の **SQL の意味論** |
| 凍結ガード非適用／再投入で不変／充足割れ拒否／401 | **integration（実 D1）** | 同上 |

- **ジェネレータは廃止済み/現役の混在プールを生成**（U5-NFR-06。「廃止ゼロ件だけを引くジェネレータでは反例探索が空回りする」＝U4b の教訓）。
- **in-memory ダブル**（`tests/fakes.py`）は**ワイヤリング検証専用**。SQL の意味論は検証しない。

### 実行結果（2026-07-17）

- **unit + PBT: 76 緑**（既存 61 + U5 15・U1/U2/U3/U4a/U4b 回帰含む・ci profile）
- **integration（実 D1 / miniflare・migration 0004 適用後）: 37/37 PASS**
  - **U5: 13/13**（`result-u5-integration.json`）
  - 回帰: U2 9/9・U3 8/8・U4a 7/7

### ★ 回帰の意味づけ

**PU3-3（export 自己完結性）が緑 = BR-U5-02 の禁止事項を踏んでいない証拠**。
**U3/U4b のテストは無改修で緑**＝export 形式が変わっていない証拠。**U5 のためにそれらを書き換えたら設計違反のシグナル**（U5-NFR-04）。

## 変更していないもの（確認済み）
`wrangler.toml` / `.github/workflows/deploy.yml` / `frontend/` / `Item` / `ExportItem` / `EXPORT_FORMAT_VERSION`（**1.0.0**）/ `schema/bt.py` / `scripts/bt_aggregate/` / U3・U4b のコードとテスト。
