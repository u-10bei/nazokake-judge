# U1 Functional Design Plan — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**スコープ**: 技術非依存の業務ロジック・ドメインモデル・業務ルール。インフラ関心（D1 接続の具体等）は Infrastructure Design。
**重点**: XC-01 割当（露出均衡・層間比率, PBT-03）、XC-02 状態ラウンドトリップ（PBT-02）、層ラベル（US-R06 前提）。

このドキュメントは Part 1（Plan + 質問）。回答後、承認を経て business-logic-model / business-rules / domain-entities を生成します。

---

## 生成予定の成果物（承認後）→ 生成済み

- [x] `construction/u1/functional-design/domain-entities.md`（エンティティ・関係）
- [x] `construction/u1/functional-design/business-logic-model.md`（割当アルゴリズム・露出カウント導出・状態シリアライズ）
- [x] `construction/u1/functional-design/business-rules.md`（制約・検証・エラー）
- [x] Testable Properties セクション（business-logic-model.md §5。P-1〜P-7。XC-01→PBT-03, XC-02→PBT-02）

**回答サマリ**: Q1=A(重み付きランダム) / Q2=A(層間率パラメータ,暫定0.65) / Q3=X(本番40/練習3/Likert10) / Q4=B(サーバシード+露出スナップショット) / Q5=A(導出方式+非アクティブ除外) / Q6=A(ベストエフォート+構成不能は事前検証) / Q7=A(全確定横断) / 追加1(セッション内制約) / 追加2(位置カウンターバランス)

---

## 参考: 想定ドメインエンティティ（Q6 で確認）

- **Item**（作品）: `item_id`, `layer`（pro/ai/edit/rule 必須）, 本文参照
- **Token**（参加者トークン）: `token`, `status`（unused/in_progress/completed）
- **Session**: token に 1:1、`phase`, 進捗
- **PairSequence**: session に確定保存されるペア列（順序付き, 各要素 `pair_id, item_a, item_b, is_practice`）
- **Judgment**: `token, pair_id, choice(A/B)`（冪等）
- **LikertResponse** / **SurveyResponse**
- **ExposureCounts**（導出 or 保持: H-2）

---

## 質問（すべて回答してください）

回答方法: 記号を `[Answer]:` の後ろに記入。該当なしは「Other」。研究設計の値は暫定でも可（後で調整可能、Negotiable）。

## Question 1
露出均衡（各項目の露出回数を均す）を実現するアルゴリズム方針は?

A) 重み付きランダム抽選（露出の少ない項目ほど選ばれやすい重みを与え、シードで決定論化）

B) 貪欲法（各ステップで最も露出の少ない項目を優先的にペアに組む）

C) ラウンドロビン + ランダム化（全項目を巡回しつつ相手をランダム選択）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
層間ペア（異なる出自層どうしの比較）の扱いは?

A) 目標割合を設定（例: 全ペアの一定割合を層間ペアにする）。具体値は Other か補足で指定

B) 特定の層ペアを重視（例: プロ層 × 他層 を必ず一定数含める）

C) 層は割当では区別せず露出均衡のみ重視（層間比率は集計時に事後確認）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
1 セッションの構成（具体値）は? 暫定でも可。

A) 目安: 本番ペア 40 / 練習ペア 3 / ブリッジ Likert 5 項目（標準的な想定）

B) 目安: 本番ペア 30 / 練習ペア 2 / ブリッジ Likert 3 項目（短め）

C) 未定（設計を「パラメータ化」し、具体値は実験計画確定時に設定）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4
割当のシード（決定論性）はどう扱いますか?

A) トークンごとに固定シード（同一トークンは常に同じペア列 → 再開時の再現・XC-02 と整合）

B) セッション開始時にサーバ側で乱数シードを生成し保存（保存値で再現）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 5
露出カウントの実現方式は?（申し送り H-2）

A) 導出方式: 保存済みペア列（確定分）から毎回集計して算出（単一の真実、推奨）

B) 保持方式: 専用カウンタテーブルを更新

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 6
ペア割当のエッジケース方針は?（プール規模 90〜95 件で通常は充足する前提）

A) 露出目標を満たせない場合はベストエフォート（可能な範囲で均衡）+ ログ警告

B) 事前検証で不足を検出したらセッション開始を拒否（データ品質優先）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 7
既に完了した他トークンの回答は、露出カウント（次セッションの割当）に算入しますか?

A) 算入する（全確定回答を横断して露出均衡を図る → XC-01 の全体不変条件と整合）

B) 算入しない（セッション単位で独立に均衡）

X) Other (please describe after [Answer]: tag below)

[Answer]: 
