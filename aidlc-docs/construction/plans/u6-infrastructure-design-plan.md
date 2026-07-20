# U6 Infrastructure Design Plan — 層拡張 + 事前生成割当

**ユニット**: U6。LC-U6-01〜14 を実インフラにマップする。
**前提（既決）**: FD（BR-U6-01〜22）/ NFR Req（U6-NFR-01〜22 / TSD-U6-01〜10）/ NFR Design（DP-U6-01〜08 / LC-U6-01〜14）。共有インフラは U1 所有・同一 Worker・CI デプロイ（`deploy.yml`）・Basic 認証境界（`ADMIN_BASIC_*`）。

**差分の見込み**: **(a) migration 0005** / **(b) `/admin/plan`・`/admin/plan/activate` の POST 2 本** / **(c) `scripts/plan_generate`（非デプロイ）**。`wrangler.toml` / `deploy.yml` / `frontend/` / シークレット / CORS は**無変更の見込み**。

> **ただし U5 と決定的に違う点**: U5 の 0004 は**安全な no-op 移行**（NULL 許容の列追加のみ）だったが、**0005 は「データがある状態での親テーブル再構築」**であり、**適用タイミングに制約がある**（U6-NFR-04）。**インフラ面の重心はここ**。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `construction/u6/infrastructure-design/infrastructure-design.md`（差分中心）を生成します。

## 生成予定の成果物（Part 2）
- [ ] `construction/u6/infrastructure-design/infrastructure-design.md`

---

## 調査で判明した論点（2026-07-20）

| # | 事実 | 影響 |
|---|---|---|
| 1 | **`assignment_plan` に FK（`item_left`/`item_right` → `items`）を張ると、0005 適用後に items を参照する FK が 2 本 → 4 本になる** | **U6-NFR-06 の「FK 全数調査結果をヘッダに残す」は 0005 時点の記録**だが、**0005 自身が FK を増やす**。将来 items を再構築する migration は **`pairs` に加え `assignment_plan` も退避対象**にしないと同じ罠を踏む → **その旨も 0005 のヘッダに残す必要**（Q1） |
| 2 | **成立版とフォールバック版で参照する item 集合が異なる**（N1〜N8 ⇄ S02・S19・S11・S12 等） | **FK を張る限り、両セットを投入するには両方の item が `items` に存在**しなければならない。しかし**それだと `n ≠ 38` になり BR-U6-22 の期待組成チェックと衝突**する（Q1） |
| 3 | **`deploy.yml` は毎回 `d1 migrations apply --remote` を走らせる** | 0005 は versioned ゆえ**適用は 1 回だけ**だが、**その 1 回がいつ起きるか＝いつデプロイするかで決まる**。**U6-NFR-04 の適用ウィンドウ制約はデプロイのタイミング制約になる**（Q2） |

---

## インフラカテゴリ適用性評価（U6・差分のみ）
| カテゴリ | 適用 | 判断根拠 |
|---|---|---|
| **Storage / Migration** | **適用（最重要）** | 0005（items 再構築 + 新規 2 テーブル + tokens 拡張）。**FK 設計と適用ウィンドウ**が論点。→ Q1 / Q2 |
| **Deployment（順序）** | **適用（U6 固有）** | 0005 の適用タイミング制約 + **プラン投入・activate・トークン発行の厳密な順序**。→ Q2 |
| **Compute** | 流用 + 極小差分 | 既存 Worker に **POST 2 本追加**（既存 AuthGuard 背後）。`plan_generate` は**非デプロイ**。→ Q3 |
| **Networking** | 流用 | 同一オリジン・CORS なし・新規公開面は `/admin/*` のみ。 |
| **Secrets** | **N/A（差分なし）** | `ADMIN_BASIC_*` 再利用。新規シークレットなし。 |
| **CI/CD** | 流用（無変更の見込み） | `deploy.yml` は versioned 自動適用ゆえ 0005 を書き足す必要なし。→ Q4 |
| **Static Assets** | **N/A** | フロント無関係（**参加者 UI は一切変わらない**）。 |
| **Monitoring** | 流用 + 差分 | `admin_log` に `plan_ingest` / `plan_activate` / `plan_activate_rejected` 追加。 |
| **Messaging / Scalability / Resiliency** | **N/A** | プラン引き当ては PK 参照・運用者の逐次操作。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【★Storage/FK】`assignment_plan` の FK と両プランセットの item 集合
**問題（事実 #1・#2）**: FD の DDL は `assignment_plan` に FK を張っているが、
(i) **0005 自身が items 参照 FK を 2→4 本に増やす**（将来の再構築の負債）
(ii) **両セットの item 集合が異なると、FK により両方の item を `items` に置く必要**があり、**期待組成 n=38 と衝突**する。

- **★A（推奨）**: **`assignment_plan` に FK を張らない**。**プラン投入をプール構成から独立**させる。
  - **整合性は生成時に保証**: `plan_generate` は**プールから**プランを構成するため、**参照する item は構成上すべて実在**する（LC-U6-06 `verify` でも検証）。
  - **投入時にも検証**: `POST /admin/plan` で**参照 item がすべて `items` に存在すること**をアプリ層で確認（FK と同じ保護を、**投入順序の柔軟性を保ったまま**得る）。
  - **利点**: (i) **将来の items 再構築の退避対象が `pairs` のままで済む**（負債を増やさない）(ii) **両セットを独立に投入でき、期待組成 n=38 と衝突しない**（フォールバック版の item は activate 時に入れ替える）。
  - **0005 のヘッダに「FK を増やさない設計判断」も記録**する（将来の migration 作成者への申し送り）。
