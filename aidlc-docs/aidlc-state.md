# AI-DLC State Tracking

## Project Information
- **Project Type**: Greenfield
- **Start Date**: 2026-07-12T01:50:30Z
- **Current Stage**: CONSTRUCTION - U3 完了（CLOSE）→ U4b Functional Design Part 1 生成完了・承認待ち（GATE）
- **Architecture Decision**: 案 A′ = 静的フロント(バニラ JS) + Cloudflare Python Workers(raw workers API + Pydantic v2, **src/ レイアウト F-8**) + D1、PBT=Hypothesis

## Workspace State
- **Existing Code**: No
- **Reverse Engineering Needed**: No
- **Workspace Root**: /home/llm-user/nazokake-judge

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Extension Configuration
| Extension | Enabled | Decided At |
|---|---|---|
| Security Baseline | No | Requirements Analysis |
| Resiliency Baseline | No | Requirements Analysis |
| Property-Based Testing | Partial (enforce PBT-02/03/07/08/09) | Requirements Analysis |

## Execution Plan Summary
- **Stages to Execute**: Application Design, Units Generation, Functional Design, NFR Requirements, NFR Design, Infrastructure Design, Code Generation, Build and Test
- **Stages to Skip**: Reverse Engineering (Greenfield)
- **Risk Level**: Medium (割当ロジックの正しさが BT 推定に直結)

## Stage Progress
### 🔵 INCEPTION PHASE
- [x] Workspace Detection
- [x] Reverse Engineering (SKIPPED - Greenfield)
- [x] Requirements Analysis
- [x] User Stories
- [x] Workflow Planning
- [x] Application Design
- [x] Units Generation

### 🟢 CONSTRUCTION PHASE — per-unit ループ（U1→U4a→U2→U3→U4b）
#### U1: 共有基盤
- [x] Functional Design (承認済み 2026-07-12)
- [x] NFR Requirements (承認済み 2026-07-12)
- [x] NFR Design (承認済み 2026-07-12)
- [x] Infrastructure Design (承認済み 2026-07-12, H-1=(c) 確定)
- [x] Code Generation Part 1 (Planning) — 承認済み 2026-07-13
- [x] Code Generation Part 2 (Generation) — 承認済み 2026-07-13（unit+PBT 19 passed, α/S 較正確定）
- [x] Build & Test — 承認済み 2026-07-13（unit+PBT 19 + integration 4 全 PASS）。**U1 完了**

#### U4a: スクリプト先行分（token_issue / pool_ingest + 管理 API 先行導入）
- [x] Functional Design (承認済み 2026-07-13。Q5=X: Item.body を D1 格納=U1 波及。BR-U4a-12 発行時充足ゲート)
- [x] NFR Requirements (承認済み 2026-07-13。全 7 問★A + pool_sufficiency 単一実装)
- [x] NFR Design (承認済み 2026-07-13。全 5 問★A、DP-U4a-01〜07 / LC-U4a-01〜06)
- [x] Infrastructure Design (承認済み 2026-07-13。全 5 問★A。RT-1 を U4a で消化)
- [x] Code Generation Part 1 (Planning) — 承認済み 2026-07-13（全 5 決定点★A）
- [x] Code Generation Part 2 (Generation) — 承認済み 2026-07-13（unit+PBT 27 + integration 7 全 PASS。RT-1 CLOSED）
- [x] Build & Test — Code Generation 内で実施（integration 実 D1 全 7 シナリオ + unit/PBT 27）。**U4a 完了**

#### U2: 参加者セッション（participant）
- [x] Functional Design — **承認済み**（2026-07-14）。Q3=X（Likert 選定機構実装・方針は後日）、他は★A。**H-3 宿題クローズ**（XC-02=DB 行復元）。成果物 4 件（business-logic-model / business-rules BR-U2-01〜30 / domain-entities / frontend-components）
- [x] NFR Requirements — **承認済み**（2026-07-14）。全 8 問★A。U2-NFR-01〜15（出自秘匿の NFR 昇格・no-store・相関ハッシュ・楽観更新なし・migration 0003）+ TSD-U2-01〜06
- [x] NFR Design — **承認済み**（2026-07-14）。全 5 問★A。DP-U2-01〜07（出自秘匿の型排除が要）+ LC-U2-01〜08 + Repository/ビュー型拡張
- [x] Infrastructure Design — **承認済み**（2026-07-14）。全 5 問★A。Workers Static Assets 同一オリジン配信・CORS なし・migration 0003・deploy.yml 無変更・beta 3 点検証を Code Gen 冒頭に
- [x] Code Generation Part 1（Planning）— **承認済み**（2026-07-14, 全 6 決定点★A / Q1=U1 FD Q4=B の生成方法改訂を記録）
- [x] Code Generation（Part 1+2）— **承認済み・完了**（2026-07-14, 全 16 ステップ / 6 決定点★A）。unit+PBT 33 緑（U1/U4a 回帰含む）。実機で 2 バグ捕捉・修正: **F-7**（seed の D1 bind オーバーフロー→48bit）・**F-8**（バンドル module root→src/ レイアウト移行）+ entry.py catch-all→404。Q1=U1 FD Q4=B の生成方法改訂を記録
- [x] Build & Test — **完了**（2026-07-14）。unit+PBT **33 緑** / integration **全 9 項目 PASS**（実 D1/miniflare, result-u2-integration.json: PU2-2/4/5/7/8 + 一巡・出自秘匿）/ **本番初回デプロイ完了**（migrations 0001+0002+0003 本番適用済み）/ beta 3 点は dev 実測で確定（①api 到達・③未知=404・④admin 401・health 200）。**残**: F-8+catch-all 反映の**再デプロイ後の prod curl 疎通**（①=200・③=404・②`/`=index.html）→ beta 最終 CLOSE（自明・疎通のみ）。**U2 完了**

