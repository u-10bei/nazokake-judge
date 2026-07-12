# U1 NFR Requirements Plan — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**目的**: U1 の非機能要件を確定し、技術スタックの具体値を固定する。
**前提（既決・再質問しない）**:
- アーキ = 案 A′：静的フロント + **Cloudflare Python Workers（FastAPI）+ D1**、PBT = **Hypothesis**（案 B はフォールバック温存）。
- プロジェクト NFR：NFR-01 小規模（総数十名・同時数名）／NFR-04 基本セキュリティ衛生必須（HTTPS 強制・トークン推測困難・SQLi 対策・CORS）／NFR-06 可用性作り込み不要／NFR-07 PBT Partial（強制 PBT-02/03/07/08/09）。
- U1 業務ルール：BR-08 判定冪等、BR-11 層ラベル必須、BR-12 パラメータ化クエリ、BR-06 ベストエフォート+ログ警告、BR-05 構成不能は事前検証。

このドキュメントは **Part 1（Plan + 質問）**。回答後、承認を経て `nfr-requirements.md` / `tech-stack-decisions.md` を生成します。

---

## 生成予定の成果物 → 生成済み（Part 2 実行済み, 2026-07-12）

- [x] `construction/u1/nfr-requirements/nfr-requirements.md`（U1-NFR-01〜15。性能・信頼性・セキュリティ衛生・可観測性・保守/テスト容易性 + 拡張適合サマリ）
- [x] `construction/u1/nfr-requirements/tech-stack-decisions.md`（TSD-01〜08。言語/ランタイム・モデル層・DB アクセス・冪等・トークン契約・ロギング・PBT・コード配置）

**回答サマリ**: 全 8 問 = 推奨デフォルト A。Q1=A(Pydantic v2+検証+フォールバック) / Q2=A(SLO なし) / Q3=A(原子的一括保存) / Q4=A(DB 冪等) / Q5=A(128-bit トークン) / Q6=A(JSON ログ標準出力) / Q7=A(Hypothesis ローカル/CI・dev/ci profile・固定シード) / Q8=A(スナップショット競合許容)

---

## スコープの考え方（なぜ質問が少なめか）

U1 は「土台」で、規模・セキュリティ方針・PBT モードは**プロジェクト要件で既に確定**しています。したがって本ステージの真の論点は、**案 A′ 特有の技術制約を U1 の設計へ落とすとき**に現れる次の点に絞られます。各問には推奨デフォルト（★）を付けたので、合意なら記号だけでも構いません（研究/実装値は Negotiable）。

---

## 質問（すべて回答してください）

回答方法: 記号を `[Answer]:` の後ろに記入。該当なしは `X`（Other）に説明を添える。

## Question 1 — モデル層（Pydantic）とランタイム制約 ★重要
Cloudflare Python Workers は **Pyodide** 上で動作します。C-SCHEMA は Pydantic モデルを共有契約に据える想定ですが、Pydantic v2 のコアはコンパイル拡張（Rust/pydantic-core）で、Pyodide/Workers での可用性は要検証です。方針は?

A) ★ **Pydantic v2 を第一候補**とし、Workers(Pyodide) での可用性を **Infrastructure Design / Code Generation で検証**。不可なら pure-Python 手段へフォールバックする（フォールバック先を tech-stack-decisions に明記）

B) 最初から **Pyodide 互換が確実な軽量手段**（`dataclasses` + 手書きバリデーション、または pydantic v1 pure-python）を採用し、リスクを取らない

C) スキーマ定義（Pydantic）は **ローカル/scripts 用の共有ライブラリ**として使い、Worker の I/O 境界は最小限の手書き検証に割り切る（Worker 内で重い検証を持ち込まない）

X) Other

[Answer]:

## Question 2 — 性能目標（セッション開始のペア生成 + 露出導出）
`generate_pairs`（プール 90〜95・本番 40 ペア）+ `derive_exposure`（全確定ペア列を毎回集計）はセッション開始時に走ります。小規模（NFR-01）ですが目標の置き方は?

