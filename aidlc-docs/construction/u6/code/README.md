# U6 Code — 層拡張（下帯アンカー）+ 事前生成割当

**背景**: 実データ確定（**n=38 / E=8 / J=228 / m=12**）。
**目的**: **割当を実行時から設計時へ移す**。実行時から抽選ロジックを除去し、**事前生成・検査済みの固定プランの引き当て**にする。
**効果**: 露出 gap が **0.45〜0.75 → 0**、**較正（p=3・α=0.7・S=30、n=95 由来）が不要**になる。

---

## 構成

### 設計時（`scripts/plan_generate/` — 非デプロイ・追加依存なし）

| ファイル | LC | 役割 |
|---|---|---|
| `constraints.py` | LC-01 | **三つ組**（プール・期待組成・制約ファイル）の読込と整合検証 |
| `placement.py` | LC-02 | **制約付き円周配置探索**（辞書式目的関数） |
| `graph_build.py` | LC-03 | m-正則巡回グラフ（**gap=0・全体連結・同一ペア0 を構成で保証**） |
| `partition.py` | LC-04 | E スロット分割（k 制約）+ **ブロック連結の実行可能性検査** |
| `sequencing.py` | LC-05 | スロット内順序付け（隣接回避）+ **練習を先頭に固定** |
| `verify.py` | LC-06 | BR-U6-10 ①〜⑥ + PU6-8 + Likert の検証（**投入前ゲート**） |
| `__main__.py` | LC-07 | CLI（構成 → 検証 → **seed 再試行** → 明示失敗） |

`scripts/plan_ingest.py` が**投入側の CLI**（生成と投入で 2 本＝Code Gen Q1=A）。分離の理由は
**両者の間に `git commit` が挟まる**こと（BR-U6-12）——1 コマンドだと**コミット前のプランを
投入できてしまい**、「コミットされたものが投入された」という証跡が成立しない。

### 実行時（`src/backend/`）

| 箇所 | 変更 |
|---|---|
| `repo/repository.py` | `get_token_plan`（**組で返す**）/ `get_plan_pairs` / `get_plan_meta` / `insert_plan` / `activate_plan` / `count_judgments_for_plan_set` / `answered_pair_ids_for_slot` / `existing_item_ids`。**`list_items()` は凍結** |
| `scripts/plan_ingest.py` | **投入 CLI**: ★ハッシュ照合 → `POST /admin/plan` → `--activate` |
| `admin/api.py` | `POST /admin/plan`・`/admin/plan/activate`（**activate ガード**）/ 充足は `list_active_items` / `token_issue` に**プラン束縛** |
| `participant/session.py` | **★置換点**: プラン引き当て or フォールバック。**`save_pair_sequence` 以降は無変更** |
| `domain/` | **`assignment.py`・`likert.py` とも無改修** |

---

## 使い方（カットオーバー手順）

```bash
# ⓪ 許諾成立/不成立の決定と使用セットの記録（研究側記録）
# ① デプロイ（0005 が適用される）⚠️ 発行済み未消化トークンが無い時点に限る
# ② プール投入
uv run python -m scripts.pool_ingest items_real.json

# ③ プラン生成（D1 に触れない・ファイルを書くだけ）→ **コミット**
uv run python -m scripts.plan_generate \
    --pool items_real.json \
    --composition plans/primary/composition.json \
    --constraints plans/primary/constraints.json \
    --out-dir plans/primary --seed 20260720
git add plans/primary && git commit -m "plan: primary set fixed"

# ④ 投入 → 有効化（★content_hash を再計算して照合してから POST する）
uv run python -m scripts.plan_ingest plans/primary --activate

# ⑤ トークン発行（★この時点で (plan_set, plan_index) が束縛される）
uv run python -m scripts.token_issue 8 --url-template 'https://<host>/?token={token}' --out tokens.dist.txt

# 脱落時の補充（BR-U6-15）
uv run python -m scripts.token_issue 1 --plan-index 3 --url-template '...' --out sub.dist.txt
```

**⑤ は ④ の後でなければならない**（先に発行すると束縛先が未定）。**③ はプール確定後**（プランはプールから構成される）。

---

## 設計上の不変条件（テストで検出しにくい仕様の明文化）

### 1. 🔒 層の用途別リスト（BR-U6-05）

| 定数 | 用途 | 除外 |
|---|---|---|
| `POOL_LAYERS` | 充足判定の**母数** | `practice`（練習素材は本番プールではない） |
| `REQUIRED_LAYERS` | **非空を要求**する層 | `anchor`（**研究上の要請**であって**アルゴリズムの成立条件ではない**） |

**`for layer in Layer` の全走査は禁止** — 走査だと**層値を足すたびに要求が自動で増える**（`practice` を足した瞬間に「practice 非空」まで要求する誤動作）。`anchor` の投入忘れは **`plan_generate` の期待組成チェック**（BR-U6-22）で検出する。

### 2. 🔒 構成で保証 / 探索で作る / 検証する の三分割（DP-U6-02）

| 制約 | 方法 |
|---|---|
| 露出 gap=0 / 全体連結 / 同一ペア0 | **構成**（m-正則巡回グラフ） |
| 層間比率 / 禁止辺 / 濃縮 | **探索（配置）+ 検証** |
| k 制約 / ブロック連結 | **検証 + seed 再試行** |

**層間比率が配置依存**であることが要（実測: **grouped 0.390 ❌** / interleave 0.728 / shuffle 0.772）。「ランダム生成 + リトライ」だけでは **grouped 配置で構造的に収束しない**。

