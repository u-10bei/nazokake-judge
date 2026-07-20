# U6 Infrastructure Design — 層拡張（下帯アンカー）+ 事前生成割当

**ユニット**: U6。**U1〜U5 の共有インフラ（D1 + 同一 Worker + CI デプロイ + Basic 認証）を全面流用**し、差分のみを定義する。共有分は `shared-infrastructure.md`、実装規約（F-1〜F-8）は U1 `infrastructure-design.md §2.1`、CI は U4a `§5`、`scripts/` 非デプロイ CLI は U4a `§1/§6` を参照。
**方針**: 差分は **(a) migration 0005** / **(b) `/admin/plan`・`/admin/plan/activate` の POST 2 本** / **(c) `scripts/plan_generate`（非デプロイ）** のみ。**`wrangler.toml` / `deploy.yml` / `frontend/` / シークレット / CORS はすべて無変更**。Infra Design（Q1=A′ / Q2=A+2 / Q3=A / Q4=A+2, 2026-07-20）。

> ## ⚠️ U5 と決定的に違う点
> U5 の 0004 は**安全な no-op 移行**（NULL 許容の列追加のみ）だったが、**0005 は「データがある状態での親テーブル再構築」**であり、**適用タイミングに制約がある**（U6-NFR-04）。**インフラ面の重心はここ**。

---

## 1. LC-U6 → インフラ マッピング（差分）

| 論理コンポーネント | インフラ | 備考 |
|---|---|---|
| **LC-U6-14 migration 0005** | **D1**: `items` 再構築（子行退避方式）+ `assignment_plan` / `assignment_plan_meta` 新規 + `tokens` に `plan_set`/`plan_index` 追加 | **適用ウィンドウ制約あり**（§2）。**唯一の重い差分** |
| **LC-U6-09 PlanApi** | 既存 Worker の `handle_admin` に **POST 2 本追加**（`/admin/plan`・`/admin/plan/activate`） | 既存 AuthGuard 背後。**新規シークレット・CORS 変更なし** |
| **LC-U6-08 Repository 拡張** | 既存 **D1 バインディング（`DB`）** 経由 | `get_plan_pairs` / `get_token_plan` / `insert_plan` / `activate_plan` |
| **LC-U6-10 引き当て・LC-U6-13 充足判定** | Worker 内 compute | **実行時に抽選ロジックがなくなる**（軽くなる） |
| **LC-U6-01〜07 plan_generate** | **手元/CI の pure-Python**（Worker 外・**非デプロイ**） | `scripts/` 配下・`_bootstrap` で src 解決・`scripts/_client` 流用 |
| **LC-U6-12 層定数・型** | `src/schema/`（コード） | インフラ依存なし |
| 参加者 API / フロント | **一切触れない** | **参加者 UI は画面の作りが一切変わらない** |

---

## 2. Storage — migration 0005（★最重要）

### 2-1. 内容

```sql
-- ① items 再構築（層値 anchor / practice 追加）— ★子行退避方式
CREATE TABLE pairs_bak AS SELECT * FROM pairs;
DELETE FROM pairs;
CREATE TABLE items_new (... CHECK (layer IN ('pro','ai','edit','rule','anchor','practice')) ...
                        retired_at TEXT);   -- ★ U5(0004) から必ず引き継ぐ
INSERT INTO items_new SELECT item_id, layer, body, body_ref, retired_at FROM items;
DROP TABLE items;  ALTER TABLE items_new RENAME TO items;
INSERT INTO pairs (token, pair_id, idx, item_left, item_right, is_practice)
  SELECT token, pair_id, idx, item_left, item_right, is_practice FROM pairs_bak;
DROP TABLE pairs_bak;

-- ② 割当プラン（★FK を張らない・Q1=A′）
CREATE TABLE assignment_plan (plan_set, plan_index, idx, item_left, item_right, is_practice,
                              PRIMARY KEY (plan_set, plan_index, idx));
CREATE TABLE assignment_plan_meta (plan_set PRIMARY KEY, seed, content_hash, n_items, n_slots,
                                   n_pairs, m_per_item, generated_at, is_active);

-- ③ トークンへのスロット束縛（NULL 許容ゆえ再構築不要）
ALTER TABLE tokens ADD COLUMN plan_set   TEXT;
ALTER TABLE tokens ADD COLUMN plan_index INTEGER;
```

