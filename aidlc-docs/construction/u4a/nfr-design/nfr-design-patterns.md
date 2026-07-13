# U4a NFR Design Patterns — token_issue / pool_ingest（+ 管理 API）

U4a-NFR-01〜12 を設計パターン **DP-U4a-NN** に落とす。U1 の DP-01〜08 を前提に、U4a 固有分のみ。案 A′（raw workers API, F-5）の制約に整合。

---

## DP-U4a-01: 認証チョークポイント（単一）
- `on_fetch` の `/admin/*` ディスパッチ**入口に認証ガード関数を 1 箇所**置き、全管理エンドポイントが必ずそこを通る。**認証漏れのエンドポイントを構造的に作れない**。
- `Authorization: Basic` を復号 → `env.ADMIN_BASIC_USER`/`ADMIN_BASIC_PASSWORD` と**定数時間比較**（`hmac.compare_digest`）。不一致は **401 + `WWW-Authenticate: Basic`**。
- **U2/U3 が同じガードを再利用**（後からエンドポイント追加時の安全装置）。
- 対応: U4a-NFR-01/02/05, Q1。

## DP-U4a-02: ログ秘匿の強制点（構造で守る）
- 管理操作用のログは、**トークン生値・本文フィールドを構造的に受け付けない薄いラッパ／規約**を通す（U1 `emit` ベース）。**許可フィールドを `event`/`level`/件数/`item_id`/結果コードに限定**。
- 「呼び出し側の規律」ではなく境界で固定（U1 DP-06「単一発行点」の延長）。`Item.body` は未公表研究刺激のためログ経路（wrangler tail 等）にも出さない。
- 対応: U4a-NFR-03/09, Q2。

## DP-U4a-03: 原子投入（DP-01 流用）
- `insert_items` / `insert_tokens` は **D1 batch で all-or-nothing**。事前検証・ガードを通過してから 1 batch。半端投入・部分発行なし（`save_pair_sequence` の実 D1 実証イディオム）。
- 対応: U4a-NFR-06, BR-U4a-09。

## DP-U4a-04: 冪等 upsert + 凍結ガード（read-then-write, ロックなし）
- 未参照 `item_id` は `ON CONFLICT(item_id) DO UPDATE`（べき等）、新規は INSERT。**`pairs`/`judgments` 参照済み item への UPDATE は拒否**（投入全体中断）。
- ガードの read-then-write は**ロックなしで許容**（参照集合の取得を投入 batch 直前に行い窓を最小化）。同時投入のスナップショット競合は許容（U1 Q8 と同型判断。投入=実験開始前の単独研究者運用のため前提がさらに弱い）。理論上の TOCTOU は記録に留める。
- 対応: U4a-NFR-07, BR-U4a-03/04, Q3。

## DP-U4a-05: 充足判定の単一実装
- **`pool_sufficiency(items, params) -> SufficiencyResult`** を `backend/domain/` の純粋関数として単一実装。`SufficiencyResult = { ok: bool, shortfalls: list[str] }`（三点セット BR-U4a-05 のどれがどれだけ不足かの内訳）。
- **ingest（warn）と issue（gate）が同一関数を呼び、同一の `ok`/`shortfalls` を各文脈で解釈**（warning ログ / error+拒否）。判定式の 2 箇所別実装＝述語乖離を構造的に排除。PBT-03 対象（境界値・反例探索）。
- 対応: U4a-NFR-10, BR-U4a-05/12, Q4。

## DP-U4a-06: 発行ゲート + 衝突リトライ
- token_issue: **① `pool_sufficiency` ゲート（未達→error+発行拒否, BR-U4a-12）→ ② 既存トークン集合で衝突事前排除 → ③ batch 投入 → ④ PK 衝突なら全体再生成リトライ**（BR-U4a-06）。発行トークンは `status=unused`, `issued_at`。
- 対応: U4a-NFR-08, BR-U4a-06/10/12。

## DP-U4a-07: 統一エラー封筒
- 管理 API のレスポンスは**統一封筒**: 業務エラー（拒否・ゲート未達）は **200 + `ok=false` + 内訳**（`rejected`/`sufficiency_warnings`/`gate_errors`）。**認証失敗のみ HTTP 401**（+ `WWW-Authenticate`）。
- CLI は内訳を人間可読に表示、**終了コード規約**（`rejected`/`gate_errors` あり = 非ゼロ）。個別 HTTP ステータス（422 等）は本文脈（自作 CLI 一つの内部 API）で価値が薄いため不採用。
- 対応: U4a-NFR-01, Q5, FD（CLI 終了コード）。

---

## 導入しない設計部品（意図的な非採用・U1 と同方針）
| 部品 | 非採用理由 |
|---|---|
| キャッシュ | `list_items`/`pool_sufficiency` は小規模で瞬時。 |
| キュー | 同期・小規模、非同期投入なし。 |
| サーキットブレーカ / リトライ基盤 | 外部依存の連鎖なし。発行の衝突リトライは局所的で十分。 |
| 分散ロック | read-then-write はロックなし許容（DP-U4a-04）。 |
