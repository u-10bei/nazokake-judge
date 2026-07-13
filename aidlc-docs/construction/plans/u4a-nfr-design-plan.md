# U4a NFR Design Plan — token_issue / pool_ingest（+ 管理 API）

**ユニット**: U4a。NFR Requirements（U4a-NFR-01〜12）を設計パターン（DP-U4a）と論理コンポーネント（LC-U4a）に落とす。技術非依存寄りだが、案 A′（raw workers API）の制約に整合させる。
**前提（既決）**: Basic 認証・単一資格情報（U4a-NFR-01）／ログにトークン・本文を出さない（03）／原子・冪等・凍結・発行ゲート（06〜08）／`pool_sufficiency` 単一実装（10）／PBT+integration（11）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-design-patterns.md`（DP-U4a-NN）/ `logical-components.md`（LC-U4a-NN + 依存方向）を生成します。

---

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-13）
- [x] `construction/u4a/nfr-design/nfr-design-patterns.md`（DP-U4a-01〜07: 認証チョークポイント・ログ秘匿・原子投入・冪等 upsert+凍結・充足判定単一実装・発行ゲート・統一エラー封筒）
- [x] `construction/u4a/nfr-design/logical-components.md`（LC-U4a-01〜06 + DataContract 拡張・依存方向）

**回答サマリ**: 全 5 問 ★A。適用性評価（キャッシュ/キュー/CB/ロック=N/A）同意。

## 設計パターン適用性評価（U4a）
| 論点 | 適用 | 方針 |
|---|---|---|
| **認証/認可** | **適用** | Basic 認証ガード（単一チョークポイント）。→ Q1 |
| **秘匿/データ保護** | **適用** | ログ秘匿の強制点（トークン・本文非出力）。→ Q2 |
| **一貫性/原子性** | **適用** | D1 batch（DP-01 流用）+ 凍結ガードの read-then-write。→ Q3 |
| **純粋ドメインロジック** | **適用** | `pool_sufficiency` 純粋関数（単一実装）。→ Q4 |
| **エラー処理契約** | **適用（最小限）** | 管理 API の統一エラー封筒。→ Q5 |
| キャッシュ/キュー/CB/ロック | **N/A** | 小規模・同期・単独研究者（U1 と同方針）。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【認証】Basic 認証ガードの配置
- **★A（推奨）**: **単一チョークポイント** — `on_fetch` の `/admin/*` ディスパッチ入口に**認証ガード関数を1箇所**置き、全管理エンドポイントがそこを通る。認証漏れのエンドポイントを構造的に作れない。U2/U3 が同じガードを再利用（U4a-NFR-01）。
- **B**: 各エンドポイントハンドラ内で個別に認証チェック。→ 追加時の付け忘れリスク。

[Answer]: A

### Q2【秘匿】ログ秘匿の強制点
- **★A（推奨）**: **秘匿の強制点を1箇所に集約** — 管理操作用のログは、トークン生値・本文フィールドを**構造的に受け付けないヘルパ／規約**（例: `emit` を件数・`item_id`・結果コードのみで呼ぶ薄いラッパ、または「admin ログに token/body キーを渡さない」を LC 境界で固定）。U1 の DP-06「単一発行点」の思想と一致（U4a-NFR-03）。
- **B**: 各呼び出し側の規律に委ねる（生値を渡さないよう都度注意）。→ 漏出の温床。

[Answer]: A

### Q3【一貫性】凍結ガード + upsert の read-then-write 整合
凍結ガード（BR-U4a-03）は「参照済み item_id 集合を読む → その後 batch で upsert」の read-then-write。
- **★A（推奨）**: **ロックなしで許容**（単独研究者・小規模・投入は実験開始前の運用）。参照集合の取得を**投入 batch の直前**に行い窓を最小化。同時投入のスナップショット競合は許容（U1 Q8 のスナップショット競合許容と同方針）。理論上の TOCTOU は運用形態上ほぼ発生しない。
- **B**: 参照読取と投入を単一トランザクション/ロックで直列化。→ D1 の粒度に対し過剰、複雑さ増。

[Answer]: A

### Q4【純粋ロジック】pool_sufficiency の LC 位置づけ・戻り値
- **★A（推奨）**: **`backend/domain/` の純粋関数** `pool_sufficiency(items, params) -> SufficiencyResult`。`SufficiencyResult = { ok: bool, shortfalls: list[str] }`（三点セットのどれが不足かを内訳で返す）。ingest（warn）と issue（gate）が同一関数を呼び、`ok`/`shortfalls` を各文脈（warning ログ / error+拒否）で解釈（U4a-NFR-10）。PBT 対象。
- **B**: 判定を管理エンドポイント内にインライン実装。→ 単一実装要件（U4a-NFR-10）に反する。

[Answer]: A

### Q5【エラー契約】管理 API の統一エラー封筒
- **★A（推奨）**: 管理 API のレスポンスは**統一封筒**で `ok` + 詳細（`IngestResult` の `rejected`/`sufficiency_warnings`、`TokenIssueResult` の `gate_errors`）を返す。**認証失敗は HTTP 401 + `WWW-Authenticate: Basic`**（本文は簡素）。業務エラー（拒否・ゲート未達）は 200 + `ok=false` + 内訳（CLI が内訳を表示できる）。
- **B**: 各エラーを個別の HTTP ステータス（422 等）で返す。→ CLI 側のハンドリングが煩雑、内訳伝達が弱い。

[Answer]: A

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-design-patterns.md` / `logical-components.md` を生成 → 標準 2 択（Request Changes / Continue → Infrastructure Design）。