### 2-2. 単純再構築が失敗する理由（実測）

**`pairs` が `items` を FK 参照する行を持つ状態では `DROP TABLE items` が `FOREIGN KEY constraint failed` になる**。0002 が通ったのは「新規プロジェクトで既存行なし」だったため。**`PRAGMA foreign_keys=OFF` / `defer_foreign_keys=ON` は D1 の migration 実行環境では効かない**（両方実測で失敗）。→ **子行退避方式が必要**（U6-NFR-01）。

### 2-3. ★ `assignment_plan` に FK を張らない（Q1=A′）

**理由 2 点**:
1. **将来の負債を作らない**: FK を張ると **items 参照 FK が 2 → 4 本**に増え、**将来 items を再構築する migration は `pairs` に加え `assignment_plan` も退避対象**にしなければならなくなる。
2. **プラン投入をプール構成から独立させる**: FK があると「プランが参照する item がすべて `items` にある」ことを DB が要求し、**投入順序の自由度を失う**。

**整合性は二重に担保**: (i) `plan_generate` は**プールからプランを構成**するため参照 item は**構成上すべて実在**（LC-U6-06 `verify` でも検証）(ii) **`POST /admin/plan` で参照 item の実在をアプリ層で確認**（FK と同じ保護を、順序の柔軟性を保ったまま得る）。

**0005 のヘッダコメントに残すこと**（U6-NFR-06 の拡張）:
- **FK 全数調査結果**: `items` を参照する FK は **`pairs.item_left`/`item_right` の 2 本のみ**・`likert_responses.target_ref` は **FK 非設定**・`judgments` は `tokens` のみ参照 → **退避対象が `pairs` だけで足りる根拠**
- **`assignment_plan` に FK を張らない設計判断**（将来の migration 作成者が「なぜ張っていないのか」を辿れるように）

### 2-4. ★ 適用ウィンドウの制約（U6-NFR-04・ブロッキング）

退避方式は **`DELETE FROM pairs` → 復元の間に「空の `pairs` を読む窓」**が生じ、稼働中だと**露出計算・セッション再開処理が壊れる**。

> **0005 の適用は「発行済み未消化トークンが存在しない時点」に限る。**

`deploy.yml` は毎回 migrations を適用するため、**0005 の適用タイミング = U6 を最初にデプロイするタイミング**。→ **U6 のデプロイは「実験開始前のカットオーバー」として実施する**（§4）。
**本番未デプロイゆえ初回デプロイでは自然に満たされる**（0001〜0005 一括適用・items も空）が、**dev 環境・将来の再適用では明示的に守る**。

### 2-5. 適用後検証（必須・U6-NFR-05）

1. `PRAGMA foreign_key_check` が**違反なし**
2. **`items` / `pairs` の行数が適用前後で一致**
3. **`retired_at` 非 NULL 件数が適用前後で一致**（U5 の廃止状態が保全されたこと）

### 2-6. プランセットの格納（★Q1=A′・BR-U6-12 改訂）

| 対象 | 格納場所 |
|---|---|
| **両セット（成立版 + フォールバック版）** | **リポジトリにコミット**（プラン + `seed` + 内容ハッシュ + 制約検証レポート）。「**許諾判明前に両設計が固定されていた**」証跡は **commit 履歴とハッシュ**が担う（**git のタイムスタンプと不変性は D1 より強い証跡**） |
| **選択されたセットのみ** | **D1**（`assignment_plan` / `assignment_plan_meta`） |

**「両セット D1 投入」を廃止した理由**: **D1 内でセットを切り替える時間窓が存在しない**——(i) activate ガード（judgment 1 件で拒否）により**切替は収集開始前のみ** (ii) **カットオーバーは許諾判明後**ゆえ **pool_ingest の時点で使用セットは確定済み**（両セットで `items` 組成が異なる以上、プール投入前に決まっている必要がある）。→ 両セット同時保持は**使われない自由度にコストだけ払い**、非活性セットの item を `items` に置く必要から**期待組成チェック（BR-U6-22）と衝突**し、**activate 時のプール入替は凍結ガード（BR-U4a-03）とも衝突**する。

