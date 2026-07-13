# U4a Business Logic Model — token_issue / pool_ingest

**ユニット**: U4a。CLI（`scripts/`）＋ Worker 管理 API（`backend/admin/`, U4a 先行導入）＋ Repository 書き込みメソッド（U1 拡張）の三点で構成。技術非依存の業務ロジックを記述し、H-1=(c)（scripts→管理 API→D1）を実装する。

---

## 1. 構成要素（責務境界）

| 要素 | 配置 | 役割 | 新規/拡張 |
|---|---|---|---|
| `pool_ingest` CLI | `scripts/` | JSON/JSONL 読込→検証→`POST /admin/items` | 新規（U4a） |
| `token_issue` CLI | `scripts/` | count 指定→`POST /admin/tokens`→URL 一覧出力 | 新規（U4a） |
| **管理エンドポイント** | `backend/admin/` | `/admin/items`・`/admin/tokens`、**Basic 認証境界** | **新規（U4a 先行導入, Q1=A）**。U2/U3 が認証を再利用 |
| Repository 書き込み | `backend/repo/` | `insert_items(bulk)` / `insert_tokens(bulk)`（D1 batch 原子, DP-01） | **U1 拡張（U4a）** |
| Item 本文格納 | `schema/` + `migrations/` | `Item.body` 追加・`0002_item_body.sql`・`list_items` 更新 | **U1 波及（U4a, Q5=X）** |

- **依存方向**: CLI → (HTTPS+Basic) → 管理エンドポイント → Repository → D1。CLI は `schema/`（ペイロードモデル・トークン契約）のみ import、D1 に直接触れない（H-1(c) / 層の逆流禁止）。
- 管理エンドポイントは raw workers API + module-level `on_fetch` 内でルーティング（F-4/F-5, U1 で確定した規約）。Basic 認証は `on_fetch` 内の関数として実装（ASGI ミドルウェア前提にしない）。

---

## 2. pool_ingest フロー（US-R06）

```
1. CLI: JSON/JSONL を読み込み、各 record を schema.Item に検証
   （層ラベル必須 BR-U4a-01 / 本文非空 BR-U4a-02。不正はここで弾いて報告）
2. CLI: ItemIngestRequest を組み、HTTPS+Basic で POST /admin/items
3. Worker(admin): Basic 認証（BR-U4a-08）
4. Worker: プール充足の事前検証（BR-U4a-05 三点セット）
      不足 → precheck_errors を返し 投入せず終了（ok=false）
5. Worker: プール凍結ガード（BR-U4a-03）
      既存 items のうち pairs/judgments から参照済み集合を取得
      入力に「参照済み item_id への UPDATE」が含まれれば → 投入全体を中断（error, 列挙）
6. Worker: Repository.insert_items(bulk) を D1 batch で原子投入（BR-U4a-09）
      未参照 item_id は upsert（ON CONFLICT DO UPDATE, BR-U4a-04）、新規は INSERT
7. Worker: IngestResult(ok, inserted, updated, rejected, precheck_errors) を返す
8. CLI: 結果を表示（rejected/precheck_errors があれば非ゼロ終了）
```

- **べき等性**: 同一入力の再実行は同一 D1 状態（未参照 item は upsert）。
- **原子性**: 事前検証・ガードを通過してから 1 batch。途中失敗で半端投入なし（save_pair_sequence の実証済みイディオム）。

## 3. token_issue フロー（US-R05）

```
1. CLI: count とベース URL テンプレートを引数で受ける
2. CLI: TokenIssueRequest(count) を HTTPS+Basic で POST /admin/tokens
3. Worker(admin): Basic 認証
4. Worker: 既存トークン集合を読み、generate_token() で count 個を生成（衝突は事前排除, BR-U4a-06）
5. Worker: Repository.insert_tokens(bulk) を D1 batch 投入（status=unused, issued_at, BR-U4a-10）
      PK 衝突で失敗 → 全体を再生成しリトライ
6. Worker: TokenIssueResult(tokens, issued_at) を返す
7. CLI: 各 token を URL テンプレートに差し込み TokenUrl 一覧を生成
8. CLI: URL 一覧を stdout + ファイル出力（配布用・gitignore, BR-U4a-07）
```

---

## 4. U1 公開面の利用 / 拡張

| U1 公開面 | U4a での利用 |
|---|---|
| `schema.Item`（+ `body` 追加）/ `validate_item` | pool_ingest の検証、ペイロード契約 |
| `schema.generate_token` / `is_valid_token` | token_issue の生成（再実装しない, XC-03） |
| `schema`（新規ペイロードモデル追加） | ItemIngestRequest / IngestResult / TokenIssueRequest / TokenIssueResult |
| `backend.repo.Repository`（+ `insert_items`/`insert_tokens`） | 管理エンドポイントからの原子投入 |
| `backend.log.emit` | 拒否・不足・ガード発火の構造化ログ（error/warning） |

---

## 5. Testable Properties（U4a Code Generation / Build & Test で検証）

| ID | プロパティ | 対応 |
|---|---|---|
| **PU4a-1** | pool_ingest 冪等: 同一入力を 2 回投入 → D1 状態不変（2 回目は updated、inserted=0） | BR-U4a-04 |
| **PU4a-2** | 凍結ガード: 参照済み item_id の UPDATE を含む投入 → 全体拒否・D1 不変 | BR-U4a-03 |
| **PU4a-3** | プール充足述語: 三点セットを満たさない入力 → precheck_errors・投入なし／満たす入力 → 投入成功 | BR-U4a-05 |
| **PU4a-4** | トークン一意: count 個発行 → 全て一意・DB に count 行・`is_valid_token` 全通過 | BR-U4a-06 |
| **PU4a-5** | insert_items/insert_tokens の原子性: batch 途中失敗 → 全ロールバック | BR-U4a-09 / DP-01 |
| **PU4a-6** | 認証: Basic 認証なし/誤り → 401、投入なし | BR-U4a-08 |

- 統合テストは U1 と同様の実 D1 ハーネス（`tests/integration/`）を流用（管理エンドポイント越しに検証）。

---

## 6. 後続への申し送り
- **U2**: `backend/admin/` の Basic 認証を再利用。`Item.body` を参加者 UI で表示。
- **U3**: 同 Basic 認証境界にエクスポート・管理 UI を載せる。
- **U4a Code Generation の変更スコープ**（明示）: (1) 新規 `scripts/pool_ingest`・`scripts/token_issue`、(2) 新規 `backend/admin/`（エンドポイント+Basic 認証）、(3) `backend/repo` に `insert_items`/`insert_tokens` 追加、(4) **U1 波及**＝`schema/models.py` の `Item.body` 追加・`migrations/0002_item_body.sql`・`list_items` 更新・U1 テスト更新、(5) 新規ペイロードモデルを `schema/` に追加。
