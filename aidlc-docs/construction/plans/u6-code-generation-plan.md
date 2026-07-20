# U6 Code Generation Plan — 層拡張（下帯アンカー）+ 事前生成割当

**ユニット**: U6。**これまでで最大のユニット**（migration 0005 + 生成器 7 コンポーネント + API 2 本 + 引き当て置換 + 補充トークン + PBT 8 本）。
**前段**: Functional Design（BR-U6-01〜22）/ NFR Requirements（U6-NFR-01〜22 / TSD-U6-01〜10）/ NFR Design（DP-U6-01〜08 / LC-U6-01〜14）/ Infrastructure Design — すべて承認済み（2026-07-20）。
**目的**: **割当を実行時から設計時へ移す**。実行時から抽選ロジックを除去し、**事前生成・検査済みの固定プランの引き当て**にする。

> 実装規約: raw workers API + Pydantic v2 / module-level `on_fetch` / **src/ レイアウト**（F-8）/ トップレベル import 最小限（F-4）/ `scripts/` は非デプロイ・`_bootstrap` で src 解決。

このドキュメントは **Part 1（Plan + 決定点）**。承認後 Part 2 で本計画を**単一の真実**として生成する。

---

## 1. ユニット・コンテキスト

| 項目 | 内容 |
|---|---|
| **背景** | 実データ確定（n=38 / E=8 / J=228 / m=12）。**下帯アンカーは 4 層のどこに入れても測定妥当性を壊す** → 第5層値。**較正（p=3・α=0.7・S=30）は n=95 由来で n=38 では保証外** → 事前生成で較正自体を不要にする |
| **セット別確定値** | 成立版 `n=38 / J=228 / [29×4, 28×4]` / フォールバック版 `n=34 / J=204 / [26×4, 25×4]`（**両方とも実測で構成可能性を検証済み**） |
| **依存** | U1（`schema`・`Repository`・`domain`）、U4a（`handle_admin`・`AuthGuard`・`admin_log`・`scripts/_client`）、U2（`session`）、U5（`retired_at`・`list_active_items` の二本立て） |

**変更しないもの**: `wrangler.toml` / `deploy.yml` / `frontend/` / **`Item`** / **`ExportItem`** / **`EXPORT_FORMAT_VERSION`（1.0.0）** / **U3・U4b のコードとテスト** / **`assignment.py`・`likert.py`（domain は無改修）**。

---

## 2. 生成ステップ（番号付き・Part 2 の単一の真実）

### ■ スキーマ・マイグレーション

- [ ] **Step 1 — migration 0005**: `migrations/0005_layer_anchor_plan.sql`。
  **★子行退避方式**（単純再構築は FK 違反で失敗・実測）: `pairs_bak` 退避 → `DELETE FROM pairs` → `items` 再構築（CHECK に `anchor`/`practice` 追加・**`retired_at` を必ず引き継ぐ**）→ **列を明示して**復元 → `pairs_bak` 破棄。
  `assignment_plan`（**FK を張らない**）/ `assignment_plan_meta`（`seed`・`content_hash`・`is_active`）/ `tokens` に **`plan_set` + `plan_index`**（NULL 許容）。
  **ヘッダコメントに**: FK 全数調査結果（`pairs` の 2 本のみ・`likert_responses.target_ref` は FK 非設定・`judgments` は `tokens` のみ）+ **`assignment_plan` に FK を張らない設計判断**。
- [ ] **Step 2 — schema 層定数と型**: `Layer` に `ANCHOR`/`PRACTICE` 追加。**`POOL_LAYERS`**（母数・`practice` 除外）/ **`REQUIRED_LAYERS`**（非空要求・`anchor` 除外）を `schema` に追加（**`scripts` から使うため `backend` には置けない**）。`AssignmentPlanRow` / `AssignmentPlanMeta` / `PlanVerification` / `PlanIngestRequest` を追加。**🔒 `Item`/`ExportItem`/`EXPORT_FORMAT_VERSION` は不変**。
- [ ] **Step 3 — `pool_sufficiency` 置換**: **`for layer in Layer` の走査を廃し**、`POOL_LAYERS` で母数を絞り `REQUIRED_LAYERS` で非空検査。**「充足判定の唯一の実装」を維持**（置換はこの 1 関数内で完結）。

### ■ プラン生成器（`scripts/plan_generate/` — 非デプロイ）

