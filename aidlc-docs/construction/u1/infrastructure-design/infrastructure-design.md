# U1 Infrastructure Design — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**位置づけ**: U1 の論理コンポーネント（LC-01〜05）を Cloudflare 実インフラにマップし、申し送り **H-1** と App Design リスク **R-1 / R-2** を確定する。
**適用性（既決）**: Messaging = N/A、Networking / Monitoring = 最小限。以下は適用対象のみ。

---

## 1. 論理 → インフラ マッピング

| 論理コンポーネント | インフラ | 備考 |
|---|---|---|
| **LC-01 DataContract（schema/）** | Cloudflare **D1** の DDL（versioned migrations）+ 共有 Python パッケージ | 一意制約（DP-02）・NOT NULL（BR-11）・トークン契約（DP-05）を DDL/型に含む |
| **LC-02 AssignmentEngine（純粋）** | Cloudflare **Python Workers**（compute）内で実行 | 純粋関数。ランタイム外（ローカル/CI）でも同一コードで PBT 実行（DP-08） |
| **LC-03 Repository（唯一の I/O 境界）** | Python Workers 内から **D1 バインディング**でアクセス | **実行時の D1 アクセスは Worker に集約**（H-1 原則） |
| **LC-04 SessionState Serializer** | Python Workers 内（純粋、I/O は LC-03 経由） | — |
| **LC-05 LogEmitter** | Workers stdout（JSON）→ `wrangler tail` / ダッシュボード | 監視基盤・アラートなし（U1-NFR-10） |

- **Compute**: Cloudflare Python Workers（`python_workers` flag, open beta）+ FastAPI（ASGI）。
- **Storage**: Cloudflare D1（SQLite 互換, マネージド）。バインディング名は `deployment-architecture.md` で定義。
- **Networking**: Workers ルート（実験用サブドメイン）。ロードバランサ・API GW なし。CORS は U2/U3 の API 層。
- **Messaging**: なし（N/A）。

---

## 2. R-1: Python Workers beta 互換性の先行 smoke test（Q1=A）

**方針**: **Infrastructure Design 段階で最小 smoke test を先行実施**し、beta リスク（R-1）を Code Generation 前に解消する。TSD-02（Pydantic v2 可用性の「確認の儀式」）を兼ねる。

**smoke test 項目（最小 Worker をデプロイして確認）**:
1. `python_workers` flag 有効化で Worker が起動する。
2. **FastAPI（ASGI）** アプリがルーティングに応答する。
3. **Pydantic v2** が import でき、モデルの `validate`/`serialize` が動作する（TSD-02 検証）。
4. **D1 binding** 経由で最小クエリ（`SELECT 1` / 1 行 insert+select）が成功する。
5. **D1 batch**（複数ステートメントの原子適用, DP-01 の前提）が動作する（R-2 の確認）。

**判定と分岐**:
- 全項目 OK → 案 A′ 続行、結果を本書に追記（実施は Code Generation 直前でも可、記録は本書）。
- Pydantic v2 不可 → **TSD-02 フォールバック**（pydantic v1 pure-python / dataclasses+手書き検証）。LC-01 の狭い公開面（DP-07）により上位無波及。
- FastAPI/Workers 自体が不可 → **案 B（PHP+SQLite）へエスカレーション**（Application Design のフォールバック温存）。

### 2.1 smoke test 実施結果（2026-07-12・中間記録）

**実行環境**: `smoke-test/`（使い捨て。`pyproject.toml` + `uv run pywrangler`）。

| 回 | 環境 | 結果 | 備考 |
|---|---|---|---|
| 第1回 | エージェント環境・素の `npx wrangler`（認証なし） | 部分 | 項目1 ブート=実質 PASS（`from fastapi` 行で失敗＝Pyodide/stdlib は起動）、DDL `wrangler d1 migrations` 適用=PASS。項目2〜5 未了 |
| 第2回 | ローカル（miniflare, `uv run pywrangler dev`） | **全 5 項目 PASS**（`overall_pass=true`） | 詳細は下表。生データ `smoke-test/result-local.json` |
| 第3回 | **本番デプロイ**（`pywrangler deploy` → `*.workers.dev`） | **結果待ち（pending）** | Cloudflare 認証が必要（ユーザー環境で実行）。deploy 経路固有の**依存バンドル・import のメモリスナップショット化・D1 remote binding**を検証。通れば R-1 を正式クローズ。生データ予定 `result-prod.json` |

**第2回（ローカル全 PASS）詳細**:

| # | 項目 | 結果 | 詳細 |
|---|---|---|---|
| 1 | python_workers ブート | ✅ PASS | — |
| 2 | FastAPI ルーティング | ✅ PASS | ASGI 応答 |
| 3 | Pydantic v2（TSD-02） | ✅ PASS | **v2.10.6**（Cloudflare 同梱）、validate 双方向・不正値 reject |
| 4 | D1 binding | ✅ PASS | `SELECT 1`=1、insert/select roundtrip |
| 5 | D1 batch（DP-01/DP-02, R-2） | ✅ PASS | commit / **失敗時ロールバック（原子性）** / **ON CONFLICT DO NOTHING（既存維持）** |

**依存ロード方式の確定（第1〜2回で判明・TSD-01 に波及）**:
- Cloudflare Python Workers のサードパーティ依存（fastapi/pydantic）は **`requirements.txt` では不可**（pywrangler 1.15.0 は存在すると起動拒否）。**`pyproject.toml` の `dependencies` + `uv run pywrangler` でベンダリング**するのが正。→ **ツールチェーン = uv + pywrangler**（TSD-01 に明記）。
- デフォルト fetch ハンドラは **モジュールレベル `async def on_fetch(request, env, ctx)`**（クラスベース `WorkerEntrypoint.fetch` は現行ランタイムで未認識 = "Method on_fetch does not exist"）。
- ワーカーソースは `main` を独立ディレクトリ（`src/`）に隔離し、`node_modules`/`.venv` をバンドルに巻き込ませない。
- 以上は open beta ランタイムで確認した現行 API 形。**本番実装（U1 Code Generation）でも同一規約を用いる**。

**判定（暫定）**: R-1 / R-2 / TSD-02 はローカルで全 PASS。**第3回（本番）成功をもって R-1 を正式クローズ**し、本節の第3回欄と判定を確定する。フォールバック（TSD-02 / 案 B）発動の兆候は現時点でなし。

### 2.2 ゲート G-1（U1 実デプロイの前提条件）

**方針 A（合意 2026-07-12）**: ローカル PASS を暫定エビデンスとして U1 Code Generation を先行させ、**権威ある R-1 判定は本番 smoke test に置く**（放棄ではなく位置の移動）。この Claude 環境からは Cloudflare 認証不可（アカウント別）のため、本番検証はユーザーのマシンで手動実行する。

- **G-1（OPEN）**: **§2.1 第3回（`pywrangler deploy` → `*.workers.dev/smoke/all`）の全 5 項目 PASS を、U1 の最初の実デプロイの前提条件**とする。H-1/H-2/H-3 と同じ申し送り方式で追跡（`aidlc-state.md` Open Gates 欄にも記載）。
- **検証手段の分離**: G-1 の検証は**使い捨て `smoke-test/` で行い、本実装の初回デプロイでは代替しない**。初回デプロイで兼ねると、失敗時に「beta ランタイムの問題」か「アプリのバグ」かが切り分け不能になるため。→ **`smoke-test/` は G-1 クローズまで削除しない**（`wrangler delete` も同）。
- **失敗時分岐**（README §結果の解釈 の判定表を流用）:
  - **項目3のみ FAIL（Pydantic v2 不可）→ TSD-02 フォールバック**（pydantic v1 / dataclasses）。**DP-07 の狭い公開面で隔離**され上位無波及。
  - **それ以外の FAIL → 案 B（PHP+SQLite）へエスカレーション**。対象＝項目1/2（Workers/FastAPI 自体）、項目4/5（D1/batch）、および **deploy 固有リスク（依存バンドル / import メモリスナップショット化 / D1 remote binding）**。この受け皿は **DP-07 ではない**（DP-07 の隔離は Pydantic 起因の失敗に限定）。案 B 移行時、U1 で生き残るのは**純粋ロジック（LC-02/04）＋ schema 設計**のみで、**Repository/API 層は書き直し**。
- **クローズ**: 本番 deploy → `result-prod.json` 受領 → §2.1 第3回欄・判定を確定 → G-1 CLOSED → `smoke-test/` 削除可。

---

## 3. R-2: D1 の制約と対処

| 制約 | 対処 |
|---|---|
| トランザクション粒度 | **D1 batch（暗黙にトランザクショナル）** でセッション・ブートストラップを原子確定（DP-01）。明示的な多文トランザクションが要る箇所は batch に寄せる。 |
| 機能面（SQLite サブセット） | スキーマは単純（U1）。一意制約・`ON CONFLICT DO NOTHING`（DP-02）は SQLite 標準機能で充足。 |
| I/O 集約 | 全 D1 アクセスを LC-03 Repository に集約し、制約が顕在化しても差し替え可能に保つ（R-2 緩和, App Design）。 |

