# U6 Logical Components — 層拡張 + 事前生成割当

**方針**: **設計時（`scripts`）と実行時（`backend`）を明確に分ける**。実行時から割当ロジックを除去し、**引き当てのみ**を残す。層の一方向依存（`scripts` → `schema` / `backend` → `domain` → `schema`）は不変。

---

## 論理コンポーネント一覧

### ■ 設計時（`scripts/plan_generate/` — 非デプロイ・pure-Python）

### LC-U6-01: `constraints`（研究側入力の読込・検証）
- **役割**: **制約ファイル**（BR-U6-21）と**期待組成**（BR-U6-22）を読み、検証する。
  - 制約ファイル: **禁止ペア（ハード）/ 忌避ペア（ソフト）/ 濃縮目標 / 隣接回避グループ**
  - 期待組成: `n` と層別件数（例 38 = pro10/anchor2/edit14/ai9/rule3）→ **実プールと不一致なら明示失敗**
- **器と中身の分離**: **中身は研究側（タスク5）の成果物**。研究側の更新が**コード変更なしに反映**される。
- **依存**: `schema`（`Item` / `POOL_LAYERS`）。純粋。

### LC-U6-02: `placement`（★制約付き円周配置探索）
- **役割**: item を円周に並べる順序を決める。**単なるインターリーブではなく制約付き探索**（DP-U6-03）。
- **目的関数**: ① **禁止ペアを円周距離 >6 に**（ハード）② 忌避ペアを可能なら遠くに（ソフト）③ **濃縮対象を近接**させる ④ **層間比率 ≥0.65** を確保。
- **なぜ必須か**: **配置だけで層間比率がゲートを割る**（実測: grouped **0.390 ❌** / interleave 0.728 / shuffle 0.772）。**「たまたま通る」に委ねられない**。
- **実測（成立性）**: 禁止辺 8 本・濃縮 9 件で **違反 0 / 層間 0.706 / 濃縮 9-9 本を同時達成**。
- **依存**: LC-U6-01。純粋（`random.Random(seed)` で決定論）。

### LC-U6-03: `graph_build`（m-正則グラフの構成）
- **役割**: 配置済みの円周から **巡回グラフ `C_n(1..m/2)`** を構成（辺数 = n·m/2 = J）。
- **構成で保証される**（DP-U6-02）: **露出 gap=0**（全頂点が次数 m）/ **全体連結**（距離 1 の輪を含む）/ **同一ペア 0**（辺は集合）。
- **依存**: LC-U6-02。純粋。

### LC-U6-04: `partition`（スロット分割）
- **役割**: J 辺を E スロットへ分割（例 [29,29,29,29,28,28,28,28]）。**k 制約（評価者内の同一 item ≤3）**を満たす貪欲配分。
- **検証項目**（構成では保証されない）: **k 制約** / **ブロック連結性**（BR-U6-20）。
- **依存**: LC-U6-03。純粋。

### LC-U6-05: `sequencing`（★提示順の順序付け）
- **役割**: **各スロット内のペア列を並べ替える**。同一評価者内で**指定グループを連続提示しない**（内容制約④, BR-U6-21）。
- **なぜ独立ステップか**: **辺集合ではなくペア列の順序**の制約ゆえ、グラフ構成・分割では表現できない。**分割後に 1 段必要**。
- **練習ペアの固定記載**もここで行う（全評価者共通・`is_practice=1`, BR-U6-16）。
- **出力順がそのまま `pair_index`** になる（実行時に再現される）。
- **依存**: LC-U6-04。純粋。

### LC-U6-06: `verify`（プラン検証・投入前ゲート）
- **役割**: **BR-U6-10 の①〜⑥ + 内容制約**を検証し `PlanVerification` を返す。
  - ① 露出 gap=0 / ② 全体連結 / ③ k≤3 / ④ 同一ペア 0 / ⑤ 層間 ≥0.65 / ⑥ **ブロック連結** / **PU6-8: 禁止辺の不在**
  - **忌避ペアは違反してもエラーにせずレポート**（ソフト）。
