# U6 Domain Entities — 層拡張 + 事前生成割当

**方針**: 既存エンティティへの**層値追加**と、**割当プランの新規エンティティ**。`ExportBundle` 契約は**不変**（`EXPORT_FORMAT_VERSION` 1.0.0 据え置き）。

---

## 1. スキーマ差分（migration 0005）

### 1-1. `items.layer` の CHECK 制約更新（**テーブル再構築が必要**）

**SQLite は CHECK 制約を ALTER できない**ため、**0002 と同型のテーブル再構築**を行う（当初の「データ投入だけで済む」見立ては誤り）。

```sql
-- U6: layer に 'anchor'（下帯アンカー）と 'practice'（練習専用）を追加。
CREATE TABLE items_new (
  item_id    TEXT PRIMARY KEY,
  layer      TEXT NOT NULL
               CHECK (layer IN ('pro','ai','edit','rule','anchor','practice')),
  body       TEXT NOT NULL,
  body_ref   TEXT,
  retired_at TEXT                       -- U5（0004）から引き継ぐ
);
INSERT INTO items_new SELECT item_id, layer, body, body_ref, retired_at FROM items;
DROP TABLE items;
ALTER TABLE items_new RENAME TO items;
```

> ⚠️ **`retired_at`（0004）の引き継ぎを忘れないこと**。再構築時の列欠落は U5 の廃止状態を消失させる。

### 1-2. 割当プラン（新規テーブル）

```sql
-- U6: 事前生成した固定プラン。plan_set で成立版/フォールバック版をキーする。
CREATE TABLE IF NOT EXISTS assignment_plan (
  plan_set    TEXT NOT NULL,            -- 'primary' | 'fallback' 等（BR-U6-12）
  plan_index  INTEGER NOT NULL,         -- 0..E-1（スロット = 評価者枠）
  idx         INTEGER NOT NULL,         -- スロット内の提示順
  item_left   TEXT NOT NULL REFERENCES items(item_id),
  item_right  TEXT NOT NULL REFERENCES items(item_id),
  is_practice INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (plan_set, plan_index, idx)
);

-- 生成メタ（監査再現性: 同一 seed → 同一プラン, BR-U6-11）
CREATE TABLE IF NOT EXISTS assignment_plan_meta (
  plan_set     TEXT PRIMARY KEY,
  seed         INTEGER NOT NULL,
  n_items      INTEGER NOT NULL,
  n_slots      INTEGER NOT NULL,        -- E
  n_pairs      INTEGER NOT NULL,        -- J（本番のみ）
  m_per_item   INTEGER NOT NULL,        -- 12
  generated_at TEXT NOT NULL,
  is_active    INTEGER NOT NULL DEFAULT 0   -- activate は 1 セットのみ（BR-U6-12）
);
```

### 1-3. `tokens` にスロット紐付け

```sql
-- U6: 発行時にスロットを割り当てる（BR-U6-15 の補充トークンも同一 plan_index を持つ）
ALTER TABLE tokens ADD COLUMN plan_index INTEGER;   -- NULL 許容（U6 以前のトークン）
```

**NULL 許容ゆえテーブル再構築は不要**。NULL = U6 以前に発行されたトークン → **従来どおりオンライン生成にフォールバック**（後方互換）。

---

## 2. 型契約

### 2-1. 変更あり

| 型 | 変更 |
|---|---|
| **`Layer`（enum）** | **`ANCHOR = "anchor"` / `PRACTICE = "practice"` を追加**（BR-U6-01/04） |
| **`POOL_LAYERS`（新規定数）** | `(PRO, AI, EDIT, RULE, ANCHOR)` — **充足判定が走査する本番層の明示リスト**。`PRACTICE` を含めない（BR-U6-05）。**`for layer in Layer` の enum 走査を置換** |
| **`AssignmentParams.likert_fixed_targets`** | **値の変更のみ**（10 件全指名）。**型・実装は不変**（BR-U6-06） |

### 2-2. 🔒 不変（★重要）

| 型 | 理由 |
|---|---|
| **`ExportItem` / `WinrateRow` / `BTItemScore`** | `layer: str` で**値域を列挙していない**ため、新層値が**そのまま流れる**（U3 winrate は `GROUP BY i.item_id, i.layer` ゆえ 1 行増えるだけ・U4b は layer 非依存） |
| **`EXPORT_FORMAT_VERSION`** | **1.0.0 据え置き**。形式は変わらない → **U3/U4b は無変更** |
| **`Item`** | `layer: Layer` の enum 拡張で自動対応。**`retired_at` は持たせない**（U5 BR-U5-12 を維持） |
| **`Session`** | `likert_targets` の保存（U5）は不変。**同一 batch 原子保存も不変** |

