# User Story Generation Plan — nazokake-judge

**役割**: プロダクトオーナー
**目的**: `requirements.md` の要件を、INVEST 準拠のユーザーストーリーと受入基準、およびペルソナへ変換する。
**前提**: Requirements Analysis 承認済み。User Stories Assessment = Execute（High Priority 該当）。

このドキュメントは **Part 1: Planning** の成果物です。**Part 1 全 7 問回答済み・承認済み（2026-07-12、会話で回答受領）** → **Part 2: Generation 実行済み**。

**Part 1 回答サマリ**: Q1=C(Hybrid: 参加者=Journey / 研究者=Feature) / Q2=A(2 ペルソナ) / Q3=C(GWT + チェックリスト併用) / Q4=B(中粒度) / Q5=B(研究者機能は最小限) / Q6=C(受入基準組み込み + 横断制約別立て) / Q7=A(BT 集計スクリプトも含める)

---

## 実行チェックリスト（Part 2 で実施）

- [x] 承認済みアプローチに従い `aidlc-docs/inception/user-stories/personas.md` を生成（ユーザー原型・特性・動機）
- [x] `aidlc-docs/inception/user-stories/stories.md` を生成（INVEST 準拠のストーリー）
- [x] 各ストーリーに受入基準を付与
- [x] ストーリーが Independent / Negotiable / Valuable / Estimable / Small / Testable であることを担保
- [x] ペルソナを関連ストーリーにマッピング
- [x] ペア割当の制約（露出均衡・層間比率）を検証可能な受入基準として明示（PBT 重点箇所と接続）
- [x] 非機能制約（トークン推測困難性・逐次保存・モバイルファースト等）をストーリー/制約として反映

---

## ストーリー分解アプローチの選択肢（トレードオフ）

| アプローチ | 概要 | 向いているケース | 本プロジェクトでの示唆 |
|---|---|---|---|
| **Persona-Based** | ユーザー種別ごとにストーリーを束ねる | 複数ペルソナが異なる目的を持つ | 参加者/研究者で関心が明確に分かれる本件と相性良 |
| **User Journey-Based** | 参加者の一連の流れ（アクセス→判定→完了）に沿う | 体験フローの連続性が重要 | 参加者体験（25〜35 分）を漏れなく設計しやすい |
| **Feature-Based** | 機能単位（割当・保存・エクスポート等）で分割 | 機能の独立実装を重視 | 後続 Units 分解に接続しやすい |
| **Epic-Based** | 上位エピック → 子ストーリーの階層 | 規模が大きく段階把握が必要 | 中規模の本件ではやや過剰の可能性 |
| **Hybrid** | 上記の組合せ（例: ペルソナ × ジャーニー） | 単一軸では表現しきれない | 参加者はジャーニー、研究者はフィーチャー等 |

---

## 質問（すべて回答してください）

回答方法: 各質問の選択肢から 1 つ選び、`[Answer]:` の後ろに**記号**を記入してください。該当がなければ「Other」を選び自由記述してください。記入後「done」等でお知らせください。

## Question 1
ストーリーの分解アプローチはどれにしますか?

A) Persona-Based（参加者/研究者ごとに束ねる）

B) User Journey-Based（参加者の一連フロー中心）

C) Hybrid: 参加者は User Journey、研究者は Feature-Based

D) Feature-Based（機能単位）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
ペルソナの粒度はどうしますか?（評価者の扱い）

A) 評価者は単一ペルソナ（研究者と合わせて 2 ペルソナ）

B) 評価者を経験・熟達度でサブ分割（例: なぞかけ経験者 / 初心者）+ 研究者（計 3 ペルソナ）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
受入基準（Acceptance Criteria）のフォーマットは?

A) Given-When-Then（Gherkin 形式）

B) 箇条書きチェックリスト形式

C) 両方併用（主要フローは Given-When-Then、補足はチェックリスト）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4
ストーリーの粒度はどのレベルにしますか?

A) 実装可能な小さい単位に細分化（Small 重視、数が多くなる）

B) 中粒度（機能のまとまりごと、バランス重視）

C) 大きめ（エピック中心、詳細は後続設計に委ねる）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 5
研究者（管理者）向けストーリーのスコープはどこまで含めますか?

A) 参加者フローと同等に詳細化（進捗モニタリング・エクスポート・暫定勝率を個別ストーリー化）

B) 参加者フローを優先し、研究者機能は最小限のストーリーに留める

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 6
非機能要件（トークン推測困難性・逐次保存の堅牢性・モバイルファースト・PBT 重点箇所など）はストーリーにどう反映しますか?

A) 各機能ストーリーの受入基準に組み込む（独立した NFR ストーリーは作らない）

B) 横断的な制約・技術ストーリーとして別立てで明示する

C) 両方（受入基準に組み込みつつ、重要な横断制約は別立てでも明示）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 7
「オフライン BT 集計スクリプト」など研究者が CLI/スクリプトで行う作業もユーザーストーリーとして含めますか?

A) 含める（研究者ペルソナのストーリーとして扱う）

B) 含めない（アプリの UI 操作に閉じ、スクリプトは後続の技術設計で扱う）

X) Other (please describe after [Answer]: tag below)

[Answer]: 
