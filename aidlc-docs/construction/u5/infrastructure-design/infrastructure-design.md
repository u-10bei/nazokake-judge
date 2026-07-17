# U5 Infrastructure Design — 出題停止（item retirement）

**ユニット**: U5。**U1〜U4b の共有インフラ（D1 + 同一 Worker + CI デプロイ + Basic 認証）を全面流用**し、差分のみを定義する。共有分は `shared-infrastructure.md`、実装規約（F-1〜F-8）は U1 `infrastructure-design.md §2.1`、CI（`deploy.yml`）は U4a `§5`、`scripts/` 非デプロイ CLI パターンは U4a `§1/§6` を参照。
**方針**: **新規インフラは実質ゼロ**。差分は **(a) migration 0004（列追加 2 本）** と **(b) `/admin/items/retire|unretire` の POST ルート追加**（既存 Worker・既存 Basic 認証背後）のみ。**`wrangler.toml` / `deploy.yml` / `frontend/` / シークレット / CORS / `[assets]` はすべて無変更**。Infra Design 全 4 問 A（2026-07-17）。

---

## 1. LC-U5 → インフラ マッピング（差分）

| 論理コンポーネント | インフラ | 備考 |
|---|---|---|
| **LC-U5-07 migration 0004** | **D1 に列追加 2 本**（`items.retired_at` / `sessions.likert_targets`） | **唯一の実インフラ差分**。いずれも NULL 許容＝**安全な no-op 移行**（§4） |
| **LC-U5-04 RetireApi** | 既存 Worker の `handle_admin` に **POST ルート 2 本追加**（`/admin/items/retire`・`/admin/items/unretire`, Q2=A） | 別 Worker にしない（U4a-NFR-02）。**既存 AuthGuard を通す**（単一チョークポイント） |
| **LC-U5-01/02 Repository 拡張** | 既存 **D1 バインディング（`DB`）** 経由 | `list_active_items`（新設）/ `list_items`（**凍結**）/ `retire_items`・`unretire_items` |
| **LC-U5-03 `get_likert_targets`** | Worker 内 compute（純粋 domain への橋渡し） | インフラ依存なし |
| **LC-U5-06 Session 保存経路** | 既存 D1・`save_pair_sequence` の**同一 batch**に相乗り | 新規テーブル・新規経路なし（DP-U5-02） |
| **LC-U5-05 `pool_retire` CLI** | **手元/CI の pure-Python**（Worker 外・**非デプロイ**, Q2=A） | `scripts/_client` 流用・`urllib` のみ。U4a CLI と同型 |
| AuthGuard / `admin_log`（再利用） | 既存（U4a） | **新規シークレット・新規認証なし**。`item_retire`/`item_unretire` イベント追加 |

---

## 2. Compute / Networking（Q2）
- `/admin/items/retire` / `/admin/items/unretire` の **POST ルートを既存 Worker・同一サブドメインに追加**（別 Worker/サブドメインに分離しない）。証明書・デプロイの二重化を避ける。
- **既存 AuthGuard（Basic 認証）の背後**＝U4a の単一チョークポイント（`path.startswith("/admin/")` → `handle_admin`）を通る。
- **CORS なし**（同一オリジン・管理系は Basic 認証で参加者系〈`/api/*`〉と分離＝既存方針）。**新規公開面なし**。
- **参加者 API（`/api/*`）・フロント（`frontend/`）には一切触れない**。

## 3. Secrets（差分なし）
- **新規シークレットなし**。`ADMIN_BASIC_USER` / `ADMIN_BASIC_PASSWORD`（U4a・手元 `wrangler secret put`）を再利用。`.dev.vars` / `.dev.vars.example` に追加項目なし。

## 4. Storage — migration 0004（Q1・唯一の実差分）

```sql
ALTER TABLE items    ADD COLUMN retired_at     TEXT;  -- NULL=現役 / ISO8601=廃止時刻
ALTER TABLE sessions ADD COLUMN likert_targets TEXT;  -- JSON 配列 / NULL=旧セッション
```

- **安全な no-op 移行**: **いずれも NULL 許容**ゆえ **0002 のようなテーブル再構築は不要**・**既存行のデータ移送も不要**。適用直後の意味論は **既存 items = 全て現役 / 既存 sessions = 全てフォールバック** ＝ **適用しただけでは挙動が一切変わらない**（U5-NFR-01）。
- **インデックスなし**（プール約 95 件・全走査で十分）。
- **適用順は `migration → deploy` を厳守**（U5-NFR-02）。逆順では `retired_at`/`likert_targets` 前提のコードが旧スキーマに当たる。→ **`deploy.yml` が既にこの順（§5）ゆえワークフロー無変更で自動的に守られる**。
- **本番未デプロイの活用**: **初回デプロイで `0001`〜`0004` が一括適用**される（versioned・順次）。→ **`likert_targets IS NULL` の旧セッションは本番に実在しない**。フォールバック（BR-U5-04）は「**稼働後に U5 を適用する場合**」の保険として実装・検証する（U5-NFR-03）。
- **dev で先に適用して検証**（既存の dev/prod D1 分離を流用）。