### 2-3. 新規（`src/schema/`）

```
AssignmentPlanRow = { plan_set, plan_index, idx, item_left, item_right, is_practice }
AssignmentPlanMeta = { plan_set, seed, n_items, n_slots, n_pairs, m_per_item, generated_at, is_active }
PlanVerification   = { ok, exposure_gap, n_components, max_k, cross_layer_ratio, duplicate_pairs, errors[] }
```

`PlanVerification` は **BR-U6-10 の①〜⑤の検証結果**を表し、**投入前の検査**（CLI）と PBT の双方で使う。

---

## 3. 層値の意味論

| 値 | 意味 | `POOL_LAYERS` | 層順序予測 | 備考 |
|---|---|:---:|:---:|---|
| `pro` | プロ作品層 | ✅ | ✅ | S04・S10・N 群。**バーは指名アンカーの β 位置**（層平均ではない, BR-U6-03） |
| `ai` | AI 生成層 | ✅ | ✅ | |
| `edit` | 編集・自作層 | ✅ | ✅ | プロ超え候補 + 中位対照 |
| `rule` | ルールベース生成層 | ✅ | ✅ | **陰性対照**（β 最下帯に団子の事前予測） |
| **`anchor`** | **下帯アンカー**（役割層） | ✅ | ❌ | S03・S13。**役割ベース命名**（出自では `pro` の S04・S10 と区別できないため, BR-U6-01/02） |
| **`practice`** | **練習専用**（分析的に不活性） | ❌ | ❌ | 開示セット。**充足の母数外**・`is_practice=1` で出力段除外（BR-U6-04/05） |

---

## 4. データフロー

```
【設計時】plan_generate（CLI・オフライン）
   items（active ∩ POOL_LAYERS = 38 件）+ 開示セット（practice）
        │ 12-正則グラフ構成 → 8 スロット分割 → 練習ペア固定記載
        │ 検証（PlanVerification: gap=0 / 成分1 / k≤3 / 同一ペア0 / 層間≥0.65）
        ▼
   assignment_plan（primary / fallback の 2 セット）+ assignment_plan_meta

【発行時】token_issue 8
        ▼
   tokens.plan_index = 0..7

【実行時】start_or_resume（割当ロジックなし）
   tokens.plan_index → assignment_plan（is_active なセット）→ ペア列
        │ Likert = likert_fixed_targets（固定 10 件）
        ▼
   save_pair_sequence（Session + PairSequence + likert_targets を同一 batch・U5 から不変）

【分析】export → bt_aggregate
   出現回数は token + pair_index から導出（スキーマ追加なし, BR-U6-19）
```

**過去データへの影響なし**: `pairs` / `judgments` / `likert_responses` の構造は変更しない。`assignment_plan` は**設計の記録**であり、確定したペア列は従来どおり `pairs` に入る。

---

## 5. 後続への申し送り（NFR Requirements / NFR Design / Code Generation）

- **NFR Requirements〈U6〉**: プラン検証の PBT 化（BR-U6-10 の①〜⑤）・migration 0005 の**`retired_at` 引き継ぎ検証**（再構築で U5 の状態を失わないこと）・後方互換（`plan_index IS NULL` のフォールバック）・**U3/U4b 無変更の保証手段**（既存テストを無改修で緑＝形式不変の証拠、U5-NFR-04 と同型）。
- **NFR Design〈U6〉**: `POOL_LAYERS` の配置（`schema` か `domain` か）・プラン引き当ての LC・**`generate_pairs` を残しつつ参加者フローから切り離す構造**（BR-U6-17）。
- **Code Generation〈U6〉**: migration 0005（**`retired_at` の列引き継ぎを Step に一行固定**）・`Layer` 拡張・`POOL_LAYERS` 置換（**`for layer in Layer` の走査を残さない**）・`scripts/plan_generate.py`・`start_or_resume` の置換（`session.py:53`）・`token_issue` の `plan_index` 割当。
- **NFR Design 以降の決定点**:
  1. **`anchor` を `POOL_LAYERS` の非空要求に含めるか**（含めるとドライラン等で `anchor` 不在時にゲートが落ちる）
  2. **脱落時の引き継ぎ粒度**（未消化分のみ再開 / スロット全体やり直し, BR-U6-15）
  3. **`plan_index` をエクスポートに含めるか**（含めると版上げが必要。**token の別で評価者は識別できる**ため既定は含めない）
