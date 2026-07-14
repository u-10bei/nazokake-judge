# AI-DLC State Tracking

## Project Information
- **Project Type**: Greenfield
- **Start Date**: 2026-07-12T01:50:30Z
- **Current Stage**: CONSTRUCTION - U2 Infrastructure Design Part 2 生成完了・承認待ち（GATE）
- **Architecture Decision**: 案 A′ = 静的フロント(バニラ JS) + Cloudflare Python Workers(FastAPI) + D1、PBT=Hypothesis（案 B はフォールバック温存）

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
- [~] Infrastructure Design — **Part 2 生成完了・承認待ち**（2026-07-14）。全 5 問★A。Workers Static Assets 同一オリジン配信・CORS なし・migration 0003・deploy.yml 無変更・beta 3 点検証を Code Gen 冒頭に
- [ ] Code Generation - EXECUTE
- [ ] Build and Test - EXECUTE

### 🟢 CONSTRUCTION PHASE（U3 / U4b 未着手）
- [ ] U3（研究者・管理）: Functional Design 以降
- [ ] U4b（bt_aggregate）: Functional Design 以降

### 🟡 OPERATIONS PHASE
- [ ] Operations - PLACEHOLDER

## Current Status
- **Lifecycle Phase**: CONSTRUCTION（per-unit ループ, U2）
- **Current Stage**: **U2 Infrastructure Design Part 2 — 生成完了・承認待ち**（standardized 2-option GATE）
- **Units**: U1 基盤 / U2 参加者 / U3 研究者管理 / U4 スクリプト（実装順序 U1→U4a→U2→U3→U4b）
- **Completed**: U1（完了）／U4a（完了・承認済み 2026-07-13）／**U2 Functional Design + NFR Requirements + NFR Design（承認済み 2026-07-14）**
- **Next Stage**: U2 Infrastructure Design 承認 → **U2 Code Generation**（冒頭に Static Assets×Python Workers の beta 3 点検証）
- **Status**: U2 Infrastructure Design の成果物を生成（全 5 問★A / Workers Static Assets 同一オリジン / migration 0003 / deploy.yml 無変更）。plan の [Answer] 欄バックフィル済み。承認後 Code Generation〈U2〉へ

## Open Gates / Blockers
（申し送り H-1/H-2/H-3 と同じ追跡方式）

- **G-1（✅ CLOSED, 2026-07-13）: 本番 smoke test 全 PASS = U1 最初の実デプロイの前提条件**
  - **結果**: `infrastructure-design.md §2.1` 第3回（GitHub Actions ubuntu-latest → `pywrangler deploy` → `*.workers.dev/smoke/all`）で**全 5 項目 PASS**（`smoke-test/result-prod.json`, CI artifact）。R-1/R-2 解消・TSD-02 本番確証。
  - **重要な構成変更**: **FastAPI → raw workers API + Pydantic v2**（F-4: FastAPI トップレベル import が起動 CPU 制限 10021 超過）。ハンドラは module-level `on_fetch(request, env)`（F-5）、`workers_dev=true`（F-6）、デプロイは CI 経由（F-1/F-3）。→ TSD-01 改訂・deployment-architecture.md 更新済み。
  - **フォールバック**: 案 B（PHP+SQLite）／TSD-02（pydantic v1/dataclasses）いずれも**発動せず**（フレームワーク差し替えで解消）。
  - **残タスク（ユーザー側・任意）**: Cloudflare 側 smoke Worker / D1（`nazokake-smoke`）の削除可（`smoke-test/` フォルダと workflow はリポジトリ残置＝本実装 CI 雛形）。`CLOUDFLARE_API_TOKEN` は本実装 CI 流用なら残置、しないなら失効。

## Residual Tasks（非ブロッキング）
- **RT-1: `.github/workflows/deploy.yml` の肉付け** — **✅ CLOSED（2026-07-13, U4a Code Generation で消化）**。`deploy.yml` を機能化: `uv sync → test（unit+PBT, 前置ゲート）→ d1 migrations apply --remote(0001+0002) → deploy`（tee パイプ不使用で終了コード保持）。`ADMIN_BASIC_*` は手元 `wrangler secret put`。実デプロイはユーザー環境（Cloudflare 認証）で実行。