- [ ] **Step 4 — `constraints`（LC-U6-01）**: 制約ファイル + **期待組成**の読込・検証。**三つ組（プール・期待組成・制約ファイル）はセット単位**。期待組成の不一致で**明示失敗**（BR-U6-22）。
- [ ] **Step 5 — `placement`（LC-U6-02・★制約付き探索）**: 円周配置を探索。**目的**: ① 禁止ペアを距離 >6（ハード）② 層間比率 ≥0.65 ③ 濃縮対象を近接 ④ 忌避ペアを可能なら遠くに（ソフト）。**実測で 3 目的の同時成立を確認済み**（違反 0 / 層間 0.706 / 濃縮 9-9）。
- [ ] **Step 6 — `graph_build`（LC-U6-03）**: `C_n(1..m/2)` を構成。**構成で保証**: 露出 gap=0 / 全体連結 / 同一ペア 0。
- [ ] **Step 7 — `partition`（LC-U6-04）**: J 辺を E スロットへ分割（k≤3 を満たす貪欲配分）。
- [ ] **Step 8 — `sequencing`（LC-U6-05）**: スロット内のペア列を並べ替え（**隣接回避**）。**練習ペアを全評価者共通で固定記載**（`is_practice=1`）。**出力順がそのまま `pair_index`**。
- [ ] **Step 9 — `verify`（LC-U6-06）**: **BR-U6-10 の①〜⑥ + PU6-8（禁止辺不在）**を検証し `PlanVerification` を返す。**忌避はレポートのみ**（失敗させない）。
- [ ] **Step 10 — `plan_generate` CLI（LC-U6-07）**: **構成 → 検証 → 失敗なら seed を進めて再試行 → 上限で明示失敗**。**明示失敗**: 正則不能（`2J` が `n` で割り切れない）/ **分割総和 ≠ J** / 期待組成不一致 / 再試行上限。**メタ記録**: 初期 `seed` + **成功試行番号** + **内容ハッシュ**。

### ■ 実行時（`src/backend/`）

- [ ] **Step 11 — `Repository` 拡張（LC-U6-08）**: `get_plan_pairs(plan_set, plan_index)` / **`get_token_plan(token) → (plan_set, plan_index)`**（★組で返す）/ `insert_plan(rows, meta)` / `activate_plan(plan_set)` / `count_judgments_for_plan_set(plan_set)`。**🔒 `list_items()` の凍結（U5 BR-U5-02）は維持**。
- [ ] **Step 12 — `PlanApi`（LC-U6-09）**: `POST /admin/plan`（投入・**参照 item の実在をアプリ層で検証**＝FK を張らない代替）/ `POST /admin/plan/activate`（**judgment 存在で 4xx 拒否**）。`admin_log` に `plan_ingest` / `plan_activate` / `plan_activate_rejected`（**`plan_set` + `seed` + 内容ハッシュ**）。
- [ ] **Step 13 — `start_or_resume` の分岐（LC-U6-10・★置換点）**: `get_token_plan` が **NULL ならフォールバック**（`generate_pairs` 無改修）/ **非 NULL ならプラン引き当て**。**`save_pair_sequence` 以降は一切変更しない**（U5 DP-U5-02 の原子保存）。
- [ ] **Step 14 — 補充トークン（LC-U6-11）**: 同一 `(plan_set, plan_index)` を束縛し、**本番の未回答ペアのみ**引き継ぐ（`judgments` との差分）。**★練習ペアは常に全量再提示**（補充者は別人・出力段除外で二重カウントの害ゼロ）。
- [ ] **Step 15 — `token_issue` 拡張**: 発行時に **`(plan_set, plan_index)` の組を束縛**（`plan_index` 単独にしない＝competition 窓の除去）。**activate 済みセットから**割り当てる。

### ■ テスト・文書