- **投入前に失敗を検出できる**ことが事前生成の価値（実行時生成では不可能）。
- **依存**: LC-U6-01〜05。純粋。

### LC-U6-07: `plan_generate` CLI（オーケストレーション + I/O）
- **役割**: `python -m scripts.plan_generate --constraints c.json --expect-composition ... --seed N`。
  **構成 → 検証 → 失敗なら seed を進めて再試行 → 上限回数で明示失敗**（決定論は「seed → プラン」で保つ）。
- **明示失敗の条件**（U6-NFR-11）: 正則グラフが構成できない（`2J` が `n` で割り切れない等）/ **J の分割指定の総和 ≠ J** / 期待組成の不一致 / 再試行上限。
- **投入**: `POST /admin/plan`（管理 API 経由・D1 直は採らない）。
- **メタ記録**: **`seed`（初期）+ 成功試行番号 + プラン内容ハッシュ**（DP-U6-07）。
- **依存**: LC-U6-01〜06、`scripts/_client`。U4a/U5 の CLI と同型（**非デプロイ**）。

### ■ 実行時（`src/backend/` — 割当ロジックなし）

### LC-U6-08: `Repository` 拡張（プラン読み取り + 投入）
- `get_plan_pairs(plan_set, plan_index)` → スロットのペア列（**練習含む**・`idx` 順）
- `get_token_plan(token)` → **`(plan_set, plan_index)`**（NULL 可）★束縛された組を返す（DP-U6-06）
- `insert_plan(rows, meta)` / `activate_plan(plan_set)` / `count_judgments_for_plan_set(plan_set)`（activate ガード用）
- **依存**: D1。**`list_items()` の凍結（U5 BR-U5-02）は維持**。

### LC-U6-09: `PlanApi`（`handle_admin` 拡張）
- **`POST /admin/plan`（投入）/ `POST /admin/plan/activate`（有効化）** を**既存 AuthGuard 背後**に追加。**ルート名で操作を明示**。
- **activate ガード**: **当該セットに judgment が 1 件でも存在したら 4xx で拒否**（アプリ層の事前検証・DB 制約では表現不可）。
- **`admin_log`**: `plan_ingest` / `plan_activate` / `plan_activate_rejected` に **`plan_set` + `seed` + 内容ハッシュ**を記録。
- **依存**: LC-U6-08、既存 AuthGuard / `admin_log`。

### LC-U6-10: `start_or_resume` の分岐（★置換点・1 箇所）
```
新規セッション:
  (plan_set, plan_index) = get_token_plan(token)          ← トークン自身の束縛を読む
  if plan_index is None:                                   ← フォールバック（dev/ドライラン専用）
      pool  = list_active_items()
      pairs = generate_pairs(pool, exposure, seed, params) ← 従来経路（無改修で存置）
  else:
      pairs = get_plan_pairs(plan_set, plan_index)         ← 引き当てのみ（抽選なし）
  save_pair_sequence(session, pairs)                       ← U5 DP-U5-02 の原子保存を維持（不変）
```
- **`save_pair_sequence` 以降は一切変更しない**。`likert_targets` の同一 batch 保存も不変。
- **`generate_pairs` は無改修**（BR-U6-17）。呼ばれるのは**フォールバック経路のみ**。
- **依存**: LC-U6-08、既存 `domain`。

### LC-U6-11: 補充トークンの引き継ぎ
- **役割**: 脱落スロットの補充トークンに **`(plan_set, plan_index)` を同じ組で束縛**し、**本番の未回答ペアのみ**を `pairs` として作る（`judgments` との差分で導出）。
- **★練習ペアは常に全量再提示**（補充者は別人ゆえ読み返しテストの習得が必要。出力段除外ゆえ二重カウントの害はゼロ, BR-U6-15）。
- **依存**: LC-U6-08。

### ■ 共有（`src/schema/`）

