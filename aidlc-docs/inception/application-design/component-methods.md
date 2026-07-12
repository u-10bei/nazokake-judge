# Component Methods — nazokake-judge

**注記**: 高レベルのメソッド署名・入出力型のみ。**詳細な業務ルールは Functional Design（per-unit, CONSTRUCTION）で定義**する。型は Python / Pydantic を想定（案 A′）。ここでの署名は設計意図の共有が目的で、最終的なシグネチャは実装で調整され得る（Negotiable）。

---

## C-SVC-SESSION: SessionService

| メソッド | 署名（概略） | 目的 |
|---|---|---|
| `start_or_resume` | `(token: str) -> SessionView` | トークン検証 → 状態判定。未使用なら AssignmentEngine でペア列を確定・保存し開始、進行中なら再開位置を返す、完了なら完了状態を返す。 |
| `get_state` | `(token: str) -> SessionView` | 現在の進捗・次に提示すべきペア・残数を返す。 |
| `mark_complete` | `(token: str) -> None` | 全工程完了時にセッションを完了へ遷移。 |

- `SessionView`: `{ status: "unused"|"in_progress"|"completed", next_pair: PairView|None, progress: {done:int, total:int}, phase: "instruction"|"practice"|"judging"|"likert"|"survey"|"done" }`

## C-SVC-RESPONSE: ResponseService

| メソッド | 署名（概略） | 目的 |
|---|---|---|
| `submit_judgment` | `(token: str, pair_id: str, choice: "A"|"B") -> SubmitResult` | ペア判定を冪等保存（同一 token×pair は 1 件）。練習試行は集計対象外。 |

- `SubmitResult`: `{ saved: bool, duplicate: bool, next_pair: PairView|None }`
- **H-3（Functional Design で確定）**: 練習/本番の判定は **`is_practice` をクライアントから受け取らず、サーバが保存済みペア列上の位置から判定**する（クライアント申告は信用しない。US-P02 の集計正しさのため）。上記署名は当初 `is_practice: bool` を含めていたが削除した。あわせて **XC-02 のラウンドトリップ対象**（`SessionView` か DB 行の復元か）を Functional Design で定義する。詳細は application-design.md §8。

## C-SVC-SURVEY: SurveyService

| メソッド | 署名（概略） | 目的 |
|---|---|---|
| `submit_likert` | `(token: str, item_id: str, rating: int) -> None` | ブリッジ Likert 保存（BT 較正アンカーとして区別）。 |
| `submit_survey` | `(token: str, answers: SurveyAnswers) -> None` | 事後アンケート保存。 |

- `SurveyAnswers`: 暫定構成（経験/熟達度・ドメイン馴染み/経験様態・重視観点・年代）。プール確定後に確定。

## C-SVC-ADMIN: AdminService

| メソッド | 署名（概略） | 目的 |
|---|---|---|
| `get_progress` | `() -> ProgressView` | 発行/開始/完了数・総回答数。 |
| `get_provisional_winrates` | `() -> list[WinrateRow]` | 作品ごとの対戦数・暫定勝率（簡易・非 BT）。 |

- `WinrateRow`: `{ item_id: str, layer: str, matches: int, wins: int, winrate: float }`

## C-SVC-EXPORT: ExportService

| メソッド | 署名（概略） | 目的 |
|---|---|---|
| `export` | `(format: "csv"|"json") -> ExportBundle` | schema/ の Pydantic モデル準拠でエクスポート。形式バージョンを付与。US-R04 入力と一致。 |

- `ExportBundle`: `{ schema_version: str, judgments: [...], likert: [...], surveys: [...] }`

## C-DOM-ASSIGN: AssignmentEngine（XC-01・純粋関数）

| メソッド | 署名（概略） | 目的 |
|---|---|---|
| `generate_pairs` | `(pool: list[Item], exposure: ExposureCounts, seed: int, session_size: int) -> list[Pair]` | 露出均衡（全体不変条件）＋層間比率を満たすセッション分のペア列を生成。**純粋関数・副作用なし**。 |
| `updated_exposure` | `(exposure: ExposureCounts, pairs: list[Pair]) -> ExposureCounts` | 生成ペアで露出カウントを更新した新しいカウントを返す（純粋）。 |

- `Item`: `{ item_id: str, layer: "pro"|"ai"|"edit"|"rule" }`（層ラベル必須, US-R06）
- `ExposureCounts`: `{ item_id: -> count }`
- **PBT-03**: `generate_pairs` の出力露出偏りが許容範囲・層間比率が指定割合、を不変条件として検証。

## C-REPO: D1 Repository（抜粋）

| メソッド | 署名（概略） | 目的 |
|---|---|---|
| `get_token` / `mark_token_*` | `(token) -> TokenRow` 他 | トークン状態管理。 |
| `read_exposure_counts` | `() -> ExposureCounts` | 現在の露出カウント読取（SessionService が使用）。 |
| `save_pair_sequence` | `(token, pairs) -> None` | 確定ペア列の保存（Q3=A）。 |
| `insert_judgment` | `(token, pair_id, choice) -> bool` | 冪等挿入（重複は false）。 |
| `list_items` | `() -> list[Item]` | プール（層ラベル付き）取得。 |

- すべてパラメータ化クエリ（SQLi 対策・XC-03）。

## C-AUTH: AuthMiddleware

| メソッド | 署名（概略） | 目的 |
|---|---|---|
| `require_basic_auth` | `(request) -> None | 401` | 管理エンドポイントの Basic 認証検査。 |

## Scripts（`scripts/`）

| コンポーネント | エントリ | 署名（概略） |
|---|---|---|
| C-SCRIPT-TOKEN | `issue_tokens` | `(count: int) -> list[TokenUrl]` |
| C-SCRIPT-POOL | `ingest_pool` | `(records: list[ItemInput]) -> IngestResult`（層ラベル欠落は拒否） |
| C-SCRIPT-BT | `aggregate_bt` | `(export: ExportBundle) -> BTResult`（全作品の BT スコア） |