- [ ] **Step 16 — PBT（PU6-1〜8）**: `tests/pbt/`。PU6-1 露出 gap=0 / PU6-2 全体連結 / PU6-3 k≤3 / PU6-4 同一ペア 0 / PU6-5 層間 ≥0.65 / PU6-6 決定論 / **PU6-7 ブロック連結** / **PU6-8 禁止辺の不在**。**ジェネレータは n・E・J を振る**（1 点だけでは「その組合せでたまたま通る」ことしか示せない）。**失敗系**（正則不能・分割総和≠J）も検証。
- [ ] **Step 17 — unit**: `tests/unit/u6/`。`POOL_LAYERS`/`REQUIRED_LAYERS` の層フィルタ（**`practice` が母数外**・**`anchor` 不在でもゲートが落ちない**）/ `(plan_set, plan_index)` 引き当て / 補充トークンの引き継ぎ（**練習全量**）/ activate ガード / `admin_log` 出力。
- [ ] **Step 18 — integration（実 D1）**: `tests/integration/drive_u6.py`。**0005 を「データがある状態」で適用** + **適用後検証 3 点**（`foreign_key_check` / 行数一致 / `retired_at` 非 NULL 件数一致）/ プラン投入 → activate → セッション開始 → **ペア列がプランと一致** / **`plan_index IS NULL` のフォールバック経路が緑** / **activate ガードが judgment 存在で拒否** / **U2/U3/U4a/U5 の既存シナリオが緑**。
- [ ] **Step 19 — 回帰 + Documentation**: **U1〜U5 の既存 unit+PBT を全緑**。`aidlc-docs/construction/u6/code/README.md`。**`dry-run-dev.md` に U6 カットオーバー手順（⓪〜⑥）を追補**（「データがある状態での 0005 適用」検証を含む）。`manual-p-rsch.md` に**層 `anchor` の意味**と**バーの定義（指名アンカーの β 位置）**を追記。

---

## 3. Part 1 決定点（★推奨デフォルト付き。回答は各 [Answer] に記入）

### Q1【CLI の分割】生成と投入を分けるか
- **★A（推奨）**: **`plan_generate`（生成・ファイル出力）と `plan_ingest`（投入）を分ける**。
  - **理由**: BR-U6-12 が「**両セットはリポジトリにコミットして固定 → D1 には選択セットのみ投入**」を要求する以上、**生成と投入の間に「コミット」という人間の行為が挟まる**。1 つの CLI にすると、その分離が曖昧になる。
  - **U4b の「取得と推定の分離」と同型**（`curl` で `export.json` を得てから `bt_aggregate` する）。**生成物がファイルとして固定される**ことで**監査単位がファイルで閉じる**。
  - `plan_ingest` は**コミット済みファイルを読んで POST するだけ**（内容ハッシュを再計算して照合）。
- **B**: 1 つの CLI（`plan_generate --ingest`）。→ 生成と投入が同一実行になり、**「コミットされたものが投入された」保証が弱まる**。

[Answer]:

### Q2【パッケージ構成】`plan_generate` のファイル分割
- **★A（推奨）**: **`scripts/plan_generate/` をパッケージ**にし、**LC と一対一**で分割: `constraints.py`（LC-01）/ `placement.py`（LC-02）/ `graph_build.py`（LC-03）/ `partition.py`（LC-04）/ `sequencing.py`（LC-05）/ `verify.py`（LC-06）/ `__main__.py`（LC-07 CLI）。**U4b `bt_aggregate` と同型**（PBT の import 単位が LC 単位と一致し、分離をディレクトリ構造で物理的に強制）。
- **B**: 単一ファイル。→ 7 コンポーネントで肥大。PBT の import が濁る。

[Answer]:

### Q3【制約ファイルの形式】
- **★A（推奨）**: **JSON**（標準 `json`・追加依存なし）。**セット単位で 1 ファイル**:
  ```json
  {
    "plan_set": "primary",
    "forbidden_pairs":  [["N7", "C-6"], ...],
    "discouraged_pairs": [["...", "..."], ...],
    "enrichment": [{"anchor": "N8", "counterparts": ["...", ...], "target": 9}],
    "avoid_adjacent_groups": [["例1", "例4"], ["N6", "新作3"]]
  }
  ```
  - **`plan_set` を内包**させ、**期待組成の `plan_set` と一致しなければ明示失敗**（**成立版の制約ファイルをフォールバック版に誤適用する事故を防ぐ**——制約ファイルはセット別で流用不可, BR-U6-21）。
  - **未知キーは拒否**（`extra="forbid"`・typo で制約が黙って無効化されるのを防ぐ）。
- **B**: YAML / TOML。→ 追加依存（`pyyaml` 等）。**追加依存なし**の方針に反する。

[Answer]:

