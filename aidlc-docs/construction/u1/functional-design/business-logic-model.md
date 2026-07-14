# U1 Business Logic Model — 共有基盤

技術非依存の業務ロジック。中核は AssignmentEngine（XC-01）、露出カウント導出（H-2）、セッション状態シリアライズ（XC-02）。

---

## 1. AssignmentEngine（XC-01・純粋関数）

### シグネチャ
```
generate_pairs(pool: list[Item],
               exposure: ExposureCounts,
               seed: int,
               params: AssignmentParams) -> list[Pair]

updated_exposure(exposure: ExposureCounts, pairs: list[Pair]) -> ExposureCounts   # PBT モデル用
```
- `AssignmentParams`: `session_pairs`(本番ペア数), `practice_pairs`, `cross_layer_min_ratio`, `max_item_occurrence_k`。
- **純粋関数**: 同一 `(pool, exposure, seed, params)` → 同一出力（決定論）。副作用なし（DB I/O は SessionService）。

### アルゴリズム方針（Q1=A: 重み付きランダム抽選）
1. 決定論的乱数を `seed` で初期化。
2. 目標本番ペア数に達するまで、以下でペアを構成:
   - 各 `Item` に**露出の少なさに応じた重み**を与える（重み関数は下記）。
   - 重みに比例して 1 つ目の作品を抽選 → 制約（BR-01 同一ペア禁止・a≠b、BR-02 同一項目上限 k、層間比率誘導）を満たすよう 2 つ目を抽選。
   - **位置決定（追加規則 2）**: 選ばれた 2 作品のどちらを `item_left`(A) にするか一様ランダムに決め記録。
3. 練習ペアを別途構成（集計対象外、`is_practice=true`）。
4. 生成後、`index` を付与して順序確定。

**重み関数（較正確定 2026-07-13）**: 露出回数 `e`（有効露出＝累積露出＋セッション内出現）に対し **`w = 1/(e+1)³`**（指数 p=3）。当初 p=1（`1/(e+1)`）は本番規模 95 件・S=30 で露出偏りが過大（必要 α≈0.713）だったため p=3 に強化。貪欲法を避ける理由（比較グラフの連結性・混合性を保ち BT 推定を安定させる）は p=3 でも維持され、**連結成分は常に 1・平均ユニーク相手数 ~22 と不変**（副作用なしを確認）。詳細は `business-rules.md` 較正確定節、実装 `backend/domain/assignment.py`。

### 層間比率の扱い（Q2=A）
- `cross_layer_min_ratio`（暫定下限 **0.65**）を**下限保証**として誘導。4 層からの一様抽選では自然に約 75% が層間ペアになるため、本制約は下限割れの防止として働く。
- 2 つ目の作品抽選時に、層間比率が下限を下回りそうなら層の異なる候補を優先する誘導を入れる（詳細は実装）。

---

## 2. 露出カウント導出（H-2 / Q5=A / Q7=A）

```
derive_exposure(all_sessions) -> ExposureCounts
```
- **導出方式**: 保持テーブルを持たず、**全確定 PairSequence**（completed + アクティブな in_progress）から `item_id` 出現回数を集計。
- **非アクティブ除外（BR-04）**: `last_active_at` が閾値より古い in_progress セッションのペア列は集計から除外（離脱データの空カウント滞留を防止）。
- Q7=A（全確定回答横断）は本導出により自動的に実現 = XC-01 の**全体不変条件**。
- `updated_exposure` 純粋関数は本番では未使用でも **PBT のモデル（オラクル）**として保持し、`derive_exposure` と整合することを検証。

---

## 3. セッション状態シリアライズ（XC-02 / PBT-02）

- **ラウンドトリップ対象**: セッション再開に必要な状態 = 確定 PairSequence + 既 Judgment から導出される「次の未回答 index」。
- `serialize(state) -> bytes/json` / `deserialize(...) -> state` が論理的に等価（元 == 復元）であることを PBT-02 で検証。
- `seed`/`exposure_snapshot` は監査・完全リプレイ用の付随情報（H-3 の対象定義に沿い、ラウンドトリップ必須対象には含めない）。

---

## 4. リプレイ可能性（Q4=B）