**`admin_log` の `plan_ingest` に記録された内容ハッシュが、コミット済みハッシュと一致**することで**内容の同一性が閉じる**。

---

## 3. Compute / Networking（Q3）
- **`/admin/plan`（投入）/ `/admin/plan/activate`（有効化）** を**既存 Worker・同一サブドメイン**に追加。**既存 AuthGuard（Basic 認証）の背後**＝U4a の単一チョークポイントを通る。**ルート名で操作を明示**（ブール引数で意味を変えない）。
- **CORS なし**（同一オリジン・管理系は Basic 認証で参加者系と分離）。**新規公開面は `/admin/*` のみ**。
- **`scripts/plan_generate` は非デプロイ**（手元/CI の pure-Python・Worker バンドルに含めない）＝U4a/U5 CLI と同型。
- **参加者 API（`/api/*`）・`frontend/` には一切触れない**。

## 4. Deployment — カットオーバー手順（★Q2）

```
⓪ 許諾成立/不成立の意思決定と使用セットの決定を記録（研究側記録・admin_log 外）
   → 以降②〜④は決定済みセットで一本道（BR-U6-12 改訂により切替は発生しない）

① U6 をデプロイ（deploy.yml 手動実行）→ 0001〜0005 が適用される
   ⚠️ 前提: 発行済み未消化トークンが存在しないこと（U6-NFR-04）
   ⚠️ 適用後検証（§2-5）: foreign_key_check / items・pairs 行数一致 / retired_at 非NULL件数一致

② pool_ingest（決定済みセットのプール。anchor と practice 素材を含む）

③ plan_generate（リポジトリの該当セットを）→ POST /admin/plan
   ⚠️ ③はプール確定後でなければならない（プランはプールから構成される）

④ POST /admin/plan/activate（投入セットを有効化）

⑤ token_issue 8
   ★この時点で (plan_set, plan_index) がトークンへ束縛される（DP-U6-06）
   ⚠️ ⑤は④の後でなければならない（先に発行すると束縛先が未定）

⑥ 配布・実験開始
```

**順序を誤ると静かに壊れる**（④の前に⑤すると束縛先が定まらない）。**dev ドライランで⓪〜⑥の全順序をリハーサル**すること（§6）。

## 5. CI/CD（`deploy.yml` 無変更, Q4）
- **`deploy.yml` は無変更**。既存フロー `uv sync → test（前置ゲート）→ d1 migrations apply --remote（0001〜0005）→ deploy` がそのまま機能する（**versioned 自動適用ゆえ 0005 を書き足す必要すらない**）。
- **U6 の追加テスト（PU6-1〜8 + unit）は前置ゲートに自動搭載**。
- **PU3-3 が緑であることがデプロイの前提**＝**U5 BR-U5-02 の禁止事項を踏んだコードは本番に出られない**（U5 から継承）。
- **CI Secrets 差分なし**。

## 6. 動作確認（Q4）
- **integration（実 D1 / miniflare）**:
  - **0005 を「データがある状態」で適用**（U6-NFR-01/05）+ 適用後検証 3 点
  - プラン投入 → activate → セッション開始 → **ペア列がプランと一致**
  - **`plan_index IS NULL` トークンのフォールバック経路が緑**（U6-NFR-14 の実機確認。**0005 適用後 + 5 層値環境で通ること**に意味がある）
  - **activate ガードが judgment 存在で拒否**（4xx）
  - **U2/U3/U4a/U5 の既存シナリオが緑**（回帰）
