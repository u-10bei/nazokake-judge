# U1 Code Generation Plan — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**前段**: Functional Design（cb57583）／NFR Requirements（c70340a）／NFR Design（9cf22aa）／Infrastructure Design（8a4dc6f, H-1=(c) 確定）— すべて承認済み。
**目的**: U1 の論理コンポーネント（LC-01〜05）を実コードに落とす。全ユニットが依存する **schema/（データ契約）・backend/domain/（純粋割当ロジック）・backend/repo/（唯一の I/O 境界）・LogEmitter** を生成し、PBT ハーネス（tests/pbt/）と較正ループを含める。

このドキュメントは **Part 1（Plan + 決定点）**。承認後 Part 2 で本計画を単一の真実として step ごとにコードを生成する（`code-generation.md` Step 10〜16）。

> **成果物の位置規則（Critical Rule）**: アプリコードは **ワークスペース直下**（`schema/` `backend/` `tests/` 等、**aidlc-docs/ には絶対に置かない**）。ドキュメント要約のみ `aidlc-docs/construction/u1/code/` に置く。

---

## 1. ユニットコンテキストとスコープ境界

### U1 が所有・生成するもの（このユニットの範囲）
| コンポーネント | 実装先 | 中身 |
|---|---|---|
| **C-SCHEMA**（LC-01 DataContract） | `schema/` | Pydantic v2 モデル群 + D1 DDL(.sql) + エクスポート形式バージョン番号 + トークン契約（長さ/エントロピー/文字集合, U1-NFR-08） |
| **C-DOM-ASSIGN**（LC-02 / LC-04） | `backend/domain/` | 純粋関数: `generate_pairs` / `updated_exposure` / `derive_exposure` / `serialize` / `deserialize`（副作用なし・決定論） |
| **C-REPO**（LC-03 Repository） | `backend/repo/` | 唯一の I/O 境界: `save_pair_sequence`（D1 batch 原子確定）/ `insert_judgment`（冪等 UPSERT）/ `read_exposure_counts` / `get_token`・`mark_token_*` / `list_items`。全メソッド **パラメータ化クエリ**（BR-12） |
| **LC-05 LogEmitter** | `backend/`（横断） | `emit(event, level, **fields)` → JSON を stdout（U1-NFR-10）。相関キー `session_id`/`token` |
| **PBT ハーネス + 較正ループ** | `tests/pbt/` + `tests/unit/u1/` | P-1〜P-7、ドメインジェネレータ、α/S 較正シミュレーション（DP-08 と共有実装） |

### U1 のスコープ**外**（下位ユニットが U1 の公開面を消費）
- **Worker の FastAPI ルート / SessionService・ResponseService（オーケストレーション）= U2**。U1 は「計算関数と永続化窓口」まで。開始時に露出を読み・ペア列を生成し・保存する制御は U2。
- **管理用エンドポイント（scripts→Worker, Basic 認証, H-1 (c)）の Worker API 実装 = U4a の前提**（U4a Functional Design で扱う）。
- 参加者 UI（frontend, U2）/ 管理 UI・エクスポート・暫定勝率（U3）/ token_issue・pool_ingest・bt_aggregate（U4）。
- → 本ユニットでは **API Layer / Frontend Components ステップは N/A**（下記 Step で明示スキップ）。

### 依存
- **上流依存なし**（U1 は最下層）。schema/ → 依存なし、domain/repo/ → schema/ のみ import。**層の逆流禁止**（U1-NFR-15, 逆流禁止テストを tests/unit/u1 に含める）。
- 実行時 D1 アクセスは Worker 集約（H-1=(c)）。ただし U1 が生成する Repository は **Worker 内専用モジュール**として D1 binding（`env.DB`）を受け取る形にし、Worker/ルート実装（U2）から呼ばれる。

---

## 2. プロジェクト構造（Greenfield・初期化）

