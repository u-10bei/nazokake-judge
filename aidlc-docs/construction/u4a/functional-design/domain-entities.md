# U4a Domain Entities — スクリプト先行分（token_issue / pool_ingest）

**ユニット**: U4a。U1 の `Item`/`Token` を参照しつつ、管理 API の HTTP ペイロードと CLI 入出力のモデルを定義する。ペイロードモデルは**単一データ契約**として `schema/` に追加し、Worker（`backend/admin/`）と scripts が同一モデルを import する（Q3=A）。

---

## 1. U1 エンティティへの波及変更（Q5=X, U4a スコープに含む）

### Item の変更 — 本文を D1 に格納
現行 U1 の `Item.body_ref` は「本文への参照（本文自体は非格納）」だが、参照の解決先が存在せず **U2 の参加者 UI がペアの謎かけ本文を表示できない**（設計の穴）。NFR-08 の「リポジトリ管理外」は **git リポジトリ**を指し、DB は対象外（README「刺激はデプロイ時に別経路で投入する」＝投入先が D1）。

| フィールド | 変更前（U1） | 変更後（U4a 波及） |
|---|---|---|
| `item_id` | str（PK） | 変更なし |
| `layer` | Layer（NOT NULL, BR-11） | 変更なし |
| **`body`** | （なし） | **`str`（必須, min_length=1）= 謎かけ本文。D1 に格納**（pool_ingest が投入） |
| `body_ref` | str（必須, 参照） | **`str \| None`（任意）= 出自メモ**（例: コレクション番号・制作系列 ID）に格下げ |

**波及する実変更（U4a Code Generation で実施）**:
1. `schema/models.py` の `Item`: `body: str` 追加、`body_ref: str \| None = None` に変更。`validate_item` は層ラベル必須（BR-11）+ `body` 非空を検証。
2. `migrations/0002_item_body.sql`: `items` に `body TEXT NOT NULL` 追加（既存行があれば移行時の扱いを明記。新規プロジェクトのため実害なし）。`body_ref` は NULL 許容へ。
3. `backend/repo/repository.py` の `list_items`: `body`/`body_ref` を含める。
4. 関連テスト（`tests/unit/u1/test_schema.py` 等）の更新。
- **投入用 JSON ファイル自体は gitignore**（本文の git 非格納 = NFR-08 の実装）。

---

## 2. 管理 API ペイロード / CLI 入出力モデル（schema/ に追加）

### pool_ingest 系
- **`ItemIngestRequest`**: `{ items: list[Item] }`。CLI が JSON/JSONL を読み、`Item` へ検証してから bulk POST。
- **`IngestResult`**: 投入結果。
  | フィールド | 型 | 意味 |
  |---|---|---|
  | `ok` | bool | 全体成功可否 |
  | `inserted` | int | 新規 INSERT 件数 |
  | `updated` | int | 既存 upsert 件数（未参照 item のみ, BR-U4a-04） |
  | `rejected` | list[`RejectedItem`] | 拒否内訳（`{item_id, reason}`。層欠落/本文欠落/凍結ガード等） |
  | `sufficiency_warnings` | list[str] | **マージ後プール**（既存∪入力）の充足判定（BR-U4a-05）の不足内訳。**warning 扱いで投入は成功**（段階投入を妨げない。ハードなゲートは token_issue=BR-U4a-12） |

- **`RejectedItem`**: `{ item_id: str, reason: str }`。

### token_issue 系
- **`TokenIssueRequest`**: `{ count: int (ge=1) }`。URL テンプレートは CLI 側の責務（API は count のみ）。
- **`TokenIssueResult`**: `{ ok: bool, tokens: list[str], issued_at: str \| None, gate_errors: list[str] }`。
  - **発行時充足ゲート（BR-U4a-12）**: 現行プールが三点セット未達なら `ok=false`・`tokens=[]`・`gate_errors` に不足内訳（**発行拒否**）。充足なら `ok=true`・生成トークン列を返す。
- **`TokenUrl`**（CLI 内部・出力用）: `{ token: str, url: str }`。CLI がベース URL テンプレートに token を差し込んで生成。

### 参照する U1 モデル
- `Item`（上記変更後）、`Token`（`status=unused`, `issued_at` を発行時に設定）、`Layer`。
- トークン契約: `schema.generate_token()` / `is_valid_token()`（128-bit, XC-03）。

---

## 3. 永続化先（D1, U1 の DDL + migration 0002）
- `items`（`item_id` PK, `layer` NOT NULL CHECK, **`body` NOT NULL**（0002）, `body_ref` NULL 許容）。
- `tokens`（`token` PK, `status` DEFAULT 'unused', `issued_at` NOT NULL）。
- 書き込みは **Repository の新規メソッド `insert_items(bulk)` / `insert_tokens(bulk)`**（D1 batch 原子投入, Q2=A）経由のみ。scripts は直接 D1 に触れない（H-1(c)）。

---

## 4. 関係図（データフロー）
```
[pool_ingest CLI]  --JSON/JSONL 読込→ Item 検証--→ POST /admin/items (ItemIngestRequest)
[token_issue CLI]  --count 指定-------------------→ POST /admin/tokens (TokenIssueRequest)
                                (HTTPS + Basic 認証)      │
                                                          ▼
                              [ Worker backend/admin/ (Basic 認証境界) ]
                                   検証 → 事前チェック → ガード → Repository(insert_*)
                                                          │ env.DB (batch, 原子)
                                                          ▼
                                                     [ D1: items / tokens ]
[token_issue CLI]  ← TokenIssueResult(tokens) ── URL テンプレ合成 → URL 一覧(stdout/ファイル, gitignore)
```
