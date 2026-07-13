# U4a NFR Requirements — token_issue / pool_ingest（+ 管理 API 先行導入）

U1 の NFR を前提に、U4a 固有の非機能要件を **U4a-NFR-NN** で定義する。最大論点は Basic 認証背後の管理 API のセキュリティ衛生。

---

## 1. セキュリティ（最重要）

- **U4a-NFR-01（認証境界）**: 管理エンドポイント `/admin/*` は **Basic 認証必須**・**HTTPS 強制**。資格情報は**単一の管理ペア** `ADMIN_BASIC_USER` / `ADMIN_BASIC_PASSWORD`（本番 `wrangler secret`、ローカル `.dev.vars`=gitignore）。**U2/U3 が同一境界を再利用**（認証境界一本化, App Design Q5=B / H-1(c)）。（Q1）
- **U4a-NFR-02（露出面）**: `/admin/*` は**サーバ間 CLI 専用**。**CORS を設けない**（ブラウザ由来アクセスを想定しない）。参加者 API と同一 Worker に同居し Basic 認証で分離。（Q2）
- **U4a-NFR-03（ログ秘匿）**: **構造化ログにトークン生値・謎かけ本文を出力しない**。管理操作ログは `event`/`level`/件数/`item_id`/結果コードのみ。**U4a 管理操作では token 生値を相関キーにしない**（U1 LogEmitter の相関キー既定と区別）。理由: `Item.body` の D1 格納（FD Q5=X）により謎かけ本文は**未公表の研究刺激**であり、ログ経路（wrangler tail 等）への漏出も防ぐ。（Q3）
- **U4a-NFR-04（配布物の非コミット）**: 配布用 URL 一覧・投入 JSON は **gitignore・リポジトリ非コミット**（NFR-08）。本文は D1 に格納するが git には置かない。（Q3）
- **U4a-NFR-05（基本衛生）**: Basic 認証情報の比較は**定数時間比較**（タイミング攻撃回避, `secrets.compare_digest` 相当）。管理 API 入力は schema/ Pydantic で検証、全 D1 アクセスはパラメータ化クエリ（BR-12）。（Requirements Q12=B 基本衛生）

## 2. 信頼性

- **U4a-NFR-06（原子投入）**: `insert_items` / `insert_tokens` は **D1 batch で all-or-nothing**（BR-U4a-09 / DP-01）。半端投入・部分発行を許さない。（Q4）
- **U4a-NFR-07（冪等・凍結）**: pool_ingest は**未参照 item にべき等**（`ON CONFLICT DO UPDATE`, BR-U4a-04）。**参照済み item への UPDATE は拒否**（凍結ガード BR-U4a-03、研究データ完全性）。（Q4）
- **U4a-NFR-08（発行の一貫性）**: トークン発行は**衝突事前排除 → batch → 全体リトライ**（BR-U4a-06）。**発行時充足ゲート**（現行プールが未達なら error+発行拒否, BR-U4a-12）で不完全プールでの実験開始を排除。（Q4）

## 3. 可観測性（最小限）

- **U4a-NFR-09（構造化ログ）**: U1 LogEmitter（`emit`）を再利用。管理操作の warning（BR-U4a-05 プール不足）・error（BR-U4a-03 ガード発火 / BR-U4a-12 発行拒否 / 401）を構造化出力。**トークン・本文は非出力**（U4a-NFR-03）。監視基盤なし（stdout, U1-NFR-10 と同方針）。

## 4. テスト容易性

- **U4a-NFR-10（充足判定の単一実装）**: **`pool_sufficiency(items, params)` を `backend/domain/` の純粋関数として単一実装**し、**BR-U4a-05（ingest 時の warn 判定）と BR-U4a-12（issue 時のハードゲート）の両方が同一関数を呼ぶ**こと。判定式を 2 箇所に別実装すると「warn は通ったが issue で落ちる（逆も）」の述語乖離が起きるため、単一実装で PBT が両呼び出し点を同時にカバーする。（Q6 追加要件）
- **U4a-NFR-11（PBT/統合の振り分け）**: 純粋ロジックは **PBT（Hypothesis）**、D1 依存は**統合テスト**（`tests/integration/` 流用）。（Q6）
  - PBT: `pool_sufficiency`（三点セットの境界値・反例探索）、トークン生成の一意性・契約適合（PU4a-4 生成部分）。
  - integration（実 D1）: PU4a-1（冪等 upsert）/ PU4a-2（凍結ガード）/ PU4a-5（原子性）/ PU4a-3a（段階投入 warn）/ PU4a-3b（発行ゲート）/ PU4a-6（認証 401）。
  - PBT 強制セットは U1 と同一（PBT-02/03/07/08/09）。

## 5. データ・マイグレーション

- **U4a-NFR-12（migration 0002）**: `migrations/0002_item_body.sql` を **versioned** で追加（`items.body TEXT NOT NULL`、`body_ref` NULL 許容化）。**新規プロジェクトで既存行なし**のため NOT NULL 追加は安全（二段階不要）。適用は `wrangler d1 migrations`（dev→prod, デプロイ時操作）。`schema/Item`・`list_items`・U1 テストを同時更新（U4a スコープ）。（Q5）

---

## 6. 非目標（意図的な非要件）

- **Performance**: SLO なし（約95件=1 POST・数十トークン。U1-NFR-02 と同方針）。
- **Scalability / Resiliency**: N/A（単独研究者・小規模）。
- **レート制限・濫用対策は設けない**（Q7）: Basic 認証背後・内部運用・小規模でレート制限は過剰。DoS 対策は Cloudflare 側の標準保護に委ねる。**「要件を課さない」ことを意図的な非要件として明示記録**する（後で「濫用対策の考慮漏れでは」と再燃させないため。U1 Q8 記録と同じ流儀）。