### 3. 🔒 Likert 固定リストは**内容と件数の両方**がプラン権威（BR-U6-06）

プラン経路では `AssignmentParams(likert_fixed_targets=<10 件>, likert_items=len(<10 件>))` を渡す。

**件数も合わせる理由（integration で実測・検出）**: `select_likert_targets` は `want = min(likert_items, |pool|)` 件を返すため、**固定リストが `likert_items` より短いと不足分をラウンドロビンが補充**する＝**FD Q2 で否決した挙動が部分的に復活**する。長さを合わせれば**補充ループに入らない**（`likert.py` は無改修）。

### 4. 🔒 `save_pair_sequence` 以降は無変更（U5 DP-U5-02）

Session + PairSequence + `likert_targets` の**同一 batch 原子保存**は U5 のまま。U6 は**その手前（何を保存するか）だけ**を差し替えた。

### 5. 🔒 トークンには `(plan_set, plan_index)` を**組で**束縛（DP-U6-06）

`plan_index` 単独だと `plan_set` が「その時点の有効セット」参照になり、**発行 → セッション開始の間に activate が切り替わるとトークンの意味が変わる**。組で束縛すればこの窓が消え、**activate ガードの述語も一意に定まる**。

### 6. 補充トークンは「特別扱い」しない（BR-U6-15）

`start_or_resume` は**常に**「そのスロットで**まだ回答されていない本番ペア**だけを配る」:
- **初回**: 回答済みゼロ → 全量（分岐不要）
- **補充**: 脱落者の未回答分のみ → **m=12 が保たれる**（全量やり直しは二重判定で gap≠0）

**練習だけは常に全量再提示**（補充者は別人ゆえ読み返しテストの習得が必要・出力段除外で二重カウントの害ゼロ）。

### 7. 🔒 投入前の内容ハッシュ照合（DP-U6-07）

`plan_ingest` は `plan.json` の行 + `plan.meta.json` の `likert_targets` から
**`content_hash` を再計算**し、メタ記載値と一致しなければ **POST せず exit 1**。検出できるもの:

| 事象 | 検出のしかた |
|---|---|
| 生成後の手直し・マージ事故 | 行の 1 箇所の変更でハッシュが変わる |
| `plan.json` と `plan.meta.json` が**別々の生成実行に由来** | ハッシュが `likert_targets` も含むため、行が同じでも検出できる |
| 投入経路での取り違え | サーバが記録したハッシュとも突き合わせる |

**`content_hash` は `plan_generate` と同一の実装を import している**——再実装すると
「自分の計算どうしが一致する」だけになり、**生成器とのずれを検出できない**（照合が自己満足になる）。
unit で `plan_ingest.content_hash is generator_hash` を固定している。

### 8. `assignment_plan` に FK を張らない（Infra Q1=A′）

(i) items 参照 FK を 2→4 本に増やすと**将来の items 再構築の退避対象が増える** (ii) プラン投入をプール構成から独立させる。**整合性は生成時（`verify`）+ 投入時（アプリ層の実在検証）で二重に担保**。

---

## テスト

| 検証 | 場所 | 理由 |
|---|---|---|
| PU6-1〜8（露出/連結/k/同一ペア/層間/決定論/**ブロック連結**/**禁止辺**） | PBT | 生成器は純関数 |
| 層フィルタ・引き当て・**Likert 配線**・補充トークン | unit（`FakeRepo`） | ワイヤリング |
| **0005 のデータあり適用**・プラン投入/activate ガード・**フォールバック経路** | **integration（実 D1）** | SQL の意味論 |

**ジェネレータは n・E・J を振る**（U6-NFR-10）。1 点だけでは「その組合せでたまたま通る」ことしか示せない。

### 実行結果（2026-07-20）

- **unit + PBT: 108 緑**（U1〜U5 回帰含む・ci profile）
- **integration（実 D1・0005 適用後）: 52/52 PASS** — U6 **15/15** / 回帰 U2 9・U3 8・U4a 7・U5 13

### 🔍 テストが見つけた実装の穴 3 件

| 発見 | 内容 |
|---|---|
| **enum 走査がテスト基盤にも潜んでいた** | `Layer` に 2 値を足したら `generators.py`（`list(Layer)`）・`test_pool_sufficiency`（オラクルの `for L in Layer`）・`test_likert_selection`（層数「4」のハードコード）が回帰。BR-U6-05 は**実装だけ**を対象にしていた |
| **ブロック連結の実行可能性検査が無かった** | PBT の反例 `n=10, m=4, E=3`。ブロックが **n−1 辺に届かない**組合せは**どの seed でも不可能**なのに、`max_attempts` 回リトライして曖昧に失敗していた → **事前検査**を追加 |
| **Likert 固定リストの件数が権威でなかった** | integration で発覚。固定 3 件 + `likert_items=10` → **7 件がラウンドロビンで補充**されていた → **件数もプラン権威**に |

いずれも「**仕様は正しいが実装/テストに穴**」の類で、**PBT の反例と実 D1 の実測がそれぞれ 1 件ずつ検出**した。

## 変更していないもの（確認済み）
`wrangler.toml` / `deploy.yml` / `frontend/` / `Item` / `ExportItem` / **`EXPORT_FORMAT_VERSION`（1.0.0）** / `schema/bt.py` / `scripts/bt_aggregate/` / U3・U4b のコードとテスト / **`domain/assignment.py`・`domain/likert.py`**。
**`list_items()` は凍結**（シグネチャ・SQL とも無変更）。**PU3-3 は緑**＝U5 BR-U5-02 の禁止事項を踏んでいない証拠。