---

## 4. H-1 確定: scripts → D1 の接続方式 = 案 (c)（Q2=A）

**確定**: `scripts/`（U4 token_issue / pool_ingest / bt_aggregate）の**実行時 D1 アクセスは、Worker の管理用エンドポイント（Basic 認証背後）経由**とする。依存は `SCRIPT → API`（旧 `SCRIPT → REPO` を置換）。

**根拠**:
- **認証境界の一本化**: 管理画面（US-R01/R03）・エクスポート（US-R02）・スクリプト系（U4a）がすべて同一 Basic 認証（App Design Q5=B）背後に収まる。
- **I/O 境界の維持**: LC-03 Repository が **Worker 内専用**に保たれ、D1 アクセス経路が一本化される（LC-03「唯一の I/O 境界」）。
- **データ契約の共有**: scripts↔Worker の HTTP ペイロードにも `schema/` の Pydantic モデルを使用でき、単一データ契約（App Design Q6=A）が接続方式にまで及ぶ。
- **投入規模の現実**: pool_ingest 対象 約 95 件 = 1 回の POST で送れる規模。wrangler 直実行とのハイブリッド（経路 2 本）は複雑さの方が高くつくため (c) で統一。

**明確化（H-1 の例外ではない）**: **DDL 適用**（`wrangler d1 migrations`, §5）は管理エンドポイントを通らないが、これは**デプロイ時操作**であり「scripts の実行時接続」ではない。H-1 の原則（**実行時**の D1 アクセスは Worker に集約）と矛盾しない。

**波及**: App Design `component-dependency.md` の通信パターン「scripts/ → D1: 直接接続」を「**scripts/ → Worker 管理 API（Basic 認証）→ D1**」へ、依存マトリクス `C-SCRIPT-TOKEN / C-SCRIPT-POOL → C-REPO` を `→ C-API` へ更新（本ステージで反映済み）。**U4a/U4b の Functional Design はこの前提で行う**。

---

## 5. DDL / マイグレーション（Q4=A）

- **方式**: **`wrangler d1 migrations`**。versioned `.sql` を `schema/`（または `migrations/` サブディレクトリ）で管理し、migrations コマンドで各環境へ適用。
- **DDL に含む**: `Judgment` (`token`,`pair_id`) 一意制約（DP-02 / U1-NFR-04）、`Item.layer` NOT NULL（BR-11）、トークン長/文字集合（DP-05）、その他エンティティ（domain-entities.md）。
- **理由**: 「どの環境にどの DDL が適用済みか」を追跡可能にする。raw `execute`（B）は適用履歴が追えず不採用。

---

## 6. シークレット管理（Q5=A）

- **本番**: **`wrangler secret`**（Cloudflare secret ストア）。Basic 認証情報（管理 API, H-1 (c)）・機微設定を格納。**リポジトリに秘密を置かない**（NFR-08）。
- **ローカル**: `.dev.vars`（**gitignore 対象**）。→ `.dev.vars` の gitignore 追加を **Code Generation のチェック項目**に含める。

---

## 7. トレーサビリティ

| 項目 | 対応 |
|---|---|
| H-1 確定 (c) | App Design §8 H-1 → 本書 §4（+ component-dependency.md 更新） |
| R-1 緩和 | App Design R-1 → §2 smoke test |
| R-2 緩和 | App Design R-2 → §3 |
| DP-01（原子確定） | §3 D1 batch |
| DP-02（冪等） | §5 一意制約 |
| U1-NFR-08/DP-05（トークン契約） | §5 DDL |
| U1-NFR-10（ログ） | §1 LC-05 |

## 8. 後続申し送り（Code Generation）
- smoke test（§2）: ローカル全 PASS 記録済み。**ゲート G-1（§2.2）= 本番 smoke test 全 PASS を U1 実デプロイ前に必須**。`smoke-test/` は G-1 クローズまで温存。失敗時分岐は §2.2（項目3のみ→TSD-02 / それ以外→案 B）。
- **ツールチェーン**: 依存は `pyproject.toml`（`requirements.txt` 不可）、実行は **`uv run pywrangler`**。エントリポイントは**モジュールレベル `on_fetch(request, env, ctx)`**。`main` はソース隔離ディレクトリに置く（§2.1 確定）。
- `.dev.vars` gitignore、`wrangler.toml`（bindings/flags/routes）、migrations ディレクトリ構成。
- `α`/`S` 較正（DP-08 ハーネス共有）。
