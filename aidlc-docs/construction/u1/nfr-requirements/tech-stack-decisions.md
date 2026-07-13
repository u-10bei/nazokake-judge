# U1 Tech Stack Decisions — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**位置づけ**: 案 A′ の確定アーキを U1 の実装技術に落とす。値は Negotiable だが、決定形（何を選び、不可時どうするか）は本書で固定する。
**根拠**: U1 NFR Requirements 回答（Q1〜Q8 = 全て A）、`nfr-requirements.md`（U1-NFR-01〜15）。

---

## TSD-01: 言語・ランタイム・フレームワーク（★本番 smoke test で改訂, 2026-07-13）
- **言語**: Python。
- **ランタイム**: **Cloudflare Python Workers（Pyodide ベース, `python_workers` flag）**。
- **フレームワーク（改訂）**: **raw workers API（モジュールレベル `async def on_fetch(request, env)` + 手動ルーティング）+ Pydantic v2**。
  - **変更前**: FastAPI（ASGI）。**変更後**: raw workers API + Pydantic v2。
  - **根拠**: **F-4**（FastAPI のトップレベル import は起動 CPU 制限超過 `startup exceeded CPU limit ... [code: 10021]` で deploy 不可）、**F-5**（ハンドラはモジュールレベル `on_fetch`；クラス `WorkerEntrypoint` 継承は `TypeError: Method on_fetch does not exist` で不認識）。→ `infrastructure-design.md §2.1`。
  - **影響評価**: ルート数は 10 本程度で手動ルーティングの負担は軽微。Pydantic による I/O 検証・データ契約（App Design Q6=A）は無傷。案 A′ の骨格（Workers + D1 + Hypothesis + `schema/` 共有）は不変。**U2/U3 Functional Design はこのハンドラ形式を前提**とする（ASGI ミドルウェア前提の設計をしない。Basic 認証は `on_fetch` 内の関数として実装）。
- **ツールチェーン / デプロイ（smoke test で確定）**: **uv + pywrangler** を正とし、**実行（デプロイ）環境は CI（GitHub Actions ubuntu-latest）を正**とする（**F-1** requirements.txt 不可＝依存は `pyproject.toml`、**F-3** Windows ネイティブの pywrangler 非サポート＝uv 0.11.28 の Pyodide 配置と `python.exe` 期待パス不整合、WSL で回避可だが本プロジェクトは CI に一本化）。`wrangler.toml` に **`workers_dev = true`** を明記（**F-6**）。`main` はソース隔離ディレクトリ。
- **含意**: U1 の `backend/domain`・`backend/repo` は Pyodide 上で動作可能な pure-Python 依存に留め、**トップレベル import は最小限**（10021 再発防止, F-4）。重い C 拡張依存は避ける。
- 根拠: 案 A′（`aidlc-state.md`）、Infrastructure Design §2.1 smoke test（本番 F-1〜F-6）。

## TSD-02: モデル層（データ契約）— ★リスク管理付き決定
- **第一候補**: **Pydantic v2**（`schema/` の Pydantic モデルを Worker と `scripts/` で共有する**単一データ契約**。Application Design Q6=A）。
- **可用性検証**: Pydantic v2 の Pyodide/Workers 上での動作を **Infrastructure Design / Code Generation で確認**する（`pydantic-core` は Pyodide 公式パッケージセットに含まれ、Cloudflare のドキュメントでも FastAPI と並び挙げられているため**通る見込みは高い**。本決定の実質は「確認の儀式 + beta 環境への保険」）。→ **smoke test ローカル PASS（2026-07-12, Cloudflare 同梱 pydantic v2.10.6 で validate 双方向 OK, `infrastructure-design.md §2.1`）。本番デプロイ確認で正式クローズ。フォールバック発動の兆候なし。**
- **フォールバック（発動不要・条項は保守のため残置）**: 本番で v2.10.6 を確証したため以下は**発動しない**が、将来 beta ランタイム変更時の保険として残す:
  1. **pydantic v1（pure-Python）** — API 差はあるが単一契約の思想を維持できる。
  2. **`dataclasses` + 手書きバリデーション** — 依存最小。共有契約は型注釈 + 明示バリデータで表現。
- **不採用**: 「最初から軽量手段」（回答 B）は単一データ契約（Worker/scripts 共有）の利点を放棄するため採らない。
- **クローズ（2026-07-13）**: Pydantic **v2.10.6** の本番動作を確証（valid roundtrip / invalid rejected, §2.1 第3回）。**フォールバック発動不要**。DP-07 の狭い公開面は保守性のため維持。
- 根拠: Q1=A, U1-NFR-（モデル層）, App Design Q6=A, Infrastructure Design §2.1（本番確証）。

## TSD-03: DB アクセス（Repository / C-REPO）
- **DB**: **Cloudflare D1**（SQLite 互換, マネージド）。
- **クエリ**: **パラメータ化クエリのみ**（SQLi 対策, U1-NFR-07 / BR-12）。文字列連結による SQL 組立を禁止。
- **原子性**: PairSequence の一括保存は **D1 batch（暗黙にトランザクショナル）** で原子的に確定（U1-NFR-03）。部分書き込みを許さない。
- **具体 API 形**: D1 の batch/transaction の具体呼び出しは Infrastructure Design / Code Generation で確定。
- 根拠: Q3=A, 案 A′。