- **dev ドライランでカットオーバー全順序（⓪〜⑥）をリハーサル**: `dry-run-dev.md` に U6 手順を追補し、**「データがある状態での 0005 適用」検証をこのリハーサルに載せる**。→ integration とは別に、**実際の運用手順そのものを一度通す**。
- **beta 検証は不要**（新規ランタイム機構なし）。**参加者 UI の目視も不要**（**画面の作りが変わらない**。ペア列の出所変更は integration の「ペア列がプランと一致」で覆われる）。
- **本番デプロイ後の確認**: **§2-5 の適用後検証 3 点** + `POST /admin/plan` の疎通（200・未認証 401）+ `wrangler tail` で `plan_ingest` ログ。

## 7. Secrets / Static Assets / Monitoring
- **Secrets**: **差分なし**（`ADMIN_BASIC_*` 再利用・`.dev.vars` 追加項目なし）。
- **Static Assets**: **`[assets]` 変更なし**（参加者 UI 不変）。
- **Monitoring**: `admin_log` に **`plan_ingest` / `plan_activate` / `plan_activate_rejected`** を追加（**`plan_set` + `seed` + 内容ハッシュ**を記録, DP-U6-07）。基盤は不変。

## 8. トレーサビリティ
| 項目 | 対応 |
|---|---|
| 0005 子行退避方式・`retired_at` 引き継ぎ | U6-NFR-01/02/03 / §2-2 |
| FK を張らない設計判断・ヘッダ記録 | Q1=A′ / U6-NFR-06 / §2-3 |
| 適用ウィンドウ制約 | U6-NFR-04 / §2-4 |
| 適用後検証 3 点 | U6-NFR-05 / §2-5 |
| 両セットはリポジトリ固定・D1 は単一セット | **BR-U6-12（改訂）** / §2-6 |
| カットオーバー順序（⓪〜⑥） | Q2 / §4 |
| POST 2 本・既存 AuthGuard 背後・CLI 非デプロイ | Q3 / §3 |
| `deploy.yml` 無変更・PU3-3 がデプロイの前提 | Q4 / §5 |
| フォールバック経路の integration 確認 | U6-NFR-14 / §6 |

## 9. 後続申し送り（Code Generation〈U6〉）
- **生成対象**: `migrations/0005_layer_anchor_plan.sql` / `Layer` 拡張 + `POOL_LAYERS`・`REQUIRED_LAYERS` / `pool_sufficiency` 置換 / `Repository` 拡張 / `PlanApi`（POST 2 本 + activate ガード）/ `start_or_resume` の分岐 / 補充トークン / `scripts/plan_generate`（LC-U6-01〜07）/ `schema` 型追加。
- **★ Step に一行固定すべき事項**:
  1. **0005 は子行退避方式**（単純再構築は FK 違反で失敗）・**`retired_at` の引き継ぎ**・**FK 全数調査結果 + 「`assignment_plan` に FK を張らない」判断をヘッダに**。
  2. **`list_items()` の凍結（U5 BR-U5-02）を維持**。
  3. **`save_pair_sequence` 以降を触らない**（U5 DP-U5-02 の原子保存）。
  4. **`for layer in Layer` の走査を残さない**（`POOL_LAYERS`/`REQUIRED_LAYERS` へ完全置換）。
  5. **トークンには `(plan_set, plan_index)` の組を束縛**（`plan_index` 単独にしない＝競合窓の除去）。
  6. **補充トークンは本番未回答分のみ引き継ぎ・練習は全量**。
  7. **プラン投入時に参照 item の実在をアプリ層で検証**（FK を張らない代替）。
  8. **回帰**: U3/U4b のテストは**無改修で緑**。**PU3-3 が緑 = U5 BR-U5-02 非違反の証拠**。
- **`dry-run-dev.md` への追補**: **U6 カットオーバー手順（⓪〜⑥）** + **「データがある状態での 0005 適用」検証**。
- **⚠️ 未確定事項**: **フォールバック版の期待組成 `n`**。提示された層内訳から計算すると **n=34**（pro6 + anchor2 + edit14 + ai9 + rule3）だが **n=36 と 2 件差**がある。**n=36 → `J=216`・`[27×8]` で完全均一** / **n=34 → `J=204`・`[26×4, 25×4]` の混在**。**どちらも成立するが結果が変わる**ため、フォールバック版のプラン生成前に確定が必要。