### Q4【★placement 探索】目的関数の優先順位と打ち切り
- **★A（推奨）**: **辞書式（lexicographic）の優先順位**で近傍探索（2 点交換）:
  1. **禁止ペアの違反数を最小化**（ハード・0 でなければ失敗）
  2. **層間比率を 0.65 以上に**（ゲート・**閾値到達で頭打ち**＝過剰最適化しない）
  3. **濃縮目標の達成本数を最大化**
  4. **忌避ペアの違反数を最小化**（ソフト・**達成できなくても失敗させない**）
  - **打ち切り**: 近傍探索の上限ステップ数に達したら**その seed は失敗**とし、**seed を進めて再試行**（決定論は「初期 seed → 試行列」で保つ）。**再試行上限で明示失敗**。
  - **②で頭打ちにする理由**: 層間比率を無制限に最大化すると**濃縮（③）と競合**する。**ゲートは満たせば十分**。
- **B**: 重み付き和（スカラー化）。→ 重みのチューニングが必要になり、**「禁止はハード」という質的差**を表現できない。

[Answer]:

### Q5【プランの格納場所と形式】
- **★A（推奨）**: **リポジトリ直下 `plans/<plan_set>/`** に 3 ファイル:
  - `plan.json`（`plan_index` / `idx` / `item_left` / `item_right` / `is_practice`）
  - `plan.meta.json`（`seed` / 成功試行番号 / `content_hash` / `n` / `E` / `J` / `m` / `generated_at`）
  - `verification.md`（`PlanVerification` の人間可読レポート・**忌避の未達も記載**）
  - **コミットする**（BR-U6-12: 「許諾判明前に両設計が固定されていた」証跡は **commit 履歴とハッシュ**が担う）。
  - **✅ `.gitignore` 確認済み（実測）**: `plans/<set>/plan.json`・`plan.meta.json`・`verification.md`・`constraints.json`・`composition.json` の**すべてが追跡対象**（`pool_*.json` / `items_*.json` / `export*.json` のいずれにも該当しない）。**プランは `item_id` のみで本文を含まない**ため**コミットして安全**。
- **B**: `aidlc-docs/` 配下。→ **成果物であって設計文書ではない**。コードと同じライフサイクルで管理すべき。

[Answer]:

### Q6【回帰の完了基準】
- **★A（推奨）**: **U1/U2/U3/U4a/U4b/U5 の既存 unit+PBT + U6 追加分をすべて緑**（ブロッキング）。
  - **PU3-3 が緑 = U5 BR-U5-02 の禁止事項を踏んでいない証拠**（U5 から継承）。
  - **U3/U4b のテストは無改修で緑を維持**＝**書き換えたら形式を変えた証拠＝設計違反のシグナル**。
  - **`generate_pairs` の既存 PBT（P-1）も緑のまま**（BR-U6-17 で残す方針ゆえ）。
  - integration は **0005 適用後**に U2/U3/U4a/U5 の既存シナリオを実 D1 で緑にする。
- **B**: U6 追加分のみ。→ **`items` テーブル再構築 + 参加者フローの割当置換**という**これまでで最も侵襲的な変更**。不採用。

[Answer]:

---

## 4. 完了基準
- [ ] 全 Step `[x]`。migration 0005・層定数・生成器 7 コンポーネント・API 2 本・引き当て置換・補充トークン・CLI 2 本が生成。
- [ ] **U1〜U5 回帰含め全テスト緑**（PU6-1〜8 追加）、**integration（実 D1・0005 をデータがある状態で適用）実行実績**。
- [ ] **🔒 `list_items()` が凍結**されている（U5 BR-U5-02）。
- [ ] **🔒 `for layer in Layer` の走査が残っていない**（`POOL_LAYERS`/`REQUIRED_LAYERS` へ完全置換）。
- [ ] **🔒 `save_pair_sequence` 以降が無変更**（U5 DP-U5-02）。
- [ ] **`wrangler.toml` / `deploy.yml` / `frontend/` / `Item` / `ExportItem` / `EXPORT_FORMAT_VERSION` / U3・U4b のコードとテストの変更なし**を確認。
- [ ] `construction/u6/code/README.md` + **`dry-run-dev.md` の U6 カットオーバー手順追補** + `manual-p-rsch.md` の層 `anchor` 追記。標準 2 択（Request Changes / Continue → Build & Test〈U6〉）。

---

**Part 2 生成時の運用**: 各 Step を順に生成し完了ごとに `[x]`。**本 plan の [Answer] 欄を記入**（監査証跡の自己完結）。テスト実行実績を提示。**Step が多いため、スキーマ/生成器/実行時/テストの 4 ブロックに分けて進捗を報告する**。
