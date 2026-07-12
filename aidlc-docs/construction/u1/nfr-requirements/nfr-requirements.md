# U1 NFR Requirements — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**位置づけ**: 技術非依存の Functional Design を、案 A′（Cloudflare Python Workers/Pyodide + FastAPI + D1、PBT=Hypothesis）の制約下で非機能面から具体化する。
**上位根拠**: プロジェクト要件 NFR-01/04/06/07/08、U1 業務ルール BR-05/06/08/11/12、U1 Functional Design（Q4=B リプレイ, H-2 露出導出, XC-02 ラウンドトリップ）。
**技術決定の詳細**: `tech-stack-decisions.md`（TSD-01〜08）を参照。

---

## 1. 性能 (Performance)

| ID | 要件 | 根拠 |
|---|---|---|
| **U1-NFR-01** | セッション開始処理（`generate_pairs` + `derive_exposure`）に**明示的な数値 SLO は設定しない**。参考目安として「セッション開始 < 1s（体感即時）」を非公式に置く。 | Q2=A, NFR-01 |
| **U1-NFR-02** | `derive_exposure` は全確定 PairSequence の毎回集計（保持テーブルなし, H-2）で実装してよい。想定データ規模（〜50 セッション × 約 43 ペア ≈ 2,000 行）では D1 上で実質瞬時であり、キャッシュ・マテリアライズは**不要**。 | Q2=A, H-2 |

**方針**: SLO を置いて計測・追跡する運用コストが、得られる価値を上回る規模。性能はアルゴリズム計算量（プール 90〜95・本番 40 ペア）と D1 の単純クエリで自然に満たされる。

---

## 2. 信頼性・データ整合 (Reliability / Integrity)

| ID | 要件 | 根拠 |
|---|---|---|
| **U1-NFR-03** | **PairSequence はセッション開始時に原子的一括保存**する。全ペアを 1 バッチ/トランザクションで確定し、部分書き込み（半端なペア列）を許さない。→ D1 の batch（暗黙にトランザクショナル）で実現。 | Q3=A, US-P08, H-2 |
| **U1-NFR-04** | **判定の冪等（BR-08）は DB 側で保証**する。(`token`,`pair_id`) の**一意制約**を DDL に含め、重複送信は冪等 UPSERT/INSERT（衝突時は既存回答を維持し成功応答）で 1 件に収束。アプリ層の check-then-insert には依存しない（競合窓を残さない）。 | Q4=A, BR-08 |
| **U1-NFR-05** | トークン状態遷移（`unused → in_progress → completed`, BR-09）の一方向性は永続層で担保。completed への新規回答は拒否。 | BR-09（FD 由来） |
| **U1-NFR-06** | 露出導出は**非アクティブ in_progress を除外**（`inactive_threshold` 48h, BR-04）した適格集合に対して行う。離脱データの空カウント滞留を信頼性上の要件として固定。 | BR-04（FD 由来） |

**非目標**: 高可用性・自動フェイルオーバー・DR は設計しない（NFR-06）。データ保全は回答の逐次保存 + 原子的ペア列確定で足りる（NFR-05）。

---

## 3. セキュリティ衛生 (Security Baseline — 拡張は No, 通常実装で必須)

| ID | 要件 | 根拠 |
|---|---|---|
| **U1-NFR-07** | **全永続化はパラメータ化クエリ**（SQLi 対策, BR-12/XC-03）。文字列連結による SQL 組立を禁止。 | NFR-04, BR-12 |
| **U1-NFR-08** | **トークンは 128-bit 以上のエントロピー**（`secrets.token_urlsafe(16)` 相当、22 文字前後 base64url）。トークンの**契約（長さ・エントロピー・文字集合）は U1 の `schema/` で規定**し、発行実装（U4a `token_issue`）はこれに従う。 | Q5=A, NFR-04, XC-03 |
| **U1-NFR-09** | HTTPS 強制・CORS 設定は U2/U3 の API 層で担保するが、その前提となる**トークン/識別子の型・制約は U1 schema/ が定義**する。 | NFR-04（波及元） |

