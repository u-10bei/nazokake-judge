# U4a Logical Components — token_issue / pool_ingest（+ 管理 API）

**方針**: U4a は U1 の公開面（schema / Repository / domain / LogEmitter）を消費・拡張し、**管理 API 境界（backend/admin/）を先行導入**する。専用インフラ部品（queue/cache/CB/lock）は導入しない（DP-U4a 非採用表）。

---

## 論理コンポーネント一覧

### LC-U4a-01: AdminApi（`backend/admin/`）
- **役割**: 管理エンドポイント境界。`on_fetch` 内で `/admin/items`・`/admin/tokens` を手動ディスパッチ（raw workers API, F-5）。統一エラー封筒（DP-U4a-07）で応答。
- **フロー**: 認証（LC-U4a-02）→ 検証（schema）→ 充足判定/ガード（LC-U4a-03 / Repository）→ 原子投入（LC-U4a-04）→ 秘匿ログ（LC-U4a-05）。
- **依存**: LC-U4a-02（認証）、LC-U4a-03（pool_sufficiency）、U1 `Repository`（拡張, LC-U4a-04）、`schema`（ペイロード）、LC-U4a-05（ログ）。

### LC-U4a-02: AuthGuard（`backend/admin/`）
- **役割**: Basic 認証の**単一チョークポイント**（DP-U4a-01）。`env` の資格情報と定数時間比較、401 + `WWW-Authenticate`。
- **依存**: `env`（wrangler secret / .dev.vars）。**U2/U3 が再利用**。

### LC-U4a-03: PoolSufficiency（`backend/domain/`）
- **役割**: `pool_sufficiency(items, params) -> SufficiencyResult{ok, shortfalls}`。三点セット（BR-U4a-05）を評価する**純粋関数・単一実装**（DP-U4a-05）。副作用なし。
- **依存**: `schema`（Item/AssignmentParams）のみ。PBT 対象。

### LC-U4a-04: Repository 書込拡張（`backend/repo/`, U1 LC-03 拡張）
- **役割**: `insert_items(bulk, upsert+凍結ガード)` / `insert_tokens(bulk)` を **D1 batch 原子投入**で追加（DP-U4a-03/04）。凍結ガード用に「参照済み item_id 集合」読取も提供。
- **依存**: `schema`、U1 `_d1` ヘルパ。**Worker 内専用**（H-1(c)、実行時 D1 は Worker 集約）。

### LC-U4a-05: AdminLog（横断, `backend/` ログ規約）
- **役割**: 管理操作の**秘匿ログ強制点**（DP-U4a-02）。U1 `emit` を許可フィールド限定で呼ぶラッパ/規約。token 生値・本文を構造的に排除。
- **依存**: U1 `backend.log.emit`。

### LC-U4a-06: CLI（`scripts/pool_ingest`, `scripts/token_issue`）
- **役割**: Worker 外の pure-Python。JSON/JSONL 読込・`count`+URL テンプレート → HTTPS + Basic で AdminApi を叩く。結果表示・URL 一覧出力（gitignore）。
- **依存**: `schema`（ペイロードモデル・トークン契約）のみ import。**D1 に直接触れない**（H-1(c)）。

### DataContract 拡張（U1 LC-01 = `schema/`, U4a 波及）
- `Item` に `body: str`（必須）追加・`body_ref` を任意化（migration 0002）。
- ペイロードモデル追加: `ItemIngestRequest` / `IngestResult` / `RejectedItem` / `TokenIssueRequest` / `TokenIssueResult` / `SufficiencyResult`。

---

## 依存方向（層の逆流禁止）

```
[ scripts/ CLI (LC-U4a-06) ]  ──HTTPS + Basic──►  ┐
                                                   ▼
        ┌─────────── LC-U4a-01 AdminApi (backend/admin/) ───────────┐
        │  → LC-U4a-02 AuthGuard   → LC-U4a-05 AdminLog(秘匿)         │
        │  → LC-U4a-03 PoolSufficiency (backend/domain, 純粋)         │
        │  → LC-U4a-04 Repository 書込拡張 (backend/repo, Worker専用) │
        └───────────────────────────┬───────────────────────────────┘
                                     │ import（公開面のみ）
                          ┌──────────▼───────────┐
                          │ LC-01 DataContract    │ ← 最下層（schema/, U4a で body/ペイロード拡張）
                          └───────────────────────┘
                                     │
                                  [ D1 ]
```

- **一方向依存**: CLI は `schema`（ペイロード）のみ、AdminApi は U1 公開面（Repository/domain/log）+ schema。**U4a から上位への依存なし**、`scripts` は D1 に直接依存しない（U1-NFR-15 / H-1(c)）。
- LC-U4a-03（PoolSufficiency）は純粋（副作用なし）。副作用（D1 I/O）は LC-U4a-04 Repository に集約。ログ（LC-U4a-05）は横断。

---

## 後続への申し送り（Infrastructure Design / Code Generation）
- **Infrastructure Design（U4a）**: 管理 API のルート（`/admin/*`）・シークレット（`ADMIN_BASIC_*` を wrangler secret）・migration 0002 の適用順。基盤は U1 共有（D1 + CI デプロイ）を流用するため差分は小さい見込み。
- **Code Generation**: `backend/admin/`（AdminApi + AuthGuard）、`backend/domain/pool_sufficiency`、`backend/repo` 拡張、`scripts/`、schema 波及、migration 0002、PBT + integration。