```
nazokake-judge/
├── frontend/            （U2/U3 で生成 — U1 では空/未作成）
├── backend/
│   ├── domain/          ← U1: AssignmentEngine（純粋）+ SessionState Serializer
│   ├── repo/            ← U1: D1 Repository（唯一の I/O 境界）
│   ├── log.py           ← U1: LogEmitter emit()
│   ├── participant/     （U2）
│   └── admin/           （U3）
├── schema/              ← U1: Pydantic モデル + models/DDL + 形式バージョン（共有）
├── migrations/          ← U1: wrangler d1 migrations 用 versioned .sql
├── scripts/             （U4）
├── tests/
│   ├── unit/u1/         ← U1: example-based（層逆流禁止含む）
│   └── pbt/             ← U1: Hypothesis（P-1〜P-7）+ 較正ハーネス
├── pyproject.toml       ← U1: schema/ を backend も scripts も import 可能に（TSD-08）
├── wrangler.toml        ← U1: python_workers flag / D1 binding / dev・prod / ルート
└── .dev.vars.example    ← U1: ローカル秘密のテンプレ（実体 .dev.vars は gitignore）
```

---

## 3. 生成ステップ（番号付き・Part 2 の単一の真実）

各 step は完了時に `[x]` を付ける（Part 2 実行時）。

