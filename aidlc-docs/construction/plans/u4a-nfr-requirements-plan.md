# U4a NFR Requirements Plan — スクリプト先行分（token_issue / pool_ingest）

**ユニット**: U4a（C-SCRIPT-TOKEN / C-SCRIPT-POOL + 管理 API 先行導入）
**目的**: U4a の非機能要件を確定する。U4a は **Basic 認証背後の管理 API（`/admin/*`）を先行導入**するため、**セキュリティ衛生（認証・トークン秘匿・ログ非出力）**が最大論点。冪等性・原子性は Functional Design（BR-U4a-04/09）で決定済みなので NFR として明文化する。
**前提（既決）**: 拡張 opt-in は U1 と共通（Security Baseline=No / Resiliency=No / **PBT=Partial**）。案 A′（Cloudflare Python Workers + D1, raw workers API）。監視基盤なし（stdout JSON）。App Design Q5=B（Basic 認証）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-requirements.md`（U4a-NFR-NN）/ `tech-stack-decisions.md`（U4a 追加分）を生成します。

---

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-13）
- [x] `construction/u4a/nfr-requirements/nfr-requirements.md`（U4a-NFR-01〜12: セキュリティ/信頼性/可観測性/テスト容易性 + 非目標）
- [x] `construction/u4a/nfr-requirements/tech-stack-decisions.md`（TSD-U4a-01〜06: Basic 認証実装、pool_sufficiency 純粋関数、migration 0002、PBT/integration）

**回答サマリ**: 全 7 問 ★A。Q6 に追加要件「**`pool_sufficiency` は単一実装・2 呼び出し点**（BR-U4a-05 warn と BR-U4a-12 gate の述語乖離防止）」。Q7 レート制限なしを非目標として記録。

## NFR カテゴリ適用性（U4a）
| カテゴリ | 適用 | 備考 |
|---|---|---|
| **Security** | **適用（最重要）** | Basic 認証境界を先行導入・トークン/本文の秘匿。→ Q1〜Q3 |
| **Reliability** | 適用 | 冪等 upsert（BR-U4a-04）・原子投入（BR-U4a-09）・充足ゲート（BR-U4a-12）。→ Q4 |
| **Performance** | N/A | 約95件=1 POST・数十トークン。SLO なし（U1-NFR-02 と同方針）。 |
| **Observability** | 適用（最小限） | 構造化ログ（U1 emit 再利用）。ただしトークン生値・本文はログ非出力。→ Q3 |
| **Testability** | 適用 | PU4a-1〜6 の PBT/integration 振り分け・充足判定の純粋関数化。→ Q6 |
| **Scalability/Resiliency** | N/A | 単独研究者・小規模。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Security】Basic 認証の資格情報粒度
- **★A（推奨）**: **単一の管理資格情報ペア**（`ADMIN_BASIC_USER` / `ADMIN_BASIC_PASSWORD`）で全 `/admin/*` を保護。単独研究者・小規模運用（Q3=A 規模）に十分で、App Design Q5=B（Basic 認証・認証境界一本化）と整合。U2/U3 も同一ペアを再利用。
- **B**: ロール別（発行用/投入用/管理用）に資格情報を分離。→ 小規模には過剰、鍵管理コスト増。

[Answer]: A

### Q2【Security】管理エンドポイントの露出・CORS
- **★A（推奨）**: `/admin/*` は **サーバ間 CLI 専用**（ブラウザ非経由）。**CORS は設けない**（ブラウザ由来アクセスを想定しない）。参加者 API と同一 Worker に同居するが **Basic 認証で分離**。将来 U3 の管理 UI がブラウザから叩く場合の CORS/認証拡張は U3 で検討。
- **B**: 管理 API を別 Worker/サブドメインに分離。→ デプロイ・運用の二重化。小規模には過剰。

[Answer]: A

### Q3【Security/Observability】トークン・本文の秘匿（保存・配布・ログ）
- **★A（推奨）**: (i) **HTTPS 強制**（管理 API）。(ii) 配布用 URL 一覧・投入 JSON は **gitignore・リポジトリ非コミット**（NFR-08）。(iii) **構造化ログにトークン生値・謎かけ本文を出力しない**（管理操作のログは件数・`item_id`・結果コードのみ。U1 LogEmitter は相関キーに token を使うが、**U4a 管理操作では token 生値を相関キーにしない**）。
- **B**: ログにトークンを出す（デバッグ容易だが漏洩経路）。→ 不採用。

[Answer]: A

### Q4【Reliability】冪等性・原子性の要件化
- **★A（推奨）**: Functional Design の決定を NFR として固定 — `insert_items`/`insert_tokens` は **D1 batch で all-or-nothing**（BR-U4a-09/DP-01）、pool_ingest は **未参照 item に対しべき等**（BR-U4a-04）、発行は**衝突事前排除→batch→全体リトライ**（BR-U4a-06）。半端投入・部分発行を許さない。
- **B**: ベストエフォート（部分成功を許容）。→ 研究データ完全性（凍結ガード BR-U4a-03）と矛盾。

[Answer]: A

### Q5【Data/Migration】`migration 0002`（Item.body 追加）の適用・後方互換
- **★A（推奨）**: `migrations/0002_item_body.sql` を **versioned** で追加（`items` に `body TEXT NOT NULL`、`body_ref` を NULL 許容へ）。**新規プロジェクトで既存行なし**のため NOT NULL 追加は安全。適用は `wrangler d1 migrations`（dev→prod, デプロイ時操作）。schema/ の `Item`・`list_items`・U1 テストも同時更新（U4a スコープ）。
- **B**: `body` を NULL 許容で追加し後で NOT NULL 化。→ 二段階マイグレーションは不要（既存行なし）。

[Answer]: A

### Q6【Testability】PU4a-1〜6 の PBT/統合の振り分け + 充足判定の純粋関数化
- **★A（推奨）**: **純粋ロジックは PBT（Hypothesis）**、**D1 依存は統合テスト**（`tests/integration/` 流用）に振り分け:
  - PBT: 充足判定 `pool_sufficiency(items, params)`（BR-U4a-05 三点セットを**純粋関数**として `backend/domain/` に実装）、トークン生成の一意性・契約適合（PU4a-4 の生成部分）。
  - integration（実 D1）: 冪等 upsert の実挙動（PU4a-1）、凍結ガード（PU4a-2）、原子性（PU4a-5）、発行時ゲートの拒否/成功（PU4a-3b）、Basic 認証 401（PU4a-6）。
  - PBT 強制セットは U1 と同じ（PBT-02/03/07/08/09）に準拠。
- **B**: すべて統合テストで検証。→ 述語（充足判定）の反例探索が弱くなる。

[Answer]: A ＋ 追加要件: 充足判定 `pool_sufficiency(items, params)` は **単一実装・2 呼び出し点**（BR-U4a-05 の ingest 時 warn 判定と BR-U4a-12 の issue 時ハードゲートが同一関数を呼ぶ＝述語乖離の防止）。

### Q7【Security】管理 API のレート制限・濫用対策
- **★A（推奨）**: **設けない**。Basic 認証背後・単独研究者の内部運用・小規模（数十トークン/約95件）でレート制限は過剰。DoS 対策は Cloudflare 側の標準保護に委ねる。
- **B**: 簡易レート制限を実装。→ 規模に対し過剰・状態管理の複雑さ増。

[Answer]: A ＋ レート制限なしを **非目標**として nfr-requirements.md の非目標節に記録（U1 Q8 と同じ流儀）。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-requirements.md` / `tech-stack-decisions.md` を生成 → 標準 2 択（Request Changes / Continue → NFR Design）。
