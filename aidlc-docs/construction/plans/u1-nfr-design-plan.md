# U1 NFR Design Plan — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**目的**: U1 NFR Requirements（U1-NFR-01〜15 / TSD-01〜08）を、設計パターンと論理コンポーネントに落とす。
**前提（既決・再質問しない）**: 案 A′（Cloudflare Python Workers/Pyodide + FastAPI + D1、Hypothesis）。原子的一括保存（U1-NFR-03）、DB 冪等（U1-NFR-04）、128-bit トークン契約（U1-NFR-08）、構造化 JSON ログ（U1-NFR-10）、Hypothesis dev/ci profile + 固定シード（U1-NFR-12〜14）。

このドキュメントは **Part 1（Plan + 質問）**。回答後、承認を経て `nfr-design-patterns.md` / `logical-components.md` を生成します。

---

## 生成予定の成果物 → 生成済み（Part 2 実行済み, 2026-07-12）

- [x] `construction/u1/nfr-design/nfr-design-patterns.md`（DP-01〜08。信頼性・セキュリティ・可観測性・テスト容易性の設計パターン + 要件トレーサビリティ）
- [x] `construction/u1/nfr-design/logical-components.md`（LC-01〜05 + 依存方向図 + 意図的な非採用部品）

**回答サマリ**: 全 5 問 = 推奨デフォルト A。Q1=A(単一 D1 batch 原子確定) / Q2=A(ON CONFLICT DO NOTHING+既存 choice 返却) / Q3=A(schema/ 狭い公開面) / Q4=A(単一ログヘルパ emit) / Q5=A(ステートフル累積ハーネス+α/S 較正ループ共有)

---

## パターンカテゴリの適用性評価（MANDATORY: 全カテゴリを評価）

| カテゴリ | 適用 | 判断根拠 |
|---|---|---|
| **Resilience Patterns** | **N/A** | 高可用性・フェイルオーバー・DR は非目標（NFR-06 / U1-NFR「非目標」）。リトライ/サーキットブレーカ不要。データ保全は逐次保存 + 原子的ペア列確定で足りる。 |
| **Scalability Patterns** | **N/A** | 小規模（総数十名・同時数名, NFR-01）。スケーリング機構・負荷分散・キャパシティ計画不要。 |
| **Performance Patterns** | **最小限** | SLO なし（U1-NFR-01）。キャッシュ/マテリアライズは不要（`derive_exposure` は毎回集計で瞬時, U1-NFR-02）。→ 設計上の能動パターンはほぼ無し。Q は立てない（既決）。 |
| **Security Patterns** | **適用** | パラメータ化クエリ（U1-NFR-07）、トークン契約（U1-NFR-08）。→ 実装パターンを Q で確定。 |
| **Observability Patterns** | **適用** | 構造化 JSON ログ（U1-NFR-10/11）。→ ログ発行パターンを Q で確定。 |
| **Reliability/Integrity Patterns** | **適用** | 原子的一括保存（U1-NFR-03）、DB 冪等（U1-NFR-04）。→ 原子化境界・冪等セマンティクスを Q で確定。 |
| **Testability Patterns** | **適用** | PBT ハーネス（P-1 累積・P-5 オラクル, U1-NFR-12〜15）。→ ハーネス形を Q で確定。 |
| **Logical Components（queue/cache/circuit breaker 等）** | **なし** | 上記 N/A のため専用インフラ論理部品は導入しない。U1 の論理部品は「純粋関数境界（AssignmentEngine）／唯一の I/O 境界（Repository）／データ契約（schema）／ログヘルパ」に限る。→ `logical-components.md` に明記（Q なし）。 |

---

## 質問（すべて回答してください）

回答方法: 記号を `[Answer]:` の後ろに記入。各問に推奨デフォルト（★）付き。合意なら記号だけで可。

## Question 1 — セッション・ブートストラップの原子化境界（信頼性）
セッション開始時に作る **Session 行 + PairSequence（全ペア）+ `exposure_snapshot`** をどの単位で原子化しますか?

A) ★ **全部を 1 つの D1 batch で all-or-nothing** に確定（Session と PairSequence を分離不能に。半端な状態が原理的に生じない）

B) Session 行を先に確定 → PairSequence を別 batch（部分状態を許容し、起動時の整合チェックで補修）

X) Other

[Answer]:

## Question 2 — 判定冪等の衝突セマンティクス（信頼性 / API 契約）
重複判定送信（BR-08）時、DB 側の振る舞いとサーバ応答は?

A) ★ **`INSERT ... ON CONFLICT DO NOTHING`（既存維持）+ サーバは 200 で既存 `choice` を返す**（冪等かつ可観測。クライアント再送が既存値を確認できる）

B) `ON CONFLICT DO NOTHING` のみ（応答は単純 OK、既存値は返さない）

X) Other

[Answer]:

## Question 3 — モデル契約の抽象化パターン（Pydantic フォールバック耐性）
TSD-02 の「Pydantic v2 が Pyodide で不可なら pure-Python へフォールバック」の波及をどう抑えますか?

A) ★ **契約を `schema/` の単一モジュールに集約**し、上位は「モデル型 + 明示バリデート関数」という**狭い公開面のみ import**。フォールバック時は `schema/` 内の実装差し替えで吸収（公開面は不変 = 上位に波及しない）

B) 今は Pydantic を直接利用してよい。フォールバックが必要になった時点でリファクタする（先行抽象化しない）

X) Other

[Answer]:

## Question 4 — 構造化ログの発行パターン（可観測性）
JSON ログの共通形を?（U1-NFR-10/11）

A) ★ **単一ログヘルパ**（例: `emit(event, level, **fields)`）で JSON を stdout。標準フィールド = `event`/`level`/`ts`/`unit` + 文脈（`token` or `session_id`, `item_id` 等）。相関キーは `session_id`/`token`

B) 各所で個別に JSON を出力（共通ヘルパを設けない）

X) Other

[Answer]:

## Question 5 — PBT ハーネスのパターン（テスト容易性）
P-1（S セッション累積シミュレーション）と P-5（`updated_exposure` を `derive_exposure` のオラクルに）の検証ハーネス形は?

A) ★ **ステートフル・シミュレーションハーネス**: 固定シードで S セッションを逐次生成し、各回 `updated_exposure` で露出をフィードバック。都度 `derive_exposure` との一致（P-5）を確認しつつ、最終露出で P-1 述語 `max−min ≤ max(2, α×mean)` を評価。`tests/pbt/` に受入基準（XC-01/P-1/P-5）を name/docstring 明記

B) P-1 と P-5 を独立したプロパティテストに分離（累積ハーネスは共有しない）

X) Other

[Answer]:

---

## 回答後の進め方
1. 回答分析（曖昧・矛盾があれば追質問を本ファイルに追記、GATE 維持）。
2. `nfr-design-patterns.md` / `logical-components.md` を生成。
3. 標準 2 択完了メッセージ（Request Changes / Continue → Infrastructure Design）を提示。