## TSD-04: 冪等制御
- **判定冪等（BR-08）**: (`token`,`pair_id`) の **DB 一意制約** + 冪等 UPSERT/INSERT（衝突時は既存を維持し成功応答）。DDL（`schema/`）に一意制約を含める。
- **理由**: アプリ層 check-then-insert（回答 B）の競合窓を排除し、サーバ/DB 側に一本化。
- 根拠: Q4=A, U1-NFR-04。

## TSD-05: トークン契約（U1 で規定・U4a で発行）
- **エントロピー**: **128-bit 以上**。生成基準は `secrets.token_urlsafe(16)`（22 文字前後の base64url）。
- **契約の所在**: 長さ・エントロピー・文字集合を **U1 の `schema/`（Pydantic モデル/制約）で規定**。発行実装は U4a `token_issue` が本契約に従う。
- **不採用**: 256-bit（回答 B）は URL 長の不便が増すのみ（発行数十トークンに対し 2^128 で十分）。
- 根拠: Q5=A, U1-NFR-08, NFR-04/XC-03。

## TSD-06: ロギング / 可観測性
- **形式**: **構造化ログ（JSON）を標準出力**へ。専用の監視基盤・アラート・メトリクス集約は持たない（wrangler tail / ダッシュボードで運用, U1-NFR-10）。
- **最低イベント**: BR-06 露出目標未達=warning、BR-05 構成不能=error、seed/exposure_snapshot 参照=info（監査/リプレイ用）。フィールド規約（event 名・item_id 等）は Code Generation で確定。
- 根拠: Q6=A, U1-NFR-10/11, NFR-06。

## TSD-07: プロパティベーステスト（PBT-09 正式記録）
- **フレームワーク**: **Hypothesis**（Python）。**PBT-09（フレームワーク選定）の正式決定**として本書に記録。
- **実行環境**: **ローカル/CI**（Worker ランタイム外の pure-Python として `generate_pairs` 等を検証）。
- **settings profile 分離**:
  - **dev**: examples 少なめ・高速（開発中の反復用）。
  - **ci**: examples 多め・`deadline=None`（無効）・`print_blob=True`・**固定シード**（再現可能実行）。
- **統計的プロパティの決定論化**: P-1（S セッション累積シミュレーション）は確率的性質を含むため、**明示シードで決定論化**して CI の flaky 化を防ぐ（U1-NFR-13）。
- **強制対象**: PBT-02（ラウンドトリップ）/ PBT-03（不変条件）/ PBT-07（ドメインジェネレータ）/ PBT-08（縮小・シード出力）/ PBT-09（本選定）。PBT-01/04/05/06/10 は advisory。
- **配置**: `tests/pbt/`。各プロパティテストは受入基準（XC-01/XC-02, P-1〜P-7）を name/docstring に明記。
- 根拠: Q7=A, NFR-07, U1-NFR-12〜15。

## TSD-08: コード配置（U1 該当分・再掲）
- `schema/`：Pydantic モデル + D1 DDL(.sql) + エクスポート形式バージョン（U1・共有。backend も scripts も import 可能なパスへ, `pyproject.toml` の packages 設定で解決。詳細は Code Generation）。
- `backend/domain/`：AssignmentEngine（純粋関数, XC-01）。
- `backend/repo/`：D1 Repository（C-REPO）。
- **層の逆流禁止**：上位（participant/admin/scripts）は U1 の公開インターフェースのみ import。逆は禁止。
- 根拠: unit-of-work.md, U1-NFR-15。

---

## 決定サマリ

| ID | 決定 | 不可/例外時 |
|---|---|---|
| TSD-01 | Python + Cloudflare Python Workers(Pyodide) + **raw workers API（`on_fetch`+手動ルーティング）+ Pydantic v2**。デプロイは uv+pywrangler / CI(GitHub Actions) | FastAPI 不可(F-4)→raw workers API |
| TSD-02 | Pydantic v2（単一データ契約）**本番確証 v2.10.6** | フォールバック条項残置・**発動不要** |
| TSD-03 | D1 + パラメータ化クエリ + batch 原子確定 | — |
| TSD-04 | 冪等 = DB 一意制約 + UPSERT | — |
| TSD-05 | トークン 128-bit（契約は schema/） | — |
| TSD-06 | 構造化 JSON ログ → 標準出力 | — |
| TSD-07 | Hypothesis / ローカル・CI / dev・ci profile / 固定シード | — |
| TSD-08 | schema/・backend/domain・backend/repo、層の逆流禁止 | — |

## 後続への申し送り
- **Infrastructure Design**: TSD-02 Pydantic 可用性検証、TSD-03 D1 batch/transaction 具体 API、H-1（scripts→D1 接続方式）。
- **Code Generation**: ログフィールド規約（TSD-06）、`α`/`S` 較正（P-1）、`pyproject.toml` の packages 解決（TSD-08）。