- [ ] **Step 1 — Project Structure Setup**: 上記ディレクトリ雛形。**ツールチェーン = uv + pywrangler**（smoke test §2.1 で確定）: 依存は **`pyproject.toml` の `dependencies`**（`requirements.txt` は不可）、`wrangler.toml`（python_workers flag・D1 binding `DB`・dev/prod 環境・実験用サブドメインルート、`main` はソース隔離ディレクトリ）、**エントリポイントはモジュールレベル `on_fetch(request, env, ctx)`**（クラス `WorkerEntrypoint.fetch` は不可）、`.dev.vars.example` 作成、`.gitignore` に `.dev.vars` 追加（INF §6 チェック項目）。
- [ ] **Step 2 — smoke test 参照 / G-1 ゲート（INF §2.1/§2.2）**: R-1/R-2/TSD-02 の**ローカル smoke test は実施済み・全 5 項目 PASS**（`smoke-test/`, `result-local.json`）。本 Step で smoke を再実施せず、確定事項（Pydantic v2.10.6・D1 batch 原子性・ON CONFLICT・上記ツールチェーン規約）を本実装に流用する。**権威ある R-1 判定は G-1**（本番 smoke test 全 PASS = U1 実デプロイの前提, §2.2）に置く — `smoke-test/` は G-1 クローズまで温存。**失敗時分岐**（G-1）: 項目3のみ FAIL→TSD-02 フォールバック（DP-07 隔離）/ それ以外（Workers/FastAPI・D1/batch・deploy 固有=bundle/snapshot/remote binding）→案 B エスカレーション（純粋ロジック+schema のみ生存, Repository/API 書き直し）。
- [ ] **Step 3 — C-SCHEMA 生成**（`schema/`）: Pydantic モデル（Item / Token / Session / Pair・PairSequence / Judgment / LikertResponse / SurveyResponse / ExposureCounts / AssignmentParams）+ D1 DDL(.sql) + エクスポート形式バージョン番号 + トークン契約定数。DDL 制約: `Judgment (token,pair_id)` 一意（DP-02）、`Item.layer` NOT NULL（BR-11）、`token` 一意・128bit 契約（DP-05/TSD-05）、状態 enum。**公開面は「モデル型 + 明示バリデート関数」のみ**（DP-07, 実装は内部隠蔽）。
- [ ] **Step 4 — C-SCHEMA 単体テスト**（`tests/unit/u1/`）: モデル検証・トークン契約（長さ/文字集合/エントロピー）・バリデート関数の境界。
- [ ] **Step 5 — C-SCHEMA サマリ**（`aidlc-docs/construction/u1/code/`）。
- [ ] **Step 6 — Business Logic 生成**（`backend/domain/`）: `generate_pairs`（重み付きランダム抽選+シード決定論化, BR-01/02/03/07/10）、`updated_exposure`（PBT オラクル）、`derive_exposure`（確定 PairSequence から集計・非アクティブ除外 BR-04, H-2）、`serialize`/`deserialize`（XC-02 対象=確定 PairSequence + 次未回答 index、seed/snapshot は対象外 H-3）。純粋・DB I/O なし。
- [ ] **Step 7 — Business Logic テスト**: example-based（`tests/unit/u1/`）+ **PBT**（`tests/pbt/`）。P-1（露出偏り `max−min ≤ max(2, α×mean)` を S セッション累積後に評価）/ P-2（層間比率）/ P-3（セッション内制約）/ P-4（ラウンドトリップ）/ P-5（updated_exposure==derive_exposure オラクル）/ P-6（決定論）/ P-7（位置一様）。ドメインジェネレータ（PBT-07, Item/ExposureCounts/AssignmentParams）、シード+縮小出力（PBT-08）、Hypothesis settings profile dev/ci 分離（TSD-07）。
- [ ] **Step 8 — α/S 較正ハーネス**（`tests/pbt/` 内, DP-08 と**共有実装**）: 固定シードで S セッション逐次生成・`updated_exposure` フィードバックの累積ループを P-1 検証と共有し、重み関数候補ごとの露出分布から α/S 暫定値を決定。確定値を `business-rules.md` パラメータ表に追記（述語形は固定済み・定数のみ）。
- [ ] **Step 9 — Business Logic サマリ**。
- [ ] **Step 10 — Repository 生成**（`backend/repo/`）: `save_pair_sequence`（Session+PairSequence+exposure_snapshot を**単一 D1 batch で原子確定**, DP-01/TSD-03）、`insert_judgment`（`ON CONFLICT DO NOTHING` + 既存 choice 返却, 冪等 DP-02/TSD-04）、`read_exposure_counts`、`get_token`/`mark_token_*`（状態遷移 BR-09）、`list_items`。**全メソッド パラメータ化クエリ**（BR-12/DP-04）。D1 binding を受け取る Worker 内専用モジュール。
- [ ] **Step 11 — Repository テスト**（`tests/unit/u1/`）: miniflare/ローカル D1 で冪等性・原子性・パラメータ化クエリ・非アクティブ除外導出。
- [ ] **Step 12 — Repository サマリ**。
- [ ] **Step 13 — LogEmitter 生成 + テスト**（`backend/log.py`）: `emit(event, level, **fields)` JSON→stdout、標準フィールド `event/level/ts/unit` + 相関キー `session_id`/`token`（DP-06）。フィールド規約を単一発行点に集約。
- [ ] **Step 14 — DB Migration Scripts**（`migrations/`）: `wrangler d1 migrations` 用 versioned `.sql`（DDL・一意制約・NOT NULL を含む）。dev→prod 適用手順を deployment サマリに記載。
- [ ] **Step 15 — API Layer / Frontend Components: N/A（スキップ）**: U1 スコープ外（U2/U3/U4a）。スキップ理由を明記。
- [ ] **Step 16 — Deployment Artifacts 確定**: `wrangler.toml` / `.dev.vars.example` / `pyproject.toml` を最終化し、`aidlc-docs/construction/u1/code/deployment-notes.md` にデプロイ手順（smoke→migrations→secret→deploy）を記録。
- [ ] **Step 17 — Documentation**: `aidlc-docs/construction/u1/code/` に U1 コード構成・公開面（下位ユニットが import してよい面）・テスト実行方法をまとめる。README のディレクトリ構成「予定」を実体に更新。

---

## 4. ストーリー・トレーサビリティ

U1 は横断制約と基盤を担う（個別の US-P/US-R は U2〜U4 で実装）。