A) ★ **明示的な数値 SLO は置かない**。小規模ゆえ体感即時で十分。非公式目安「セッション開始 < 1s」を tech-stack-decisions に参考記載

B) **明示 SLO を置く**（例: ペア生成 p95 < 500ms、露出導出 < 200ms）。値は補足で指定

C) 未定（Infrastructure Design で D1 レイテンシ計測後に決める）

X) Other

[Answer]:

## Question 3 — PairSequence 一括保存の原子性（信頼性）
ペア列はセッション開始時に一括確定保存します（順序付き）。途中失敗で「半端なペア列」が残ると再開・露出導出が壊れます。原子性の要件は?

A) ★ **原子的に確定**（全ペアを 1 バッチ/トランザクションで保存、部分書き込みを許さない）。D1 の batch/transaction を用いる（具体は Infrastructure/Code Gen）

B) ベストエフォート保存 + 起動時の**整合性チェックで不完全セッションを検出・破棄/再生成**

C) その他

[Answer]:

## Question 4 — 判定冪等（BR-08）の実現層
(`token`,`pair_id`) の冪等（重複送信は 1 件）をどこで保証しますか?

A) ★ **DB 一意制約 + 冪等 UPSERT/INSERT（衝突時無視）**でサーバ・DB 側に一本化（アプリ層の競合判定に依存しない）

B) アプリ層で存在チェック後に挿入（一意制約は補助）

X) Other

[Answer]:

## Question 5 — トークン推測困難性（NFR-04 / XC-03）の具体エントロピー
Token（US-R05 で U4a 発行、モデルは U1）の最低エントロピーの具体値は? ※生成は U4a だが、**契約（長さ/エントロピー/文字集合）は U1 の schema/ で規定**するため U1 で確定します。

A) ★ **128-bit 以上**（例: `secrets.token_urlsafe(16)` → 22 文字前後の base64url）

B) 256-bit（`token_urlsafe(32)`）

C) その他（値を指定）

[Answer]:

## Question 6 — 可観測性・ログ（BR-06 ベストエフォート警告 / BR-05 事前検証）
露出目標未達の警告や構成不能検出などをどのレベルで出しますか?（小規模前提）

A) ★ **構造化ログ（JSON）を標準出力**へ。Workers/wrangler のログで足りる範囲。専用の監視基盤・アラートは持たない（NFR-06 と整合）

B) 構造化ログ + **軽量な集約先**（例: Workers Analytics/Logpush 等）まで用意

C) その他

[Answer]:

## Question 7 — PBT（Hypothesis）実行方針
PBT は Hypothesis 確定。P-1 は「S セッション累積シミュレーション後の統計的不変条件」で、確率的な性質を含みます。実行方針は?

A) ★ **ローカル/CI で実行**（Worker ランタイム外の pure-Python として `generate_pairs` 等を検証）。統計的プロパティ（P-1）は Hypothesis の `@example`/明示シードと**固定シードの反復試行**で決定論的に回し、`deadline` は緩め/無効化。反例時はシード+縮小入力を出力（PBT-08）

B) Hypothesis の既定設定に寄せる（examples 数・deadline はデフォルト）

C) その他（examples 数・deadline・シード方針を指定）

[Answer]:

## Question 8 — 同時セッション開始時の露出スナップショット競合（信頼性・任意）
同時に数名がセッション開始すると、各々が「その時点の導出露出」を読んでスナップショット保存します。厳密な直列化は小規模では過剰かもしれません。方針は?

A) ★ **許容する**（軽微な露出重複は BR-06 ベストエフォートの範囲。P-1 は累積で収束）。特別なロックは設けない

B) セッション開始を**軽く直列化**（トークン単位のロック等）してスナップショットの一貫性を上げる

X) Other

[Answer]:

---

## 回答後の進め方
1. 回答を分析（曖昧・矛盾があれば追加質問を本ファイルに追記、GATE 維持）。
2. 明確化後、`nfr-requirements.md` と `tech-stack-decisions.md` を生成。
3. 標準 2 択完了メッセージ（Request Changes / Continue → NFR Design）を提示。
