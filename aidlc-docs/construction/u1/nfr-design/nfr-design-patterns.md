# U1 NFR Design Patterns — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**位置づけ**: U1 NFR Requirements（U1-NFR-01〜15 / TSD-01〜08）を、具体的な設計パターンとして固定する。技術非依存の Functional Design と、案 A′ の技術決定の橋渡し。
**適用性（既決）**: Resilience / Scalability = **N/A**（NFR-06 / NFR-01）、Performance = **最小限**（SLO なし, U1-NFR-01/02）。以下は適用対象カテゴリのパターンのみ。

---

## 信頼性・整合パターン (Reliability / Integrity)

### DP-01: 原子的セッション・ブートストラップ（All-or-Nothing Batch）
- **問題**: セッション開始で Session 行・PairSequence（全ペア）・`exposure_snapshot` を書く。途中失敗で「Session はあるがペア列が無い/半端」が残ると、再開（US-P08）と露出導出（H-2）の両方が壊れる。
- **パターン**: これら 3 種の書き込みを **1 つの D1 batch（暗黙にトランザクショナル）** にまとめ、**all-or-nothing** で確定する。Session と PairSequence を分離不能にする。
- **帰結**: 半端な状態が**原理的に生じない**。整合チェック・補修ロジック（=新たなバグ源）を持たない。
- **根拠**: Q1=A, U1-NFR-03, US-P08, H-2。

### DP-02: DB 一意制約による冪等（Idempotent Upsert, 可観測）
- **問題**: 判定の重複送信（BR-08）を 1 件に収束させ、かつ再送クライアントが結果を確認できるようにする。
- **パターン**: `Judgment` に (`token`,`pair_id`) の**一意制約**を張り、書き込みは `INSERT ... ON CONFLICT DO NOTHING`（既存維持）。**サーバは 200 で既存 `choice` を返す**（冪等を**可観測**にする）。
- **帰結**: check-then-insert の競合窓を排除。再送クライアントは保存済み値を確認して次ペアへ進める → US-P03 の再試行 GWT に対応する U2 API 契約が単純化。
- **根拠**: Q2=A, U1-NFR-04, BR-08, US-P03。

### DP-03: 非アクティブ除外を組み込んだ導出（Derivation with Eligibility Filter）
- **パターン**: `derive_exposure` は保持テーブルを持たず、確定 PairSequence から毎回集計。**`last_active_at` が閾値（48h, BR-04）超の in_progress を適格集合から除外**して算出。
- **帰結**: 単一の真実（H-2）。離脱データの空カウント滞留を防ぐ。同時開始時のスナップショット鮮度ズレは**許容**（P-1 累積収束で吸収, Q8=A の非要件）。
- **根拠**: U1-NFR-02/06, BR-04, H-2, Q8=A。

---

## セキュリティ衛生パターン (Security Baseline)

### DP-04: パラメータ化クエリのみ（No String-Built SQL）
- **パターン**: Repository の全 SQL はプレースホルダ + バインド引数。文字列連結による SQL 組立を**コードレビュー/実装規約で禁止**。
- **根拠**: U1-NFR-07, BR-12, XC-03。

### DP-05: トークン契約の集中定義（Contract-at-Schema）
- **パターン**: トークンの**長さ・エントロピー（128-bit 以上）・文字集合（base64url）を `schema/` の型/制約として定義**。生成（U4a `token_issue`）・検証（U2/U3 API）は本契約を参照する。値の唯一の出所を schema/ に固定。
- **根拠**: U1-NFR-08, TSD-05, NFR-04。

---

## 可観測性パターン (Observability)

### DP-06: 単一ログヘルパによる構造化ログ（Structured Logging Facade）
- **パターン**: **単一ログヘルパ** `emit(event, level, **fields)` が JSON を **stdout** へ出力。標準フィールド = `event` / `level` / `ts` / `unit` + 文脈フィールド。**相関キーは `session_id` / `token`**。
- **最低イベント**: BR-06 露出目標未達 = `warning`、BR-05 構成不能 = `error`、seed/`exposure_snapshot` 参照 = `info`（監査/リプレイ用）。
- **帰結**: フィールド規約（Code Generation 申し送り）の**強制点がヘルパ一箇所に集約**。相関キーにより監査ログ（DP-06 info）とリプレイ調査（Q4=B）を突合可能。専用の監視基盤・アラートは持たない（NFR-06）。
- **根拠**: Q4=A, U1-NFR-10/11, TSD-06。

---

## テスト容易性パターン (Testability)

### DP-07: モデル契約の狭い公開面（Narrow Contract Facade — フォールバック耐性）
- **問題**: TSD-02 の「Pydantic v2 不可なら pure-Python へフォールバック」を、上位に波及させずに実効化する。
- **パターン**: 契約を `schema/` の**単一モジュール**に集約し、上位が触れるのは「**モデル型 + 明示バリデート関数**」という**狭い公開面のみ**。フォールバック時は `schema/` 内の実装差し替えで吸収し、**公開面は不変**に保つ。
- **帰結**: フォールバックが「実効性のある保険」になる（beta リスク緩和が機能）。公開面を狭く保つ追加コストはほぼゼロ。
- **根拠**: Q3=A, TSD-02, U1-NFR-15（層の逆流禁止と整合）。

### DP-08: ステートフル累積 PBT ハーネス（P-1 + P-5 統合オラクル）
- **パターン**: **固定シード**で S セッションを逐次生成し、各回 `updated_exposure` で露出をフィードバックする**ステートフル・シミュレーションハーネス**。
  - 各ステップで `updated_exposure` == `derive_exposure` 相当（**P-5 オラクル一致**）を確認。
  - 最終露出で **P-1 述語** `max−min ≤ max(2, α×mean)`（適格項目対象）を評価。
- **決定論化**: 統計的性質（P-1）は明示シードで固定し、CI の flaky 化を防ぐ（`deadline` 無効化, ci profile）。反例時はシード + 縮小入力を出力（PBT-08）。配置 `tests/pbt/`、受入基準（XC-01/P-1/P-5）を name/docstring 明記。
- **ハーネス = P-1 述語定義のコード化**（FD §5「S セッション累積後に評価」）。P-5 を各ステップで追加コストなく検証できる。
- **申し送り（Code Generation）**: `α`/`S` の**較正シミュレーションは本ハーネスと同一の累積ループを共有実装**する（較正スクリプト = ハーネスの流用）。較正ループと検証ループの乖離・二重実装を防ぐ。
- **根拠**: Q5=A, U1-NFR-12〜14, P-1/P-5（FD §5）, PBT-03/08/09。

---

## パターン → 要件トレーサビリティ

| パターン | 対応要件 | カテゴリ |
|---|---|---|
| DP-01 | U1-NFR-03, US-P08, H-2 | Reliability |
| DP-02 | U1-NFR-04, BR-08, US-P03 | Reliability |
| DP-03 | U1-NFR-02/06, BR-04, Q8=A | Reliability |
| DP-04 | U1-NFR-07, BR-12 | Security |
| DP-05 | U1-NFR-08, TSD-05 | Security |
| DP-06 | U1-NFR-10/11, TSD-06 | Observability |
| DP-07 | TSD-02, U1-NFR-15 | Testability / Maintainability |
| DP-08 | U1-NFR-12〜14, P-1/P-5 | Testability |