**Security 拡張**: **No**（`aidlc-state.md` Extension Configuration）。上記は「基本セキュリティ衛生」として通常実装で必ず行う範囲であり、拡張ルールの適用ではない。

---

## 4. 可観測性 (Observability)

| ID | 要件 | 根拠 |
|---|---|---|
| **U1-NFR-10** | **構造化ログ（JSON）を標準出力**へ出力する。専用の監視基盤・アラート・メトリクス集約は持たない（wrangler tail / ダッシュボードで足りる規模）。 | Q6=A, NFR-06 |
| **U1-NFR-11** | 次のイベントを最低限ログ化する: **BR-06 露出目標未達の警告**（warning）、**BR-05 構成不能の事前検証エラー**（error）、PBT リプレイに資する **seed/exposure_snapshot 参照**（info、Q4=B 監査用）。ログのフィールド規約（event 名・item_id 等）は Code Generation で確定。 | Q6=A, BR-05/06 |

---

## 5. 保守性・テスト容易性 (Maintainability / Testability)

| ID | 要件 | 根拠 |
|---|---|---|
| **U1-NFR-12** | **PBT（Hypothesis）はローカル/CI で実行**（Worker ランタイム外の pure-Python として `generate_pairs` 等を検証）。強制対象 PBT-02/03/07/08/09 を U1 の重点箇所（XC-01 割当・XC-02 ラウンドトリップ）に適用。 | Q7=A, NFR-07 |
| **U1-NFR-13** | 統計的プロパティ **P-1（S セッション累積シミュレーション）は固定シードで決定論化**し、CI の flaky 化を防ぐ。Hypothesis の `deadline` は緩め/無効化。反例時はシード + 縮小入力を出力（PBT-08）。 | Q7=A, P-1（FD §5） |
| **U1-NFR-14** | Hypothesis の **settings profile を dev / ci で分離**（dev=examples 少・高速、ci=examples 多・deadline 無効・`print_blob=True`・固定シード）。この選定・設定は **PBT-09（フレームワーク選定）の正式記録**として `tech-stack-decisions.md` に含める。 | Q7=A, PBT-09 |
| **U1-NFR-15** | U1 の公開インターフェース（Pydantic モデル、Repository 公開メソッド、`generate_pairs`/`updated_exposure`）以外への上位ユニットの依存を禁止（**層の逆流禁止**）。テストは `tests/unit/u1/` と `tests/pbt/` に配置し、受入基準（XC-01/XC-02, P-1〜P-7）を name/docstring に明記。 | unit-of-work.md, NFR-07 |

---

## 6. 拡張ルール適合サマリ (Extension Compliance)

| 拡張 | 状態 | 本ステージでの扱い |
|---|---|---|
| Security Baseline | **Disabled (No)** | N/A（拡張ルールは適用しない）。基本セキュリティ衛生は U1-NFR-07〜09 で通常実装として担保。 |
| Resiliency Baseline | **Disabled (No)** | N/A。高可用性・DR は非目標（NFR-06）。 |
| Property-Based Testing | **Partial（強制 PBT-02/03/07/08/09）** | **適用**。U1-NFR-12〜15 で満たす。PBT-01/04/05/06/10 は advisory（重点箇所を name/docstring で追跡）。非該当なし。 |

---

## 7. 未決定・後続申し送り

| 項目 | 決定タイミング | 備考 |
|---|---|---|
| Pydantic v2 の Pyodide/Workers 実可用性の検証 | Infrastructure Design / Code Generation | TSD-02。通る見込み高、不可時フォールバックあり |
| D1 batch/transaction の具体 API | Infrastructure Design / Code Generation | U1-NFR-03 の実装形 |
| ログフィールド規約（event 名等） | Code Generation | U1-NFR-11 |
| `α`/`S`（P-1 露出偏り許容定数）の較正 | Code Generation | FD §5・business-rules.md |
