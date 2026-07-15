# AI-DLC State Tracking

## Project Information
- **Project Type**: Greenfield
- **Start Date**: 2026-07-12T01:50:30Z
- **Current Stage**: CONSTRUCTION - **U4b 完了 = 全ユニット完了**（U1/U4a/U2/U3/U4b 全て CLOSE）
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
- [x] Functional Design — **承認済み**（2026-07-15, Request Changes 反映=MM 擬似データ定式化・BR 番号是正）。US-R04。MM=Hunter 2004・観測ペア限定正則化（w̃_ij=w_ij+α/2, ñ_ij=n_ij+α）・最大成分内 Σθ=0・target_ref=item_id 較正・BTResult〈source エコーバック・除外 item 可視化〉。BR-U4b-01〜13。schema/bt.py・DDL 変更なし
- [x] NFR Requirements — **承認済み**（2026-07-15）。全 5 問 A。U4b-NFR-01〜13（行順序不問決定論=item_id 正準ソート・未収束 exit0・token 非参照・終了コード網羅）+ TSD-U4b-01〜06
- [x] NFR Design — **承認済み**（2026-07-15）。全 4 問 A。DP-U4b-01〜04（正準集計 3 点セット・restrict_to_component 切り出し）+ LC-U4b-01〜07（6 純関数+CLI）。**α 適用位置の不変条件を明文固定**（aggregate=生カウント / α は fit_bt 内部のみ / BTResult.matches/wins は生＝BR-U4b-08/PU4b-6 U3 突合の成立条件・Code Gen Step へ一行申し送り）
- [x] Infrastructure Design — **承認済み**（2026-07-15）。全 4 問 A。差分ほぼゼロ（`scripts/bt_aggregate` + `src/schema/bt.py` のファイル追加のみ・Worker/D1/deploy/migration/secret/CORS/assets 全て無変更）。入力=U3 curl 経路（取得と推定の分離・スナップショット監査単位=ファイル）・schema_version 検証・PBT+unit で検証完結（実機確認対象なし）・α 適用位置の不変条件を Code Gen へ申し送り
- [x] Code Generation Part 1（Planning）— **承認済み**（2026-07-15, 全 4 問 A / Q1=パッケージ分割 / Q2=α 適用位置不変条件 / Q3=α=1.0・max_iter=10000・tol=1e-10 / Q4=回帰全緑ブロッキング）+ Step 6 に rank 同値処理・Step 10 に α 感度注記を追記
- [x] Code Generation（Part 1+2）— **承認済み・完了**（2026-07-15, 全 10 Step）。`src/schema/bt.py`（BTResult/BTItemScore/Calibration）+ `scripts/bt_aggregate/`（aggregate/graph/mm/calibrate/assemble/__main__ = LC-U4b-01〜07 一対一）。unit+PBT **57 緑**（U1/U2/U3/U4a 回帰含む・ci profile）。**PBT 反例で 1 発見**: PU4b-1 単調性は正則化 ON では**次数対称な完全総当たり**でのみ堅牢（不規則グラフは α が疎 item を非対称に縮め順位入替＝BR-U4b-01「疎な新作ほど強く縮む」の実証）→ ジェネレータを完全総当たりに限定。**α 適用位置の不変条件**を aggregate/mm/assemble 3 箇所 + PU4b-6 で二重固定。**migration/wrangler.toml/deploy.yml/src/backend 変更なし**。実機 CLI 一巡確認（pro→rank1・新作→最下位・孤立 item=null・Σθ=0・calibrated が Likert 尺度へ写像・版検証 exit 1/0）
- [x] Build & Test — **完了**（Code Generation 内で実施: unit+PBT 57 緑 + 実データ CLI 一巡・終了コード契約・非連結/較正/除外 item 検証）。U4b は非デプロイ・実機確認対象なし（U4b-NFR-13）ゆえ PBT+unit で検証完結。**U4b 完了 = 全ユニット完了**

### 🟡 OPERATIONS PHASE
- [ ] Operations - PLACEHOLDER

## Current Status
- **Lifecycle Phase**: CONSTRUCTION（per-unit ループ, U4b 進行中・最終ユニット）
- **Current Stage**: **U4b 完了 = 全ユニット完了**（CONSTRUCTION PHASE 完了）
- **Units**: U1 基盤 / U2 参加者 / U3 研究者管理 / U4 スクリプト（実装順序 U1→U4a→U2→U3→U4b）**全て CLOSE**
- **Completed**: U1／U4a（2026-07-13）／U2（2026-07-14）／U3（2026-07-15）／**U4b（2026-07-15 完了）**
- **Next Stage**: OPERATIONS PHASE（あるいは本番デプロイ運用）。判定装置の一巡クローズ達成: 投入(U4a)→発行(U4a)→参加(U2)→進捗/エクスポート(U3)→BT 集計(U4b)→新作の位置確認
- **Status**: **全ユニット完了**。U4b Code Generation 完了（10 Step / 全 4 問 A）。unit+PBT 57 緑・実機 CLI 一巡確認。α 適用位置の不変条件・rank 同値・単調性の適用範囲（完全総当たり）を明文固定。差分は `scripts/bt_aggregate/` + `src/schema/bt.py` のみ（Worker/D1/deploy/migration 無変更）

## Open Gates / Blockers
（申し送り H-1/H-2/H-3 と同じ追跡方式）

- **G-1（✅ CLOSED, 2026-07-13）: 本番 smoke test 全 PASS = U1 最初の実デプロイの前提条件**
  - **結果**: `infrastructure-design.md §2.1` 第3回（GitHub Actions ubuntu-latest → `pywrangler deploy` → `*.workers.dev/smoke/all`）で**全 5 項目 PASS**（`smoke-test/result-prod.json`, CI artifact）。R-1/R-2 解消・TSD-02 本番確証。
  - **重要な構成変更**: **FastAPI → raw workers API + Pydantic v2**（F-4: FastAPI トップレベル import が起動 CPU 制限 10021 超過）。ハンドラは module-level `on_fetch(request, env)`（F-5）、`workers_dev=true`（F-6）、デプロイは CI 経由（F-1/F-3）。→ TSD-01 改訂・deployment-architecture.md 更新済み。
  - **フォールバック**: 案 B（PHP+SQLite）／TSD-02（pydantic v1/dataclasses）いずれも**発動せず**（フレームワーク差し替えで解消）。
  - **残タスク（ユーザー側・任意）**: Cloudflare 側 smoke Worker / D1（`nazokake-smoke`）の削除可（`smoke-test/` フォルダと workflow はリポジトリ残置＝本実装 CI 雛形）。`CLOUDFLARE_API_TOKEN` は本実装 CI 流用なら残置、しないなら失効。

## Residual Tasks（非ブロッキング）
- **RT-1: `.github/workflows/deploy.yml` の肉付け** — **✅ CLOSED（2026-07-13, U4a Code Generation で消化）**。`deploy.yml` を機能化: `uv sync → test（unit+PBT, 前置ゲート）→ d1 migrations apply --remote(0001+0002) → deploy`（tee パイプ不使用で終了コード保持）。`ADMIN_BASIC_*` は手元 `wrangler secret put`。実デプロイはユーザー環境（Cloudflare 認証）で実行。