- セッション開始時: `seed` をサーバ生成し、`exposure_snapshot`（その時点の導出露出）と共に Session に保存。
- 監査時: `generate_pairs(pool, exposure_snapshot, seed, params)` を再実行すれば**保存済みペア列を完全再現**できる（PBT が本番で反例を発見した際の調査に直結）。

> **改訂注記（2026-07-14, U2 Code Generation Q1 由来）**: Q4=B の本質（**seed + exposure_snapshot を保存し完全リプレイ可能にする**）は維持したまま、**seed の生成方法のみ**を「サーバ乱数生成」から **「トークン由来の決定論シード」`seed = int(SHA-256(token) 先頭 8 バイト)`** に改訂する。理由: 監査の自己記述性向上（token から seed を再導出可能）・RNG 状態不要（Pyodide 制約回避）。RNG 品質は 128-bit ランダムトークンのハッシュゆえ問題なく、seed は参加者レスポンスに出さない（U2-NFR-06）ため漏洩経路なし。**`sessions.seed` への保存は従来どおり継続**（導出値と保存値の一致を監査で検証できる二重化）。黙示の上書きではなく本改訂として明示記録。詳細は `u2-code-generation-plan.md` Q1 / audit.md。

---

## 5. Testable Properties（XC-01→PBT-03, XC-02→PBT-02。PBT-01 は Partial では advisory だが重点箇所として明示）

| ID | プロパティ | カテゴリ | 対応 | 強制 |
|---|---|---|---|---|
| P-1 | 露出偏りが許容範囲内: 適格項目の露出回数で `max − min ≤ max(2, α × mean)` を **S セッション累積シミュレーション後**に評価（述語定義は下記） | 不変条件（統計的） | XC-01 | PBT-03 |
| P-2 | 層間ペア比率 ≥ `cross_layer_min_ratio` | 不変条件 | XC-01/FR-03 | PBT-03 |
| P-3 | セッション内: 同一ペアなし・`a≠b`・同一項目出現 ≤ k | 不変条件 | 追加規則1 | PBT-03 |
| P-4 | `serialize`→`deserialize` = 元の状態（ラウンドトリップ） | ラウンドトリップ | XC-02 | PBT-02 |
| P-5 | `updated_exposure(exposure, pairs)` == `derive_exposure` 相当（オラクル一致） | オラクル | H-2 | PBT-03（advisory 寄り） |
| P-6 | 決定論: 同一 `(pool,exposure,seed,params)` → 同一 `generate_pairs` 出力 | 不変条件 | Q4/監査 | PBT-08 と整合 |
| P-7 | 位置割当（item_left/right）が統計的に一様（カウンターバランス） | 分布 | 追加規則2 | 例示/統計テスト（PBT 補助） |

### P-1 露出偏り許容範囲の述語定義（PBT-03 のテスト述語）
- **対象**: 適格項目（非アクティブ除外後, BR-04）の露出回数の集合。
- **述語**: `max(exposure) − min(exposure) ≤ max(2, α × mean(exposure))`。
- **評価形**: 重み付きランダムは確率的なため、単一セッションのハード保証ではなく、**S セッションを逐次生成し各回で露出をフィードバックした後**に上記述語を評価する**統計的不変条件**とする（PBT では「S セッション累積シミュレーション → 述語評価」の形）。
- **定数の確定（2026-07-13 較正済み）**: **α=0.7 / S=30 / 重み指数 p=3**。本番規模プール（95 件）・20 試行の最悪 gap 評価で確定（p=3 の S=30 最悪 α≈0.475 に約 1.5 倍のマージン）。P-1 テストは**本番規模プールで評価**する（`tests/pbt/`）。**述語の形は本設計で固定**、定数は較正確定。詳細は `business-rules.md` 較正確定節。

- ジェネレータ（PBT-07）: `Item`（層ラベル付き）, `ExposureCounts`, `AssignmentParams` の**ドメインジェネレータ**を用意（プリミティブ直接使用禁止）。
- シード記録・縮小（PBT-08）: 反例時にシードと縮小入力を出力。`tests/pbt/` に配置し受入基準（P-1〜P-7）を name/docstring に明記。
