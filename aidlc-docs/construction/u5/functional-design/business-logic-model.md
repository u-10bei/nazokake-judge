# U5 Business Logic Model — 出題停止（item retirement）

**目的**: 論理削除（`retired_at`）で「新規セッションから出題されない」状態を作る。**過去の判定・BT 集計は不変**。
**設計の骨格**: 本設計は「**active のみを読む経路**」と「**全件を読む経路**」の**二本立てで初めて成立する**。この二本立てを**関数の分割**で構造的に固定する（BR-U5-02）。

---

## 1. 読み取り経路の二本立て（★設計の中心）

```
                      ┌──────────────────────────────────────┐
                      │            items（D1）               │
                      │  item_id / layer / body / body_ref   │
                      │  + retired_at  (NULL=現役)           │
                      └───────┬──────────────────┬───────────┘
                              │                  │
        🆕 list_active_items()│                  │🔒 list_items()（全件・不変）
           WHERE retired_at   │                  │   + SQL 直参照
             IS NULL          │                  │
                              ▼                  ▼
        ┌─────────────────────────────┐   ┌──────────────────────────────────┐
        │ ① 新規セッションのペア生成   │   │ ④ build_view の bodies 写像       │
        │   generate_pairs            │   │   （進行中の既存ペア列を解決）    │
        │   ※練習ペアも同一呼び出し   │   │ ⑤ 旧セッションの Likert 導出      │
        │ ② 新規セッションの Likert   │   │   フォールバック                  │
        │   ターゲット選定            │   │ ⑥ export の items（自己完結性）   │
        │ ③ 充足判定（ingest/issue）  │   │ ⑦ U3 winrate 集計（過去の事実）   │
        └─────────────────────────────┘   └──────────────────────────────────┘
              「これから出題するもの」            「既に起きたこと・既に配ったもの」
```

**判別の原理**: **「これから出題するものを選ぶ」なら active / 「既に起きたこと・既に配ったものを解決する」なら全件。**

### ❌ 禁止する実装（Code Gen の劣化経路）

**`list_items()` 自体に active フィルタを足してはならない**（引数 `active_only=True` の既定値化を含む）。要件の両輪が**同時に**壊れる:

| 壊れるもの | 機序 |
|---|---|
| **「それまでの結果は有効」** | export の `items` が縮む → 自己完結性（judgments の item ⊆ items）が破れる → **PU3-3 違反 → U4b 破壊**（judgments には出るが items にない item を assemble が黙って落とす） |
| **「新規のみ反映」** | 旧セッションのフォールバック導出が変わる → **進行中セッションの Likert ターゲットが変わる** |

→ **`list_items()` は全件のまま凍結、`list_active_items()` を新設**（BR-U5-02）。

---

## 2. 廃止フロー（BR-U5-06/11）

```
研究者 ──[著作権上の配慮で作品 X を出題停止したい]──▶ scripts/pool_retire.py X
                                                          │ Basic 認証
                                                          ▼
                                          POST /admin/items/retire {item_ids:[X]}
                                                          │
                          ┌───────────────────────────────┴───────────────────┐
                          │ AuthGuard（既存・単一チョークポイント）           │
                          └───────────────────────────────┬───────────────────┘
                                                          ▼
                              UPDATE items SET retired_at = <now>
                              WHERE item_id IN (…) AND retired_at IS NULL   ← 冪等（初回時刻を保持）
                                                          │
                          ┌───────────────────────────────┴───────────────────┐
                          │ admin_log("item_retire", item_ids=[…], count=n)   │ ← 履歴の正（BR-U5-13）
                          └───────────────────────────────┬───────────────────┘
                                                          ▼
                          {ok, retired: n, already_retired: […], not_found: […]}
```

**凍結ガードを通らない**（BR-U5-05）: `insert_items` の参照済みガードは**この経路を通らない別関数**。`body`/`layer` を変えないため、参照済み item でも許可される。逆に `pool_ingest` からは `retired_at` に触れない（`Item` 契約に無いため＝BR-U5-12 で型が担保）。

**復活**: `POST /admin/items/unretire` → `SET retired_at = NULL`（対称・冪等, BR-U5-07）。

---

## 3. 廃止後の各経路のふるまい

| 主体 | 廃止前 | 廃止後 |
|---|---|---|
| **新規セッションの参加者** | X が出題されうる | **X は出題されない**（ペア・練習・Likert すべて, BR-U5-02a/02b） |
| **進行中セッションの参加者** | X が出題されうる | **X は出題され続ける**（既存ペア列は保存済み・要件で受容, BR-U5-03）。露出停止は完了 or 非アクティブ 48h まで |
| **U5 以前からの進行中セッション** | — | Likert は**全 items から導出にフォールバック**＝従来と同一（BR-U5-04） |
| **充足判定 / token_issue** | X を母数に含む | **X を母数から除く**。割ったら**発行拒否**＝補充を促す（BR-U5-09） |
| **エクスポート** | X を `items` に出力 | **X を `items` に出力し続ける**（`retired_at` は出さない, BR-U5-10） |
| **U3 winrate** | X の集計を表示 | **変わらず表示**（過去判定の事実） |
| **U4b BT 集計** | X を推定対象に含む | **変わらず含む**（無改修＝「それまでの結果は有効」） |