#### U3: 研究者・管理（admin）
- [x] Functional Design — **承認済み**（2026-07-15）。Q1=X（ExportBundle に items/pair_index/exported_at 追加）他★A。成果物 4 件（business-logic-model / business-rules BR-U3-01〜10 / **domain-entities: ExportBundle 正本** / frontend-components）。U3 は読み取り専用（migration なし）
- [x] NFR Requirements — **承認済み**（2026-07-15）。全 5 問★A。U3-NFR-01〜11（エクスポート秘匿・CORS なし決着・読み取り専用）+ TSD-U3-01〜05。PBT は PU3-3 のみ
- [x] NFR Design — **承認済み**（2026-07-15）。全 4 問★A。DP-U3-01〜05（body 非含有=型排除・練習除外の SQL 出力段保証）+ LC-U3-01〜06。管理 HTML=ui.py 定数
- [x] Infrastructure Design — **承認済み**（2026-07-15）。全 4 問★A。差分実質ゼロ（/admin/* GET 追加のみ・migration/シークレット/CORS/assets/deploy.yml 無変更）。curl 経路を U4b 自動化の正として申し送り
- [x] Code Generation Part 1（Planning）— **承認済み**（2026-07-15, 全 4 決定点★A / Q3=標準 csv モジュール）
- [x] Code Generation（Part 1+2）— **承認済み・完了**（2026-07-15, 全 10 ステップ）。unit+PBT 39 緑（回帰含む）・integration 全 8 項目 PASS（実 D1）+ 軽微修正 2 点（filename コロン除去・winrate 未出場注記）。migration/wrangler/deploy 変更なし
- [x] Build & Test — **完了**（Code Generation 内で実施: integration 実 D1 全 8 項目 + unit/PBT 39）。**U3 完了**

#### U4b: BT 集計スクリプト（bt_aggregate・最終ユニット）
- [~] Functional Design — **Part 1 生成完了・承認待ち**（2026-07-15）。US-R04。U3 の ExportBundle を入力とするオフライン BT 推定（scripts/・Worker 非依存）

### 🟡 OPERATIONS PHASE
- [ ] Operations - PLACEHOLDER

## Current Status
- **Lifecycle Phase**: CONSTRUCTION（per-unit ループ, U3 進行中）
- **Current Stage**: **U4b Functional Design Part 1 — 生成完了・承認待ち**（standardized 2-option GATE）
- **Units**: U1 基盤 / U2 参加者 / U3 研究者管理 / U4 スクリプト（実装順序 U1→U4a→U2→U3→U4b）
- **Completed**: U1／U4a（2026-07-13）／U2（2026-07-14）／**U3（完了 2026-07-15）**
- **Next Stage**: U4b Functional Design 承認 → NFR Requirements〈U4b〉…（最終ユニット）
- **Status**: **U3 完了（CLOSE）**。U4b（bt_aggregate・最終ユニット）Functional Design Part 1 生成・回答待ち（GATE）。U4b は U3 の ExportBundle を入力とするオフライン BT 推定（scripts/・Worker 非依存）。完成で「投入→発行→参加→エクスポート→BT 集計→新作の位置確認」の判定装置一巡が閉じる

## Open Gates / Blockers
（申し送り H-1/H-2/H-3 と同じ追跡方式）

- **G-1（✅ CLOSED, 2026-07-13）: 本番 smoke test 全 PASS = U1 最初の実デプロイの前提条件**
  - **結果**: `infrastructure-design.md §2.1` 第3回（GitHub Actions ubuntu-latest → `pywrangler deploy` → `*.workers.dev/smoke/all`）で**全 5 項目 PASS**（`smoke-test/result-prod.json`, CI artifact）。R-1/R-2 解消・TSD-02 本番確証。
  - **重要な構成変更**: **FastAPI → raw workers API + Pydantic v2**（F-4: FastAPI トップレベル import が起動 CPU 制限 10021 超過）。ハンドラは module-level `on_fetch(request, env)`（F-5）、`workers_dev=true`（F-6）、デプロイは CI 経由（F-1/F-3）。→ TSD-01 改訂・deployment-architecture.md 更新済み。
  - **フォールバック**: 案 B（PHP+SQLite）／TSD-02（pydantic v1/dataclasses）いずれも**発動せず**（フレームワーク差し替えで解消）。
  - **残タスク（ユーザー側・任意）**: Cloudflare 側 smoke Worker / D1（`nazokake-smoke`）の削除可（`smoke-test/` フォルダと workflow はリポジトリ残置＝本実装 CI 雛形）。`CLOUDFLARE_API_TOKEN` は本実装 CI 流用なら残置、しないなら失効。

## Residual Tasks（非ブロッキング）
- **RT-1: `.github/workflows/deploy.yml` の肉付け** — **✅ CLOSED（2026-07-13, U4a Code Generation で消化）**。`deploy.yml` を機能化: `uv sync → test（unit+PBT, 前置ゲート）→ d1 migrations apply --remote(0001+0002) → deploy`（tee パイプ不使用で終了コード保持）。`ADMIN_BASIC_*` は手元 `wrangler secret put`。実デプロイはユーザー環境（Cloudflare 認証）で実行。
