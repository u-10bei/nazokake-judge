# U5 Infrastructure Design Plan — 出題停止（item retirement）

**ユニット**: U5。LC-U5-01〜07（`list_active_items` / retire・unretire / `get_likert_targets` / RetireApi / `pool_retire` CLI / Session 保存経路 / migration 0004）を実インフラにマップする。
**前提（既決・U1〜U4b で確定）**: 案 A′（Python Workers + D1, raw workers API, **src/ レイアウト F-8**）。共有インフラは U1 所有（`shared-infrastructure.md`）。同一 Worker・実験用サブドメイン一本・CI デプロイ（`deploy.yml`, U4a 機能化済み）・Basic 認証境界（`ADMIN_BASIC_*`, U4a 導入済み）。NFR Design 全 5 問 A（DP-U5-01〜04 / LC-U5-01〜07）。

**方針**: **新規インフラは実質ゼロ**。差分は **migration 0004（列追加 2 本）** と **`/admin/items/retire|unretire` の POST ルート追加**（既存 Worker・既存 Basic 認証背後）のみ。**`wrangler.toml` / `deploy.yml` / `frontend/` / シークレット / CORS / `[assets]` はすべて無変更**。`pool_retire` CLI は**非デプロイ**（U4a CLI と同型）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `construction/u5/infrastructure-design/infrastructure-design.md`（差分中心）を生成します（共有分は既存 `shared-infrastructure.md` を参照）。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-17, 全 4 問 A）
- [x] `construction/u5/infrastructure-design/infrastructure-design.md`（LC-U5→インフラ差分＝migration 0004 + `/admin/*` POST 追加のみ・非デプロイ CLI・適用順・動作確認方針・Code Gen 申し送り）

---

## インフラカテゴリ適用性評価（U5・差分のみ）
| カテゴリ | 適用 | 判断根拠 |
|---|---|---|
| **Storage / Migration** | **適用（唯一の実差分）** | **migration 0004**（`items.retired_at` / `sessions.likert_targets`・いずれも NULL 許容）。適用順が論点。→ Q1 |
| **Compute** | 流用 + 極小差分 | 既存 Worker に `/admin/items/retire|unretire` の **POST ルート 2 本追加**（同一サブドメイン・既存 AuthGuard 背後）。`pool_retire` CLI は**非デプロイ**（`scripts/`）。→ Q2 |
| **Networking** | 流用 | 同一オリジン・**CORS なし**（管理系は Basic 認証で分離・既存方針）。新規公開面なし。 |
| **Secrets** | **N/A（差分なし）** | `ADMIN_BASIC_*`（U4a）を再利用。**新規シークレットなし**。`.dev.vars` 追加項目なし。 |
| **CI/CD** | 流用（無変更） | `deploy.yml` は**無変更**（versioned 自動適用ゆえ 0004 が自動で載る）。U5 テストは前置ゲートに自動搭載。→ Q3 |
| **Static Assets** | **N/A** | フロント無関係。`[assets]` 変更なし。参加者 UI に変更なし（廃止は出題対象が減るだけで画面は不変）。 |
| **Monitoring** | 流用 + 差分 | `admin_log` に `item_retire`/`item_unretire` 追加（stdout JSON → `wrangler tail`）。基盤は不変。 |
| **Messaging / Scalability / Resiliency** | **N/A** | 列追加 2 本・UPDATE 数件・運用者の逐次操作。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Storage / Migration】migration 0004 の適用順と「本番未デプロイ」の活用
- **★A（推奨）**:
  - **適用順は `migration → deploy` を厳守**（Infra §4 の既存規約・U5-NFR-02）。逆順では `retired_at` / `likert_targets` 前提のコードが旧スキーマに当たる。`deploy.yml` は既に **`d1 migrations apply --remote` → `deploy`** の順ゆえ**ワークフロー無変更で自動的に守られる**。
  - **本番は未デプロイ**ゆえ、**初回デプロイで `0001`〜`0004` が一括適用**される（versioned・順次）。→ **`likert_targets IS NULL` の旧セッションは本番に実在しない**（フォールバックは「稼働後に U5 を適用する場合」の保険として実装・検証する, U5-NFR-03）。
  - **dev で先に適用して検証**（既存の dev/prod 分離を流用）。**0004 は安全な no-op 移行**（NULL 許容の列追加のみ・既存行のデータ移送なし・適用しただけでは挙動不変, U5-NFR-01）。