| 受入基準 / 要件 | U1 での実装箇所 |
|---|---|
| **XC-01**（露出均衡・層間比率） | `generate_pairs`/`derive_exposure` + P-1/P-2/P-3（Step 6/7/8） |
| **XC-02**（状態ラウンドトリップ） | `serialize`/`deserialize` + P-4（Step 6/7） |
| **XC-03**（SQLi 対策部分） | Repository パラメータ化クエリ BR-12（Step 10）。Basic 認証は U3 |
| **U1-NFR-04**（判定冪等） | `insert_judgment` UPSERT + `(token,pair_id)` 一意（Step 3/10） |
| **U1-NFR-08**（トークン契約） | schema/ トークン契約定数（Step 3） |
| **U1-NFR-10**（構造化ログ） | LogEmitter（Step 13） |
| **U1-NFR-15**（層逆流禁止） | import 方向テスト（Step 7/11） |

---

## 5. Part 1 決定点（★推奨デフォルト付き）

前段設計でほぼ確定済み。Code Generation 固有の残決定のみ（NFR §7 の申し送り）。特記なければ **★A** を採用。

- **Q1（生成順とゲート）**: ★**A** = smoke test は**ローカル実施済み・全 PASS**（§2.1）につき本生成をそのまま進める。Pydantic v2/FastAPI/D1 batch の実可用性は確定済み。権威ある R-1 判定は **G-1（本番 smoke, §2.2）を U1 実デプロイ前ゲート**として残す。B=本番 smoke まで Code Generation 全体を保留（方針 A 合意により不採用＝ゲートは位置移動）。
- **Q2（serialize 形式）**: ★**A** = **JSON**（可読・監査リプレイ突合容易・Pydantic と親和）。対象は確定 PairSequence + 次未回答 index（seed/snapshot 非対象, H-3）。B=bytes（コンパクトだが可読性・デバッグ性で劣る）。
- **Q3（LogEmitter フィールド規約）**: ★**A** = `event/level/ts/unit` 固定 + 相関キー `session_id`/`token`、発行点は `emit()` 一箇所に集約（DP-06）。B=呼び出し側任意（規約強制点が分散）。
- **Q4（pyproject packages レイアウト）**: ★**A** = `schema/` を独立パッケージとして backend も scripts も**同一モジュール import**で解決（単一データ契約, Q6=A/TSD-08）。B=相対 import / パス操作（脆く scripts 実行時に壊れやすい）。
- **Q5（α/S 較正の扱い）**: ★**A** = Step 8 で **PBT ハーネスと同一の累積ループ**を共有実装して暫定 α/S を決定し `business-rules.md` に追記（NFR Design 申し送り: 較正ループと検証ループの二重実装回避）。述語の形は設計固定・定数のみ実装時決定。B=較正を別実装（乖離リスク）。
- **Q6（テスト実行環境）**: ★**A** = PBT/unit は **Worker 外の pure-Python** でローカル/CI 実行（Hypothesis, TSD-07）。Repository の D1 依存テストは miniflare/ローカル D1。実際のテスト**実行**は次段 Build & Test で行う（本ステージは生成まで）。

---

## 6. 完了基準（code-generation.md Completion Criteria）

- [ ] 本計画が承認され、全 Step が `[x]`。
- [ ] schema/ 公開面・domain 純粋関数・repo I/O 境界・LogEmitter が生成され、層逆流なし。
- [ ] PBT（P-1〜P-7）+ ドメインジェネレータ + 較正ハーネスが生成（実行は Build & Test）。
- [ ] migrations（versioned .sql）・wrangler.toml・pyproject.toml・.dev.vars.example・.gitignore(.dev.vars) が揃う。
- [ ] smoke test ローカル結果が記録済み（§2.1）。**G-1（本番 smoke 全 PASS）は U1 実デプロイ前の未クローズゲートとして追跡**（`aidlc-state.md` Open Gates）。
- [ ] `aidlc-docs/construction/u1/code/` にサマリ・デプロイ手順・公開面ドキュメント。
- [ ] U1 が Build & Test へ引き渡せる状態。
