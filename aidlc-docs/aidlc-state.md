# AI-DLC State Tracking

## Project Information
- **Project Type**: Greenfield
- **Start Date**: 2026-07-12T01:50:30Z
- **Current Stage**: CONSTRUCTION - U4a NFR Design (Part 2 生成完了・承認待ち)
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
- [x] NFR Design (Part 2 生成完了・承認待ち 2026-07-13。全 5 問★A、DP-U4a-01〜07 / LC-U4a-01〜06)
- [ ] Infrastructure Design
- [ ] Code Generation
- [ ] Build & Test

### 🟢 CONSTRUCTION PHASE
- [ ] Functional Design - EXECUTE
- [ ] NFR Requirements - EXECUTE
- [ ] NFR Design - EXECUTE
- [ ] Infrastructure Design - EXECUTE
- [ ] Code Generation - EXECUTE
- [ ] Build and Test - EXECUTE

### 🟡 OPERATIONS PHASE
- [ ] Operations - PLACEHOLDER

## Current Status
- **Lifecycle Phase**: CONSTRUCTION（per-unit ループ, U1）
- **Current Stage**: U1 Code Generation Part 1（Planning）— 生成完了・承認待ち（standardized 2-option GATE）
- **Units**: U1 基盤 / U2 参加者 / U3 研究者管理 / U4 スクリプト（実装順序 U1→U4a→U2→U3→U4b）
- **Completed**: U1 Functional Design（cb57583）／NFR Requirements（c70340a）／NFR Design（9cf22aa）／Infrastructure Design（承認済み 2026-07-12, H-1=(c) 確定, 8a4dc6f）
- **Next Stage**: U4a Infrastructure Design（NFR Design 承認後）
- **Status**: U4a NFR Design（Part 2）生成完了・承認待ち（Request Changes / Continue → Infrastructure Design）

## Open Gates / Blockers
（申し送り H-1/H-2/H-3 と同じ追跡方式）

- **G-1（✅ CLOSED, 2026-07-13）: 本番 smoke test 全 PASS = U1 最初の実デプロイの前提条件**
  - **結果**: `infrastructure-design.md §2.1` 第3回（GitHub Actions ubuntu-latest → `pywrangler deploy` → `*.workers.dev/smoke/all`）で**全 5 項目 PASS**（`smoke-test/result-prod.json`, CI artifact）。R-1/R-2 解消・TSD-02 本番確証。
  - **重要な構成変更**: **FastAPI → raw workers API + Pydantic v2**（F-4: FastAPI トップレベル import が起動 CPU 制限 10021 超過）。ハンドラは module-level `on_fetch(request, env)`（F-5）、`workers_dev=true`（F-6）、デプロイは CI 経由（F-1/F-3）。→ TSD-01 改訂・deployment-architecture.md 更新済み。
  - **フォールバック**: 案 B（PHP+SQLite）／TSD-02（pydantic v1/dataclasses）いずれも**発動せず**（フレームワーク差し替えで解消）。
  - **残タスク（ユーザー側・任意）**: Cloudflare 側 smoke Worker / D1（`nazokake-smoke`）の削除可（`smoke-test/` フォルダと workflow はリポジトリ残置＝本実装 CI 雛形）。`CLOUDFLARE_API_TOKEN` は本実装 CI 流用なら残置、しないなら失効。

## Residual Tasks（非ブロッキング）
- **RT-1: `.github/workflows/deploy.yml` の肉付け**。現状は**スケルトン**（`main=backend/entry.py`=ヘルスのみ / `database_id` プレースホルダ / push トリガ無効）で、そのままでは実デプロイは機能しない。**U4a〜U2 が形になり最初の実デプロイをする際に、`smoke-test/.github` の `smoke-test-deploy.yml` を雛形に、実 D1・実ルート・トークンで機能する形へ更新**する（G-1 で確定した F-1〜F-6 規約に従う）。