- **B**: FK を張り、**両セットの item の和集合を `items` に投入**し、**非活性セット固有の item は U5 の `retired_at` で出題停止**にする。→ **U5 の機構を再利用できエレガント**だが、**「プラン activate」と「retire 状態の入れ替え」を常に同期**させる必要があり、**忘れると期待組成チェックが落ちる/静かにずれる**。結合が増える。
- **C**: FK を張り、**activate 時にプールを入れ替える**。→ プール入替は `items` の書き換え＝**凍結ガード（BR-U4a-03）と衝突**。不採用。

[Answer]:

### Q2【★Deployment】0005 の適用ウィンドウと運用順序
**事実 #3**: `deploy.yml` は毎回 migrations を適用するため、**0005 の適用タイミング = U6 を最初にデプロイするタイミング**。U6-NFR-04 は「**発行済み未消化トークンが存在しない時点に限る**」を要求する。

- **★A（推奨）**: **U6 のデプロイを「実験開始前のカットオーバー」として位置づけ**、手順に**厳密な順序**を明記する:
  ```
  ① U6 をデプロイ（deploy.yml 手動実行）→ 0005 が適用される
     ⚠️ 前提: 発行済み未消化トークンが存在しないこと（U6-NFR-04）
     ⚠️ 適用後検証: foreign_key_check / items・pairs 行数一致 / retired_at 非 NULL 件数一致
  ② pool_ingest（38 件・anchor 2 件と practice 素材を含む）
  ③ plan_generate → POST /admin/plan（成立版・フォールバック版の両方）
  ④ POST /admin/plan/activate（一方を有効化）
  ⑤ token_issue 8（★この時点で (plan_set, plan_index) がトークンへ束縛される）
  ⑥ 配布・実験開始
  ```
  - **順序の必然性**: ③はプール確定後（プランはプールから構成）/ ⑤は④の後（活性セットを束縛するため）。**順序を誤ると静かに壊れる**（例: ④の前に⑤すると束縛先が未定）。
  - **本番未デプロイゆえ「未消化トークンなし」は自然に満たされる**（初回デプロイで 0001〜0005 が一括適用・items も空）。→ **制約はコストゼロで満たせる**が、**将来の再適用・dev 環境では明示的に守る必要**がある。
- **B**: 適用ウィンドウを運用注意に留める。→ **U6-NFR-04 がブロッキング前提**と定めた以上、手順に組み込むべき。

[Answer]:

### Q3【Compute】POST 2 本の追加と CLI の非デプロイ
- **★A（推奨）**: **`/admin/plan`・`/admin/plan/activate` を既存 Worker・同一サブドメインに追加**（既存 AuthGuard 背後・U4a の単一チョークポイントを通す）。**新規シークレット・CORS 変更なし**。
  - **`scripts/plan_generate` は非デプロイ**（`scripts/` 配下・手元/CI の pure-Python・`_bootstrap` で src 解決・`scripts/_client` 流用）＝U4a/U5 の CLI と同型。**Worker バンドルに含めない**。
  - **参加者 API（`/api/*`）・フロント（`frontend/`）には一切触れない**（参加者 UI は**画面の作りが一切変わらない**）。
- **B**: プラン管理を別 Worker に分離。→ デプロイ・証明書の二重化。小規模に過剰。

[Answer]:

### Q4【CI/CD + 動作確認】
- **★A（推奨）**:
  - **`deploy.yml` は無変更**。既存フロー `uv sync → test（前置ゲート）→ d1 migrations apply --remote（0001〜0005）→ deploy` がそのまま機能する（**versioned 自動適用ゆえ 0005 を書き足す必要なし**）。
  - **U6 の追加テスト（PU6-1〜8 + unit）は前置ゲートに自動搭載**。**PU3-3 が緑であることがデプロイの前提**＝U5 BR-U5-02 の禁止事項を踏んだコードは本番に出られない（U5 から継承）。
  - **integration（実 D1）**: **0005 を「データがある状態」で適用**（U6-NFR-01/05）・プラン投入 → activate → セッション開始 → **ペア列がプランと一致**・**U2/U3/U4a/U5 の既存シナリオが緑**・**activate ガードが judgment 存在で拒否**。
  - **beta 検証は不要**（新規ランタイム機構なし）。**参加者 UI の目視も不要**（画面の作りが変わらない）。
  - **本番デプロイ後の確認**: 0005 適用後検証 3 点（Q2 の⑤）+ `POST /admin/plan` の疎通（200・未認証 401）+ `wrangler tail` で `plan_ingest` ログ。
- **B**: `deploy.yml` に 0005 用ステップを追加。→ versioned 自動適用と二重。不要。

[Answer]:

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `infrastructure-design.md`（差分中心）を生成 → 標準 2 択（Request Changes / Continue → **Code Generation〈U6〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