---

## 4. Likert ターゲットの保存化（BR-U5-04）

### 問題（既存設計の歪み）

| 状態 | 現状 | 安定性 |
|---|---|---|
| ペア列 | セッション開始時に**保存**（`save_pair_sequence`） | ✅ プールが変わっても不変 |
| Likert ターゲット | **毎回プールから導出**（`select_likert_targets(pool, seed, params)`） | ❌ **プールが変わると変わる** |

この非対称が原因で、プールを絞ると進行中セッションの Likert が変わる。

### 解決: ペア列と同じ「開始時確定」原則に揃える

```
新規セッション開始:
  pool_active = list_active_items()
  pairs   = generate_pairs(pool_active, exposure, seed, params)     → 保存（既存）
  targets = select_likert_targets(pool_active, seed, params)        → 🆕 保存（sessions.likert_targets）

読み取り（単一アクセサに集約・必須）:
  get_likert_targets(repo, token, params):
      stored = sessions.likert_targets
      if stored is not None: return stored                          ← U5 以降のセッション
      return select_likert_targets(list_items(), seed, params)      ← 旧セッション（全件・従来挙動を再現）
```

### 単一アクセサへの集約が必須である理由

現在 `select_likert_targets` の導出は **3 箇所に散在**する:

| 箇所 | 用途 |
|---|---|
| `build_view`（session.py:70） | 画面に**表示する**ターゲット |
| `check_complete`（session.py:126） | 完了判定 |
| `submit_likert`（survey.py:23） | `target_ref` の**検証** |

**一部だけ保存値に切り替えると壊れる**: 表示=保存値・検証=導出値のずれが生じ、**参加者に表示されたターゲットを送信すると「Likert 対象外」で拒否される**（BR-U2-18 のエラー）。→ **3 箇所すべてを `get_likert_targets` 経由に統一**する。

---

## 5. 波及範囲

| ユニット | 変更 |
|---|---|
| **migration 0004** | `items.retired_at` 追加 / `sessions.likert_targets` 追加（いずれも NULL 許容＝ALTER で足せる・テーブル再構築不要） |
| **U1（共有基盤）** | `list_active_items()` 新設（`list_items()` は凍結）。`pool_sufficiency` の呼び出し母数を active に |
| **U4a（管理）** | `POST /admin/items/retire` / `/unretire` 追加・`scripts/pool_retire.py` 新設・`admin_log` イベント 2 種。**凍結ガードは無改修** |
| **U2（参加者）** | 新規セッションで `list_active_items()` 使用 + Likert ターゲット保存。**`get_likert_targets` 単一アクセサに 3 箇所を集約** |
| **U3（管理・研究者）** | **無変更**（export は全件のまま・`retired_at` 非出力）。回帰確認のみ |
| **U4b（BT 集計）** | **無変更**（要件「それまでの結果は有効」を無改修で満たす） |
| **`Item` 契約 / `EXPORT_FORMAT_VERSION`** | **不変**（1.0.0 据え置き, BR-U5-10/12） |

---

## 6. 受入基準（Given-When-Then）

- Given 参照済み（判定実績あり）の item X、When `pool_retire X`、Then **成功**し `retired_at` が設定される（凍結ガードに阻まれない, BR-U5-05）。
- Given X が廃止済み、When 新規トークンでセッション開始、Then **ペア列・練習・Likert のいずれにも X が現れない**（BR-U5-02a/02b）。
- Given X を含むペア列を持つ**進行中**セッション、When 廃止後に再開、Then **従来どおり X が出題され**、画面は壊れない（BR-U5-03・`bodies` は全件）。
- Given U5 以前に開始した進行中セッション（`likert_targets IS NULL`）、When 廃止後に再開、Then **Likert ターゲットが変わらない**（全件導出フォールバック, BR-U5-04）。
- Given X が廃止済みで過去に judgments がある、When エクスポート → BT 集計、Then **X は `items` に含まれ・BTResult にも従来どおり現れる**（BR-U5-10・U4b 無改修）。
- Given 廃止により active が充足条件を割った、When `token_issue`、Then **発行拒否**＋不足内訳（BR-U5-09）。
- Given X が既に廃止済み、When 再度 `pool_retire X`、Then **no-op**・`already_retired` に列挙・**初回の廃止時刻が保持**される（BR-U5-06）。
- Given X が廃止済み、When `pool_ingest` で X を再投入、Then `body`/`layer` は更新されるが **`retired_at` は廃止のまま**（BR-U5-08）。
- Given X が廃止済み、When `pool_retire --unretire X`、Then `retired_at=NULL` に戻り新規セッションで再び出題されうる（BR-U5-07）。
