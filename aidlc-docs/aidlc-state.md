# AI-DLC State Tracking

## Project Information
- **Project Type**: Greenfield
- **Start Date**: 2026-07-12T01:50:30Z
- **Current Stage**: CONSTRUCTION - U1 (共有基盤) Code Generation (Part 1: Planning・承認待ち)
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
- [ ] Code Generation (Part 1: Planning・承認待ち)

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
- **Next Stage**: U1 Code Generation Part 2（Generation）。Part 1 Plan 承認後に実コード生成
- **Status**: U1 Code Generation Part 1（Planning）生成・承認待ち（Request Changes / Continue → Code Generation Part 2）

## Open Gates / Blockers
（申し送り H-1/H-2/H-3 と同じ追跡方式。クローズ時に本欄と該当設計書を確定）

- **G-1（OPEN）: 本番 smoke test 全 PASS = U1 最初の実デプロイの前提条件**
  - **定義**: `infrastructure-design.md §2.1` 第3回（`uv run pywrangler deploy` → `*.workers.dev/smoke/all`）の**全 5 項目 PASS**を、**U1 の最初の実デプロイの前提**とする。ローカル PASS（第2回, 2026-07-12）は Code Generation 続行の暫定エビデンスに留め、**権威ある R-1 判定は G-1 で確定**。
  - **理由**: この Claude 環境からは Cloudflare 認証不可（アカウント別）。本番検証はユーザーのマシンで手動実行（deploy → curl、約5分）。方針 A（Code Generation 先行、G-1 はデプロイ直前ゲート）に合意（2026-07-12）。
  - **検証手段**: 使い捨て `smoke-test/`（本実装の初回デプロイでは代替しない＝失敗時に beta ランタイム問題 vs アプリバグを切り分け可能に保つ）。→ **`smoke-test/` は G-1 クローズまで削除しない**（後片付け `wrangler delete` も同）。
  - **失敗時分岐**（README 判定表流用）: **項目3のみ FAIL（Pydantic v2 不可）→ TSD-02 フォールバック**（DP-07 の狭い公開面で隔離・上位無波及）。**それ以外の FAIL**（項目1/2=Workers/FastAPI、項目4/5=D1/batch、および deploy 固有=依存バンドル/import スナップショット/remote binding）**→ 案 B（PHP+SQLite）へエスカレーション**（U1 で生き残るのは純粋ロジック＋schema 設計のみ、Repository/API 層は書き直し。DP-07 は無効＝Pydantic 起因限定の隔離）。
  - **クローズ手順**: ユーザーが本番 deploy → `result-prod.json` 受領 → §2.1 第3回欄と判定を確定 → 本 G-1 を CLOSED → `smoke-test/` 削除可。
