# U5 NFR Design Plan — 出題停止（item retirement）

**ユニット**: U5。U5-NFR-01〜13 を設計パターン **DP-U5-NN** と論理コンポーネント **LC-U5-NN** に落とす。
**前提（既決）**: FD 全 6 問 A（BR-U5-01〜13）/ NFR Req 全 5 問 A（U5-NFR-01〜13 / TSD-U5-01〜08）。**`list_items()` 凍結 + `list_active_items()` 新設**（BR-U5-02）・**Likert ターゲットの保存化 + 単一アクセサ**（BR-U5-04）・**凍結ガードとの経路分離**（BR-U5-05）・**U3/U4b 無変更・`EXPORT_FORMAT_VERSION` 1.0.0 据え置き**。

**性格**: U5 の設計は「**要件の両輪を構造で守る**」に集約される。DP は新奇な部品の導入ではなく、**既存部品の分割と集約**の設計。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-design-patterns.md`（DP-U5-NN）/ `logical-components.md`（LC-U5-NN + 依存方向）を生成します。

## 生成予定の成果物（Part 2）
- [ ] `construction/u5/nfr-design/nfr-design-patterns.md`（DP-U5-NN + 非採用部品表）
- [ ] `construction/u5/nfr-design/logical-components.md`（LC-U5-NN + 依存方向）

---

## 調査で判明した設計上の前例（★重要）

**`Session` には既に「JSON カラム ↔ 型付きフィールド」の前例がある**:

| 項目 | 既存の `exposure_snapshot` | U5 の `likert_targets`（同型の問題） |
|---|---|---|
| DDL | `exposure_snapshot TEXT NOT NULL DEFAULT '{}'` | `likert_targets TEXT`（NULL 許容） |
| モデル | `Session.exposure_snapshot: dict[str, int]` | ? → **Q1** |
| 読み | `get_session` が `json.loads` → `Session.model_validate` | ? |
| 書き | `save_pair_sequence(session, pairs)` が**同一 batch で INSERT** | ? |
| 目的 | 監査リプレイ用（Q4=B） | 開始時確定の保存（BR-U5-04） |

→ **`likert_targets` はこの前例に従えるか**が Q1 の核心。

---

## 設計パターン適用性評価（U5）
| 論点 | 適用 | 方針 |
|---|---|---|
| **読み取り経路の分割**（要件の両輪を構造で守る） | **適用（最重要・U5 固有）** | `list_items()` 凍結 + `list_active_items()` 新設。呼び出し先を LC で固定。→ Q2 |
| **導出状態の保存化 + 単一アクセサ** | **適用（核心）** | Likert ターゲットを開始時確定・保存。3 箇所の導出を 1 アクセサに集約。→ Q1 / Q3 |
| **冪等性の SQL 化** | **適用** | 冪等を SQL の WHERE 句で作る（アプリ側分岐に頼らない）。→ Q4 |
| **経路分離によるガードの保全** | **適用** | 凍結ガード（`insert_items`）と廃止（別関数・別ルート）を分離。→ LC で固定 |
| キャッシュ / キュー / CB / ロック / スケール | **N/A** | 列追加 2 本・UPDATE 数件・プール約 95 件。→ Q5 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【★核心】`likert_targets` の型の置き場と**保存の原子性**
FD では「型の置き場は NFR Design に委ねる」と保留した論点。**`exposure_snapshot` の前例**が判断材料。

- **★A（推奨）**: **`Session.likert_targets: list[str] | None` をモデルに載せる**（`exposure_snapshot` と同じ扱い）。`get_session` で `json.loads`、**`save_pair_sequence` の同一 batch で INSERT**。
  - **原子性が本命の理由**: `save_pair_sequence` は **Session + PairSequence を単一 batch で all-or-nothing 保存**する既存設計（TSD-03: 「半端なペア列を原理的に生じさせない」）。**Likert ターゲットを同じ batch に載せれば「ペア列は保存されたが Likert ターゲットは未保存」という中間状態が原理的に生じない**。別経路で保存すると、その窓が新設される（＝BR-U5-04 の保証に穴）。
  - **前例との一貫性**: `exposure_snapshot`（JSON カラム ↔ 型付きフィールド）と完全に同型。読み書きのイディオムを増やさない。
  - **PBT-02（U5-NFR-07）が自然に載る**: ラウンドトリップは `Session` モデル経由で検証でき、**XC-02（セッション状態のラウンドトリップ）の対象に自然に入る**。
  - `extra="forbid"` ゆえ `get_session` の SELECT 列に `likert_targets` を追加する必要がある（既存の明示列指定の流儀どおり）。
- **B**: `Session` に載せず **Repository が JSON を直接読み書き**（`get_likert_targets_raw(token)`）。→ 型契約は広がらないが、(i) **保存の原子性を別途担保する必要**、(ii) `exposure_snapshot` と扱いが割れてイディオムが 2 つになる、(iii) PBT-02 / XC-02 の対象から外れる。

[Answer]:

### Q2【読み取り経路の分割】`list_active_items()` の配置と呼び出し先の固定
- **★A（推奨）**: **`Repository.list_active_items()` を新設**（`SELECT ... FROM items WHERE retired_at IS NULL`）。**`list_items()` は SELECT 列・WHERE ともに一切変更しない**（凍結）。**LC レベルで呼び出し先を固定**する:

  | 呼ぶ関数 | 呼び出し元 |
  |---|---|
  | **`list_active_items()`** | `session.start_or_resume`（新規セッションのペア生成・Likert ターゲット選定）／`admin.api` の充足判定 2 箇所（ingest の warn / issue のゲート） |
  | **`list_items()`（全件）** | `build_view` の `bodies` 写像／旧セッションの Likert 導出フォールバック |
  | **SQL 直参照（全件）** | `read_export_rows("items")`／winrate 集計 |

  - **ingest 時のマージ後評価**（BR-U4a-05）は **`list_active_items()` ∪ 入力**で行う（入力は新規＝常に active）。
  - **禁止事項を LC の注記に明記**: `list_items()` への active フィルタ追加・`active_only` 引数の新設はいずれも禁止（BR-U5-02）。
- **B**: `list_items(active_only: bool = False)` の 1 関数に統合。→ **既定値の反転や呼び出し漏れで要件の両輪が同時に壊れる**（BR-U5-02 が名指しで禁止）。不採用。

[Answer]:

### Q3【単一アクセサ】`get_likert_targets` をどの層に置くか
現状 `select_likert_targets` の導出は **3 箇所**（`build_view` / `check_complete` / `submit_likert`）。**全箇所を 1 アクセサ経由に統一**する（BR-U5-04）。その置き場を決める。

- **★A（推奨）**: **`backend/participant/session.py` に `get_likert_targets(repo, token, params) -> list[str]`** を置く（参加者サービス層）。
  - 実体は「**保存値があればそれ / なければ `list_items()`（全件）から導出**」のオーケストレーション＝**Repository（I/O）と domain（純粋選定）の橋渡し**であり、サービス層が正しい置き場。
  - `build_view` / `check_complete` は同一モジュール内。`survey.py` は既に `import ... session as sess` しているため自然に呼べる。
  - `domain/likert.py` の `select_likert_targets`（純粋）は**無改修**（層の逆流を作らない）。
- **B**: `Repository` に置く。→ DB アクセスと**導出ロジック（domain 呼び出し）が混ざる**。Repository は I/O 境界に留めたい（既存方針）。
- **C**: `domain/likert.py` に置く。→ **domain が repo に依存**＝層の逆流。不採用。

[Answer]:

### Q4【冪等性と分類】retire/unretire の実装レベル
- **★A（推奨）**: **冪等性を SQL の WHERE 句で作る**（アプリ側の分岐に頼らない）:
  - 廃止: `UPDATE items SET retired_at = ? WHERE item_id IN (...) AND retired_at IS NULL` → **既に廃止済みは自然に no-op**＝**初回の廃止時刻が保持**される（BR-U5-06 を SQL が保証）。
  - 復活: `UPDATE items SET retired_at = NULL WHERE item_id IN (...) AND retired_at IS NOT NULL`。
  - **分類（`retired` / `already_retired` / `not_found`）は UPDATE 直前の SELECT で判定**する（`SELECT item_id, retired_at FROM items WHERE item_id IN (...)`）。取得は **batch 直前・ロックなし**（U4a の凍結ガードと同じ窓最小化方針, U4a Q2=A）。
  - **窓の扱い**: 分類の表示が競合で僅かにずれても**実害はない**（冪等性は WHERE 句が保証しており、分類は報告用）。管理 API は運用者の逐次操作でありロックは過剰。
  - **全パラメータ化**: `IN (...)` は件数分の `?` をバインド（U5-NFR-12）。
- **B**: 事前 SELECT の結果でアプリ側が UPDATE 対象を絞る。→ SELECT と UPDATE の間の窓が**冪等性そのものに影響**する。不採用。

[Answer]:

### Q5【適用性評価の確認】
- **★A（推奨）**: キャッシュ / キュー / サーキットブレーカ / 分散ロック / スケール = **N/A**（列追加 2 本・UPDATE 数件・プール約 95 件・運用者の逐次操作）。`retired_at` のインデックスも**張らない**（全走査で十分）。新規ライブラリ・新規サービスなし。意図的な非採用として記録（U1〜U4b と同方針）。
- **B**: いずれか導入。→ 規模・性質に対し過剰。

[Answer]:

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-design-patterns.md`（DP-U5-NN）/ `logical-components.md`（LC-U5-NN + 依存方向）を生成 → 標準 2 択（Request Changes / Continue → **Infrastructure Design〈U5〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