- **B**: 0004 を別タイミングで手動適用。→ `deploy.yml` の自動適用と二重管理になり適用順の保証が崩れる。不採用。

[Answer]:A

### Q2【Compute】retire/unretire ルートと CLI のホスティング
- **★A（推奨）**: **`/admin/items/retire` / `/admin/items/unretire` の POST ルートを既存 Worker・同一サブドメインに追加**（別 Worker に分離しない, U4a-NFR-02 と同方針）。**既存 AuthGuard（Basic 認証）の背後**＝U4a の単一チョークポイントを通す。**新規シークレット・CORS 変更なし**。
  - **`pool_retire` CLI は非デプロイ**（`scripts/` 配下・手元/CI の pure-Python・`_bootstrap` で src 解決・`scripts/_client` 流用）＝U4a `token_issue`/`pool_ingest` と同型。**Worker バンドルに含めない**。
- **B**: 廃止操作を別 Worker / 別サブドメインに分離。→ デプロイ・証明書の二重化。小規模に過剰。不採用。

[Answer]:A

### Q3【CI/CD】`deploy.yml` と品質ゲート
- **★A（推奨）**: **`deploy.yml` は無変更**。既存フロー `uv sync → test（unit+PBT, 前置ゲート）→ d1 migrations apply --remote（0001〜**0004**）→ deploy` がそのまま機能する（versioned 自動適用ゆえ 0004 を書き足す必要すらない）。
  - **U5 の追加テスト（PU5-1〜4 + PBT-02 + unit）は前置ゲートに自動搭載**＝回帰時はデプロイをブロック。
  - 特に **PU3-3（export 自己完結性）が緑であることがデプロイの前提**＝**BR-U5-02 の禁止事項を踏んだコードは本番に出られない**（U5-NFR-04/13）。
- **B**: `deploy.yml` に 0004 用のステップを追加。→ versioned 自動適用と二重になり不要。不採用。

[Answer]:A

### Q4【動作確認】検証方針
- **★A（推奨）**:
  - **integration（実 D1 / miniflare）**: **migration 0004 適用後に U2/U3 の既存シナリオが緑**であること（回帰・U5-NFR-13）+ **U5 シナリオ**（参照済み item の廃止が成功 → 新規セッションに出ない → 進行中セッションには出続ける → export の items は縮まない → 充足割れで発行拒否）。既存ハーネス（`tests/integration/`）を流用。
  - **beta 検証は不要**（新規ランタイム機構なし。列追加 2 本と POST ルート 2 本は F-4 実測の対象になる規模ではない）。
  - **参加者 UI の目視確認は不要**（廃止は出題対象が減るだけで**画面の作りは一切変わらない**）。
  - **本番デプロイ後の確認**: `pool_retire` の疎通（`/admin/items/retire` が 200・未認証が 401）と `wrangler tail` で `item_retire` ログが出ること。
- **B**: beta 検証や UI 目視を要求。→ 新規ランタイム機構・UI 変更がなく対象が存在しない。不採用。

[Answer]:A

---

**回答サマリ**: 全 4 問 A。差分は **migration 0004 + `/admin/items/retire|unretire` POST 追加のみ**。適用順は `deploy.yml` の既存順（test → migrations → deploy）で**自動的に守られる**。本番未デプロイゆえ **0001〜0004 一括適用＝旧セッション不在**。**PU3-3 緑がデプロイの前提＝BR-U5-02 違反コードは本番に出られない**（仕様の明文・PBT の網・デプロイゲートの三重）。beta/UI 目視は不要。

**次**: 標準 2 択（Request Changes / Continue → **Code Generation〈U5〉**）。