### LC-U6-12: 層定数と型
- **`POOL_LAYERS`**（母数）/ **`REQUIRED_LAYERS`**（非空要求）を **`schema` に置く**（`scripts` は `backend` を import できないため）。
- `Layer` に `ANCHOR` / `PRACTICE` を追加。`AssignmentPlanRow` / `AssignmentPlanMeta` / `PlanVerification` を追加。
- **🔒 不変**: `Item` / `ExportItem` / `EXPORT_FORMAT_VERSION`（1.0.0）。

### LC-U6-13: `pool_sufficiency` の置換
- **`for layer in Layer` の走査を廃し**、**`POOL_LAYERS` で母数を絞り `REQUIRED_LAYERS` で非空を検査**する。
- **「充足判定の唯一の実装」を維持**（DP-U4a-05・ingest と issue の述語の乖離を防ぐ）ゆえ**置換はこの 1 関数内で完結**。

### LC-U6-14: migration 0005
- `items` 再構築（**子行退避方式**・`retired_at` 引き継ぎ）/ `assignment_plan` / `assignment_plan_meta` / **`tokens` に `plan_set` + `plan_index`**（NULL 許容・DP-U6-06 の束縛）。

---

## 依存方向（層の逆流禁止）

```
【設計時】scripts/plan_generate（非デプロイ）
   LC-01 constraints ─▶ LC-02 placement ─▶ LC-03 graph_build
                                              └▶ LC-04 partition ─▶ LC-05 sequencing
                                                                        └▶ LC-06 verify
                                                          LC-07 CLI（構成→検証→seed 再試行）
                                                                │ HTTPS + Basic
                                                                ▼
【実行時】Worker（既存 on_fetch）
   AuthGuard ─▶ LC-09 PlanApi（投入 / activate + ガード + admin_log）
                      │
                      ▼
   LC-08 Repository（get_plan_pairs / get_token_plan / insert_plan / activate_plan）
                      │                                    │
   LC-10 start_or_resume（NULL 分岐）───────────────────────┘
        ├─ plan あり ─▶ 引き当てのみ
        └─ plan なし ─▶ generate_pairs（無改修・フォールバック）
                      │
                      ▼  save_pair_sequence（U5 DP-U5-02・不変）
                     D1（migration 0005: LC-14）

【共有】schema: LC-12（POOL_LAYERS / REQUIRED_LAYERS / 型）← scripts も backend も参照
【domain】LC-13 pool_sufficiency（POOL_LAYERS 置換）・assignment.py は無改修
```

- **`scripts` → `schema` の一方向**（`backend` は見ない・実装確認済み）。
- **`domain` は repo に依存しない**（`assignment.py` / `likert.py` とも無改修）。
- **U3（export/winrate）・U4b（BT 集計）の LC には一切触れない**。

---

## 後続への申し送り（Infrastructure Design / Code Generation）

- **Infrastructure Design〈U6〉**: 差分は **migration 0005** + **`/admin/plan`・`/admin/plan/activate` の POST 2 本**のみ。**`wrangler.toml` / `deploy.yml` / `frontend/` / シークレット / CORS は無変更**。**適用ウィンドウ制約**（発行済み未消化トークンなし, U6-NFR-04）を**デプロイ手順に明記**。
- **Code Generation〈U6〉— Step に一行固定すべき事項**:
  1. **migration 0005 は子行退避方式**（単純再構築は FK 違反で失敗する）・**`retired_at` の引き継ぎ**・**FK 全数調査結果をヘッダコメントに**。
  2. **`list_items()` の凍結（U5 BR-U5-02）を維持**（`list_active_items` との二本立てを壊さない）。
  3. **`save_pair_sequence` 以降を触らない**（U5 DP-U5-02 の原子保存）。
  4. **`for layer in Layer` の走査を残さない**（`POOL_LAYERS` / `REQUIRED_LAYERS` へ完全置換）。
  5. **トークンには `(plan_set, plan_index)` の組を束縛**（`plan_index` 単独にしない＝競合窓の除去）。
  6. **補充トークンは本番未回答分のみ引き継ぎ・練習は全量**。
  7. **回帰**: U3/U4b のテストは**無改修で緑**（形式不変の証拠）。**PU3-3 が緑 = U5 BR-U5-02 の禁止事項を踏んでいない証拠**。