## 5. CI/CD（`deploy.yml` 無変更, Q3）
- **`deploy.yml` は無変更**。既存フローがそのまま機能する:
  ```
  uv sync → test（unit+PBT・前置ゲート）→ d1 migrations apply --remote（0001〜0004）→ deploy
  ```
  **versioned 自動適用ゆえ 0004 を書き足す必要すらない**。
- **U5 の追加テスト（PU5-1〜4 + PBT-02 + unit）は前置ゲートに自動搭載**＝回帰時はデプロイをブロック。
- **★ 品質ゲートの意味づけ**: **PU3-3（export 自己完結性）が緑であることがデプロイの前提**＝**BR-U5-02 の禁止事項（`list_items()` への active フィルタ追加）を踏んだコードは本番に出られない**（U5-NFR-04/13）。仕様の明文（BR-U5-02）・PBT の網（PU5-2/PU5-4）・**デプロイゲート**の三重で守る。
- **CI Secrets 差分なし**（`CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` のみ）。

## 6. Static Assets / Monitoring
- **`[assets]` 変更なし**。参加者 UI に変更なし（**廃止は出題対象が減るだけで画面の作りは一切変わらない**）。
- **Monitoring**: `admin_log` に **`item_retire` / `item_unretire`** を追加（stdout JSON → `wrangler tail`）。基盤は不変。**本文（`body`）は出さない**（既存の秘匿方針）。**これが廃止履歴の正**（U5-NFR-09 / BR-U5-13）。

## 7. デプロイ手順（U5）
```
1. dev: wrangler d1 migrations apply nazokake-judge --local/--remote（0004 まで）で先行検証
2. CI(deploy.yml・手動実行): uv sync → test（PU5 含む・前置ゲート）
                            → d1 migrations apply --remote（0001〜0004）→ deploy
3. 手元: python -m scripts.pool_retire <item_id...>  （必要時・非デプロイ CLI）
```
**ワークフロー・シークレット・`wrangler.toml` の変更は一切不要。**

## 8. 動作確認（Q4）
- **integration（実 D1 / miniflare・既存ハーネス流用）**:
  - **回帰**: **migration 0004 適用後に U2/U3 の既存シナリオが緑**（U5-NFR-13）。
  - **U5 シナリオ**: 参照済み item の廃止が成功 → 新規セッションに出ない → **進行中セッションには出続ける** → **export の `items` は縮まない** → 充足割れで発行拒否。
- **beta 検証は不要**（新規ランタイム機構なし。列追加 2 本と POST ルート 2 本は F-4〈起動 CPU 制限〉実測の対象になる規模ではない）。
- **参加者 UI の目視確認は不要**（画面の作りが変わらない）。
- **本番デプロイ後の確認**: `pool_retire` の疎通（`/admin/items/retire` が 200・未認証が 401）+ `wrangler tail` で `item_retire` ログが出ること。

## 9. トレーサビリティ
| 項目 | 対応 |
|---|---|
| migration 0004・適用順・no-op 移行 | Q1 / U5-NFR-01/02 / LC-U5-07 |
| 本番未デプロイ＝0001〜0004 一括・旧セッション不在 | Q1 / U5-NFR-03 |
| `/admin/items/retire|unretire`・同一 Worker・既存 AuthGuard | Q2 / U5-NFR-12 / LC-U5-04 |
| CLI 非デプロイ・`_client` 流用 | Q2 / LC-U5-05 / TSD-U5-05 |
| `deploy.yml` 無変更・PU3-3 緑がデプロイの前提 | Q3 / U5-NFR-04/13 |
| 新規シークレットなし・CORS なし・assets 無変更 | Secrets/§2/§6 差分なし |
| `admin_log` = 廃止履歴の正 | Q4/§6 / U5-NFR-09 / BR-U5-13 |
| beta/UI 目視 不要 | Q4 |

## 10. 後続申し送り（Code Generation〈U5〉）
- **生成対象**: `migrations/0004_item_retire.sql`、`Repository.list_active_items` / `retire_items` / `unretire_items`、`Session.likert_targets` + `save_pair_sequence`/`get_session` 拡張、`get_likert_targets`（単一アクセサ）、`/admin/items/retire|unretire`、`scripts/pool_retire.py`、`schema/payloads.py` に `ItemRetireRequest`/`RetireResult`。
- **★ 禁止事項（Step 記述に一行固定）**: **`list_items()` に active フィルタを足さない**（`active_only` 引数の新設も禁止）。**`list_active_items()` を新設し、新規セッション系・充足判定のみが呼ぶ**（BR-U5-02 / DP-U5-01）。踏むと **export 縮小→PU3-3 違反→U4b 破壊** と **フォールバック導出変化→「新規のみ反映」破れ** の**両輪が同時に壊れる**。
- **★ 3 箇所集約の完遂**: `build_view` / `check_complete` / `submit_likert` の**すべて**を `get_likert_targets` 経由に。**一部だけ切り替えると「表示されたターゲットの送信が拒否される」**。
- **★ 原子保存**: `likert_targets` は `save_pair_sequence` の**同一 batch**で INSERT（別経路にしない, DP-U5-02）。
- **変更しないもの**: `wrangler.toml` / `deploy.yml` / `frontend/` / `Item` / `ExportItem` / `EXPORT_FORMAT_VERSION`（1.0.0）/ U3・U4b のコードとテスト（**書き換えたら形式を変えた証拠＝設計違反のシグナル**, U5-NFR-04）。
