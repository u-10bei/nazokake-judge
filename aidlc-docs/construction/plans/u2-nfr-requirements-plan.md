# U2 NFR Requirements Plan — 参加者セッション（participant）

**ユニット**: U2（C-FE-PART / C-SVC-SESSION / C-SVC-RESPONSE / C-SVC-SURVEY / C-API〈参加者系〉）
**目的**: U2 の非機能要件を確定する。U2 は**参加者に直接触れる初の UI + 公開 API** のため、(1) **トークン=資格の衛生**（Basic 認証なし、`/api/*`）、(2) **出自秘匿による評価健全性**（layer/body_ref を参加者に出さない）、(3) **モバイル/日本語 UI の可用性**（XC-04）が固有の最大論点。冪等性・完了順序・XC-02 は Functional Design（BR-U2-11/17/22/24）で決定済みなので NFR として明文化する。
**前提（既決）**: 拡張 opt-in は U1/U4a と共通（Security Baseline=No / Resiliency=No / **PBT=Partial**、強制 PBT-02/03/07/08/09）。案 A′（Cloudflare Python Workers + D1, raw workers API + Pydantic v2）。監視基盤なし（stdout JSON）。管理境界（Basic 認証）は U4a が先行導入済み（U2 は参加者系を別接頭辞 `/api/*` で追加、認証はトークン自体）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-requirements.md`（U2-NFR-NN）/ `tech-stack-decisions.md`（U2 追加分）を生成します。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-14）
- [x] `construction/u2/nfr-requirements/nfr-requirements.md`（U2-NFR-01〜14: セキュリティ衛生/研究健全性/可用性/信頼性/性能/可観測性/テスト容易性/データ + 非目標）
- [x] `construction/u2/nfr-requirements/tech-stack-decisions.md`（TSD-U2-01〜06: 参加者 API `/api/*`・no-store・相関ハッシュ・ItemView 秘匿・migration 0003・PBT/integration 振り分け）

**回答サマリ**: 全 8 問 ★A。Q3 に追加規約「**相関ハッシュは SHA-256 先頭 8 文字等を参加者系ログ全体で単一規約**」。Q4「出自秘匿を NFR に昇格（ItemView={item_id,body} 固定・フラグ出し分け不採用）」。Q5「楽観更新なし（サーバ応答待ち）」。Q8「トークン無期限（BR-04 は失効ではない）」を非目標/明文化。

---

## NFR カテゴリ適用性（U2）
| カテゴリ | 適用 | 備考 |
|---|---|---|
| **Security** | **適用（最重要）** | トークン=資格の衛生（no-store・ログ非出力・HTTPS）、SQLi、CORS/配信オリジン。→ Q3 |
| **Usability** | **適用（U2 固有・重要）** | 初の UI。モバイルファースト・A/B 縦積み・日本語のみ・アクセシビリティ水準・送信フィードバック（XC-04）。→ Q5 |
| **研究健全性（Security 派生）** | **適用（U2 固有）** | 出自（layer/body_ref/seed）を参加者に出さない＝評価バイアス回避。→ Q4 |
| **Reliability** | 適用 | 冪等（判定初回不変・Likert 初回不変・Survey upsert）・完了順序保証・同時開始の露出競合許容。→ Q2 / Q8 |
| **Performance** | 適用（最小限） | セッション開始（generate_pairs + 露出導出）・送信の体感即時。SLO 姿勢。→ Q1 |
| **Observability** | 適用（最小限） | 構造化ログ（U1 emit 再利用）。参加者系もトークン生値・本文を非出力。→ Q3 |
| **Testability** | 適用 | PU2-1〜8 の PBT/integration 振り分け。→ Q6 |
| **Data/Migration** | 適用 | migration 0003（likert UNIQUE）・AssignmentParams.likert_fixed_targets。→ Q7 |
| **Scalability/Resiliency** | N/A | 単独研究者・小規模（総参加者数十名・同時数名）。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Performance】参加者向けレイテンシの SLO 姿勢
セッション開始は `read_exposure_counts`（H-2 導出=全確定 PairSequence 集計）+ `generate_pairs`、送信は冪等 INSERT + フェーズ再導出。
- **★A（推奨）**: **明示的な数値 SLO は設定しない**（U1-NFR-01/02 と同方針）。参考目安として非公式に「セッション開始 < 1s・各送信 < 500ms（体感即時）」を置く。想定規模（〜50 セッション × 約 43 ペア ≈ 2,000 行）では露出の毎回導出も D1 上で実質瞬時。キャッシュ・マテリアライズは不要。
- **B**: 数値 SLO を定め計測・追跡する。→ 小規模に対し運用コストが価値を上回る。

[Answer]: A — 明示的な数値 SLO は設定しない。非公式目安「セッション開始 < 1s・各送信 < 500ms」を参考記載。U1-NFR-01/02 と同方針の一貫適用（露出の毎回導出も想定規模では実質瞬時、キャッシュ不要）。

### Q2【Reliability】同時セッション開始時の露出スナップショット競合
複数参加者がほぼ同時に新規開始すると、各自が同じ露出値を読んで `generate_pairs` する可能性がある。
- **★A（推奨）**: **競合を許容する**（ロック・直列化を設けない、U1-NFR 非目標と一貫）。鮮度ズレは XC-01 の累積収束（P-1）で吸収され、各セッションの `exposure_snapshot` は「実際に参照した値」として保存されるため監査リプレイの完全性は損なわれない。同時数名の小規模では実害なし。
- **B**: セッション開始を直列化（ロック/キュー）。→ 小規模に過剰・Worker/D1 でのロックは複雑。

[Answer]: A — 競合を許容（ロック・直列化なし）。U1 NFR Q8 と同一の判断枠組み。鮮度ズレは P-1 の累積収束で吸収、`exposure_snapshot` は「実際に参照した値」保存で監査リプレイの完全性は保たれる。

### Q3【Security/Observability】参加者 API（`/api/*`）の衛生
トークン=資格（Basic 認証なし）。
- **★A（推奨）**: (i) **HTTPS 強制**。(ii) **全 `/api/*` 応答に `Cache-Control: no-store`**（トークン・本文のキャッシュ滞留防止, BR-U2-27）。(iii) **参加者系ログにトークン生値・謎かけ本文を出力しない**（AdminLog と同水準。相関が要る場合はトークンのハッシュ/接頭など非可逆化、生値は使わない）。(iv) 全 D1 アクセスはパラメータ化クエリ（SQLi 対策, BR-12）。(v) POST 系のトークンは **body 渡し**で統一（URL/クエリ露出の最小化。起動時のみ配布 URL 由来のクエリ）。
- **B**: ログにトークンを出す/no-store を付けない。→ 漏洩・キャッシュ滞留の経路。不採用。

[Answer]: A — HTTPS 強制 / 全応答 `no-store` / ログにトークン生値・本文非出力 / パラメータ化クエリ / POST はトークン body 渡し。**補足（相関ハッシュの規約・Code Generation へ申し送り）**: ログ相関にトークンの非可逆表現を使う場合、**ハッシュ形式（例: SHA-256 先頭 8 文字）を参加者系ログ全体で単一規約**に固定。wrangler tail で特定参加者フローを生値なしで追跡でき、デバッグ可用性と秘匿を両立。

### Q4【Security・研究健全性】参加者への出自秘匿（評価バイアス回避）
出自（`layer`＝プロ/AI 等・`body_ref`・`seed`）が見えると評価が汚染される（XC-01 の目的を損なう）。
- **★A（推奨）**: **参加者向け API レスポンスは本文（`body`）と表示に必要な最小項目のみ**を返し、**`layer` / `body_ref` / `seed` / `exposure_snapshot` を一切含めない**（domain-entities §4 の `ItemView = {item_id, body}` を NFR として固定）。他参加者分・発行総数も参加者スコープ外。これを「研究データ健全性を守るセキュリティ要件」として明示記録。
- **B**: デバッグ利便のため layer を含める（フラグで隠す）。→ 事故で露出するリスク。不採用。

[Answer]: A — 参加者向けレスポンスは本文と表示最小項目のみ。`layer` / `body_ref` / `seed` / `exposure_snapshot` を一切含めない（`ItemView = {item_id, body}` を NFR として固定）。**補足**: FD（domain-entities §4）の設計判断を「研究データ健全性を守るセキュリティ要件」に昇格＝削ってはいけない要件化。フラグ出し分け（B）は事故の入口ゆえ明示的に不採用。ブラインド評価の成立条件を API 契約レベルで強制。

### Q5【Usability】モバイル/日本語 UI の可用性水準（XC-04）
- **★A（推奨）**: **モバイルファースト・レスポンシブ**（A/B 縦積みで両作品が読みやすい・十分な行間/フォント・大きめタップ領域）、**日本語のみ**（切替なし）、**進捗は本番判定のみモバイル視認位置**（BR-U2-13）。アクセシビリティは**合理的水準**（セマンティック HTML・十分なコントラスト・キーボード操作可）を満たすが、**正式な WCAG 準拠適合を目標としない**（小規模・統制された評価者集団のため）。送信は**サーバ応答を待って次へ**（サーバ権威, 楽観更新はしない）、送信中/失敗/再試行は非ブロッキング表示。
- **B**: 正式な WCAG 2.1 AA 準拠を要件化。→ 小規模研究に対し過剰。
- **C**: PC 優先レイアウト。→ モバイルファースト方針（XC-04）に反する。

[Answer]: A — モバイルファースト・レスポンシブ・日本語のみ。アクセシビリティは合理的水準（セマンティック HTML・コントラスト・キーボード操作可）、正式 WCAG 準拠適合は目標にしない。**楽観更新はしない（サーバ応答を待って次へ）**。補足: 統制された評価者集団前提での線引き。「楽観更新なし」はサーバ権威（BR-U2-03）と UI の整合の固定として重要。

### Q6【Testability】PU2-1〜8 の PBT/統合の振り分け
- **★A（推奨）**: **純粋ロジックは PBT（Hypothesis）**、**D1・フロー依存は統合テスト**（`tests/integration/` 流用）に振り分け:
  - PBT: **PU2-1**（`serialize`/`deserialize` ラウンドトリップ, PBT-02）、**PU2-6**（`select_likert_targets` 決定論・fixed 包含・層網羅・件数, PBT-03 系）、**PU2-3**（`derive_phase` 単調性）。
  - integration（実 D1・`/api/*` 越し）: **PU2-2**（再開の非重複）、**PU2-4**（判定冪等）、**PU2-5**（練習の集計除外整合）、**PU2-7**（Likert 初回不変）、**PU2-8**（完了順序保証）。
  - PBT 強制セットは U1/U4a と同一（PBT-02/03/07/08/09）。統合ハーネスは U1/U4a のものを流用（参加者フロー一巡を検証）。
- **B**: すべて統合テストで検証。→ 述語（フェーズ導出・Likert 選定）の反例探索が弱くなる。

[Answer]: A — 純粋ロジックは PBT（PU2-1/3/6）、D1・フロー依存は統合（PU2-2/4/5/7/8）。補足: PU2-3（derive_phase 単調性）を PBT 側に置けるのは derive_phase が純粋述語（FD Q1=A の帰結）だから＝設計の純粋性がテスト戦略に還元。統合ハーネスは U1/U4a の実 D1 ハーネスを流用し参加者フロー一巡（/api/* 越し）を検証。

### Q7【Data/Migration】migration 0003 + AssignmentParams 拡張
- **★A（推奨）**: `migrations/0003_likert_unique.sql` を **versioned** で追加（`likert_responses` に `UNIQUE(token, target_ref)`、BR-U2-17）。**新規プロジェクトで既存行なし**のため安全。`AssignmentParams.likert_fixed_targets: list[str] | None = None` を `schema/` に追加（BR-U2-15）。適用は `wrangler d1 migrations`（dev→prod）、0002 と同じ流儀。schema/ とテストを同時更新（U2 スコープ）。
- **B**: UNIQUE を張らずアプリ層で重複排除。→ 競合窓が残る（U1-NFR-04 が DB 側保証を採った方針に反する）。

[Answer]: A — `migrations/0003_likert_unique.sql`（versioned, `UNIQUE(token, target_ref)`）+ `AssignmentParams.likert_fixed_targets` 追加。適用は 0002 と同じ流儀（dev→prod、適用→デプロイの順）。DB 側一意制約による保証は U1-NFR-04 の一貫適用（アプリ層重複排除 B は競合窓が残るため不採用）。

### Q8【Reliability】クライアント再送・ネットワーク失敗のセマンティクス
- **★A（推奨）**: **正しさはサーバ冪等が保証**（判定/Likert=初回不変・Survey=upsert, BR-U2-11/17/21）。クライアント再送は **UX 目的の軽いリトライ**（指数バックオフ程度）で、二重登録は原理的に起きない。at-least-once/exactly-once の追加インフラ（メッセージキュー等）は**設けない**。セッション/トークンに**有効期限は設けない**（in_progress は非アクティブでも再開可能。ただし露出集計からは 48h 非アクティブで除外＝BR-04、これは集計の話でトークン失効ではない）。
- **B**: サーバ側にリクエスト ID による重複排除層を別途設ける。→ 既存の (token,pair_id)/(token,target_ref) 一意制約で足りるため冗長。

[Answer]: A — 正しさはサーバ冪等が保証、クライアント再送は UX 目的の軽いリトライ。追加インフラなし。トークン有効期限なし。補足: 「非アクティブ 48h の露出集計除外（BR-04）はトークン失効ではない」を明文化＝「離脱した参加者は後日再開できるか＝できる」が要件文書に自己記述される。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-requirements.md`（U2-NFR-NN）/ `tech-stack-decisions.md`（U2 追加分）を生成 → 標準 2 択（Request Changes / Continue → **NFR Design〈U2〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す（監査証跡の自己完結）。
