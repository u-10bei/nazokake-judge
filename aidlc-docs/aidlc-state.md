# AI-DLC State Tracking

## Project Information
- **Project Type**: Greenfield
- **Start Date**: 2026-07-12T01:50:30Z
- **Current Stage**: **CONSTRUCTION PHASE 完了**（U1/U4a/U2/U3/U4b 全て CLOSE, 2026-07-15）→ OPERATIONS
- **Architecture Decision**: 案 A′ = 静的フロント(バニラ JS) + Cloudflare Python Workers(raw workers API + Pydantic v2, **src/ レイアウト F-8**) + D1、PBT=Hypothesis

## Workspace State
- **Existing Code**: No
- **Reverse Engineering Needed**: No
- **Workspace Root**: /home/llm-user/nazokake-judge

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Extension Configuration
| Extension | Enabled | Decided At |
|---|---|---|
| Security Baseline | No | Requirements Analysis |
| Resiliency Baseline | No | Requirements Analysis |
| Property-Based Testing | Partial (enforce PBT-02/03/07/08/09) | Requirements Analysis |

## Execution Plan Summary
- **Stages to Execute**: Application Design, Units Generation, Functional Design, NFR Requirements, NFR Design, Infrastructure Design, Code Generation, Build and Test
- **Stages to Skip**: Reverse Engineering (Greenfield)
- **Risk Level**: Medium (割当ロジックの正しさが BT 推定に直結)

## Stage Progress
### 🔵 INCEPTION PHASE
- [x] Workspace Detection
- [x] Reverse Engineering (SKIPPED - Greenfield)
- [x] Requirements Analysis
- [x] User Stories
- [x] Workflow Planning
- [x] Application Design
- [x] Units Generation

### 🟢 CONSTRUCTION PHASE — per-unit ループ（U1→U4a→U2→U3→U4b）
#### U1: 共有基盤
- [x] Functional Design (承認済み 2026-07-12)
- [x] NFR Requirements (承認済み 2026-07-12)
- [x] NFR Design (承認済み 2026-07-12)
- [x] Infrastructure Design (承認済み 2026-07-12, H-1=(c) 確定)
- [x] Code Generation Part 1 (Planning) — 承認済み 2026-07-13
- [x] Code Generation Part 2 (Generation) — 承認済み 2026-07-13（unit+PBT 19 passed, α/S 較正確定）
- [x] Build & Test — 承認済み 2026-07-13（unit+PBT 19 + integration 4 全 PASS）。**U1 完了**

#### U4a: スクリプト先行分（token_issue / pool_ingest + 管理 API 先行導入）
- [x] Functional Design (承認済み 2026-07-13。Q5=X: Item.body を D1 格納=U1 波及。BR-U4a-12 発行時充足ゲート)
- [x] NFR Requirements (承認済み 2026-07-13。全 7 問★A + pool_sufficiency 単一実装)
- [x] NFR Design (承認済み 2026-07-13。全 5 問★A、DP-U4a-01〜07 / LC-U4a-01〜06)
- [x] Infrastructure Design (承認済み 2026-07-13。全 5 問★A。RT-1 を U4a で消化)
- [x] Code Generation Part 1 (Planning) — 承認済み 2026-07-13（全 5 決定点★A）
- [x] Code Generation Part 2 (Generation) — 承認済み 2026-07-13（unit+PBT 27 + integration 7 全 PASS。RT-1 CLOSED）
- [x] Build & Test — Code Generation 内で実施（integration 実 D1 全 7 シナリオ + unit/PBT 27）。**U4a 完了**

#### U2: 参加者セッション（participant）
- [x] Functional Design — **承認済み**（2026-07-14）。Q3=X（Likert 選定機構実装・方針は後日）、他は★A。**H-3 宿題クローズ**（XC-02=DB 行復元）。成果物 4 件（business-logic-model / business-rules BR-U2-01〜30 / domain-entities / frontend-components）
- [x] NFR Requirements — **承認済み**（2026-07-14）。全 8 問★A。U2-NFR-01〜15（出自秘匿の NFR 昇格・no-store・相関ハッシュ・楽観更新なし・migration 0003）+ TSD-U2-01〜06
- [x] NFR Design — **承認済み**（2026-07-14）。全 5 問★A。DP-U2-01〜07（出自秘匿の型排除が要）+ LC-U2-01〜08 + Repository/ビュー型拡張
- [x] Infrastructure Design — **承認済み**（2026-07-14）。全 5 問★A。Workers Static Assets 同一オリジン配信・CORS なし・migration 0003・deploy.yml 無変更・beta 3 点検証を Code Gen 冒頭に
- [x] Code Generation Part 1（Planning）— **承認済み**（2026-07-14, 全 6 決定点★A / Q1=U1 FD Q4=B の生成方法改訂を記録）
- [x] Code Generation（Part 1+2）— **承認済み・完了**（2026-07-14, 全 16 ステップ / 6 決定点★A）。unit+PBT 33 緑（U1/U4a 回帰含む）。実機で 2 バグ捕捉・修正: **F-7**（seed の D1 bind オーバーフロー→48bit）・**F-8**（バンドル module root→src/ レイアウト移行）+ entry.py catch-all→404。Q1=U1 FD Q4=B の生成方法改訂を記録
- [x] Build & Test — **完了**（2026-07-14）。unit+PBT **33 緑** / integration **全 9 項目 PASS**（実 D1/miniflare, result-u2-integration.json: PU2-2/4/5/7/8 + 一巡・出自秘匿）/ **本番初回デプロイ完了**（migrations 0001+0002+0003 本番適用済み）/ beta 3 点は dev 実測で確定（①api 到達・③未知=404・④admin 401・health 200）。**残**: F-8+catch-all 反映の**再デプロイ後の prod curl 疎通**（①=200・③=404・②`/`=index.html）→ beta 最終 CLOSE（自明・疎通のみ）。**U2 完了**

#### U3: 研究者・管理（admin）
- [x] Functional Design — **承認済み**（2026-07-15）。Q1=X（ExportBundle に items/pair_index/exported_at 追加）他★A。成果物 4 件（business-logic-model / business-rules BR-U3-01〜10 / **domain-entities: ExportBundle 正本** / frontend-components）。U3 は読み取り専用（migration なし）
- [x] NFR Requirements — **承認済み**（2026-07-15）。全 5 問★A。U3-NFR-01〜11（エクスポート秘匿・CORS なし決着・読み取り専用）+ TSD-U3-01〜05。PBT は PU3-3 のみ
- [x] NFR Design — **承認済み**（2026-07-15）。全 4 問★A。DP-U3-01〜05（body 非含有=型排除・練習除外の SQL 出力段保証）+ LC-U3-01〜06。管理 HTML=ui.py 定数
- [x] Infrastructure Design — **承認済み**（2026-07-15）。全 4 問★A。差分実質ゼロ（/admin/* GET 追加のみ・migration/シークレット/CORS/assets/deploy.yml 無変更）。curl 経路を U4b 自動化の正として申し送り
- [x] Code Generation Part 1（Planning）— **承認済み**（2026-07-15, 全 4 決定点★A / Q3=標準 csv モジュール）
- [x] Code Generation（Part 1+2）— **承認済み・完了**（2026-07-15, 全 10 ステップ）。unit+PBT 39 緑（回帰含む）・integration 全 8 項目 PASS（実 D1）+ 軽微修正 2 点（filename コロン除去・winrate 未出場注記）。migration/wrangler/deploy 変更なし
- [x] Build & Test — **完了**（Code Generation 内で実施: integration 実 D1 全 8 項目 + unit/PBT 39）。**U3 完了**

#### U4b: BT 集計スクリプト（bt_aggregate・最終ユニット）
- [x] Functional Design — **承認済み**（2026-07-15, Request Changes 反映=MM 擬似データ定式化・BR 番号是正）。US-R04。MM=Hunter 2004・観測ペア限定正則化（w̃_ij=w_ij+α/2, ñ_ij=n_ij+α）・最大成分内 Σθ=0・target_ref=item_id 較正・BTResult〈source エコーバック・除外 item 可視化〉。BR-U4b-01〜13。schema/bt.py・DDL 変更なし
- [x] NFR Requirements — **承認済み**（2026-07-15）。全 5 問 A。U4b-NFR-01〜13（行順序不問決定論=item_id 正準ソート・未収束 exit0・token 非参照・終了コード網羅）+ TSD-U4b-01〜06
- [x] NFR Design — **承認済み**（2026-07-15）。全 4 問 A。DP-U4b-01〜04（正準集計 3 点セット・restrict_to_component 切り出し）+ LC-U4b-01〜07（6 純関数+CLI）。**α 適用位置の不変条件を明文固定**（aggregate=生カウント / α は fit_bt 内部のみ / BTResult.matches/wins は生＝BR-U4b-08/PU4b-6 U3 突合の成立条件・Code Gen Step へ一行申し送り）
- [x] Infrastructure Design — **承認済み**（2026-07-15）。全 4 問 A。差分ほぼゼロ（`scripts/bt_aggregate` + `src/schema/bt.py` のファイル追加のみ・Worker/D1/deploy/migration/secret/CORS/assets 全て無変更）。入力=U3 curl 経路（取得と推定の分離・スナップショット監査単位=ファイル）・schema_version 検証・PBT+unit で検証完結（実機確認対象なし）・α 適用位置の不変条件を Code Gen へ申し送り
- [x] Code Generation Part 1（Planning）— **承認済み**（2026-07-15, 全 4 問 A / Q1=パッケージ分割 / Q2=α 適用位置不変条件 / Q3=α=1.0・max_iter=10000・tol=1e-10 / Q4=回帰全緑ブロッキング）+ Step 6 に rank 同値処理・Step 10 に α 感度注記を追記
- [x] Code Generation（Part 1+2）— **承認済み・完了**（2026-07-15, 全 10 Step）。`src/schema/bt.py`（BTResult/BTItemScore/Calibration）+ `scripts/bt_aggregate/`（aggregate/graph/mm/calibrate/assemble/__main__ = LC-U4b-01〜07 一対一）。unit+PBT **57 緑**（U1/U2/U3/U4a 回帰含む・ci profile）。**PBT 反例で 1 発見**: PU4b-1 単調性は正則化 ON では**次数対称な完全総当たり**でのみ堅牢（不規則グラフは α が疎 item を非対称に縮め順位入替＝BR-U4b-01「疎な新作ほど強く縮む」の実証）→ ジェネレータを完全総当たりに限定。**α 適用位置の不変条件**を aggregate/mm/assemble 3 箇所 + PU4b-6 で二重固定。**migration/wrangler.toml/deploy.yml/src/backend 変更なし**。実機 CLI 一巡確認（pro→rank1・新作→最下位・孤立 item=null・Σθ=0・calibrated が Likert 尺度へ写像・版検証 exit 1/0）
- [x] Build & Test — **承認済み・完了**（2026-07-15, 最終確認承認）。unit+PBT **61 緑** + 実データ CLI 一巡・終了コード契約・非連結/較正/除外 item 検証。**Request Changes 1 件反映（クローズ前必須・承認済み）**: `--alpha 0/負値`で `math.log(0)` 未捕捉例外（生トレースバック漏れ）/ 負値は θ 全 0 の無意味結果を exit 0 返却 → **CLI 境界でパラメータ検証**（`--alpha>0`/`--max-iter≥1`/`--tol>0` を強制・違反は EXIT_FAIL＝U4b-NFR-11 の非0リストに「パラメータ不正」追加, DP-U4b-03）+ unit テスト 4 ケース追加。README 終了コード表更新。U4b は非デプロイ・実機確認対象なし（U4b-NFR-13）ゆえ PBT+unit で検証完結。**U4b 完了 = 全ユニット完了**

#### U5: 出題停止（item retirement・追加要件 2026-07-17）— **完了**
**背景**: **著作権上の配慮**で投入済み作品の一部を今後出題しない必要が発生。運用者の確定要件: **物理削除は不要 / それまでの判定結果は有効のまま / 進行中セッションへの反映は不要（新規セッションのみ）**。
- [x] Functional Design — **承認済み**（2026-07-17）。全 6 問 A。成果物 3 件（business-rules BR-U5-01〜13 / business-logic-model / domain-entities）。**レビュー指摘 3 点を反映**: ①**読み取り経路の分割を「関数の分割」で明文化**（BR-U5-02: `list_items()` 全件のまま凍結・`list_active_items()` 新設。`list_items()` 自体にフィルタを足すと **export 縮小→PU3-3 違反→U4b 破壊** と **旧セッションのフォールバック導出変化→「新規のみ反映」破れ** の**両輪が同時に壊れる**＝MM 式・α 適用位置と同系の明文固定案件）②**`retired_at`=現在状態 / `admin_log`=履歴の正**（BR-U5-13・unretire が NULL に戻すため）③**練習試行の経路を調査**（BR-U5-02b: 別経路なし・`generate_pairs` が同一プール同一呼び出しで先頭を練習とするだけ→active フィルタが自動で効き漏れなし）。**追加判明**: `select_likert_targets` の導出は **3 箇所**（build_view/check_complete/submit_likert）＝一部だけ切替で「表示されたターゲットの送信が拒否される」不整合→単一アクセサ集約必須。`pairs.item_left/right` に **FK** あり＝物理削除は FK 違反（論理削除が唯一の正解の構造的根拠）
- [x] NFR Requirements — **承認済み**（2026-07-17）。全 5 問 A。U5-NFR-01〜13 + TSD-U5-01〜08。**PBT-02 を U5 で新たに該当と判断**（U4b は非該当明記だったが `sessions.likert_targets` の JSON 保存/復元を新設ゆえ＝順序を含むラウンドトリップ, U5-NFR-07・質問になかった論点ゆえ要確認）。論点: migration 0004 の安全性/後方互換・**PBT で要件の両輪に網**（PU5-1 新規から消える / PU5-2 旧セッション不変 / PU5-3 冪等 / **PU5-4 export が縮まない=BR-U5-02 の直接の検出網**・混在プールのジェネレータ）・EXPORT_FORMAT_VERSION 据え置きの保証（U3/U4b のテストを書き換えたら設計違反のシグナル）・監査ログの NFR 昇格・Security 差分なし
- [x] NFR Design — **承認済み**（2026-07-17）。全 5 問 A。DP-U5-01〜04 + LC-U5-01〜07。**調査で前例発見**: `Session` には既に `exposure_snapshot`（JSON カラム ↔ 型付きフィールド・`save_pair_sequence` の同一 batch で原子保存）の前例があり、`likert_targets` は完全に同型 → Q1 の判断材料。論点: **likert_targets の型の置き場と保存の原子性**（★A=Session に載せ save_pair_sequence の同一 batch へ＝「ペア列は保存されたが Likert 未保存」の中間状態を原理的に排除・PBT-02/XC-02 に自然に載る）・`list_active_items()` の配置と呼び出し先の LC 固定・**`get_likert_targets` の層**（サービス層=session.py / domain は無改修＝層の逆流を作らない）・**冪等性を SQL の WHERE 句で作る**（`AND retired_at IS NULL` が初回時刻保持を保証）・適用性 N/A
- [x] Infrastructure Design — **承認済み**（2026-07-17）。全 4 問 A。差分ほぼゼロ = **migration 0004** + `/admin/items/retire|unretire` POST 追加のみ（`wrangler.toml`/`deploy.yml`/`frontend`/シークレット/CORS/assets すべて無変更・CLI は非デプロイ）。論点: 適用順 migration→deploy（`deploy.yml` の既存順で自動的に守られる）・**本番未デプロイゆえ初回デプロイで 0001〜0004 一括適用＝旧セッションは実在しない**（フォールバックは稼働後適用の保険）・**PU3-3 緑がデプロイの前提＝BR-U5-02 違反コードは本番に出られない**・beta/UI 目視不要
- [x] Code Generation Part 1（Planning）— **承認済み**（2026-07-17）。14 Step + 決定点 4 問 A。**調査事実**: `build_view` は `get_session` を呼ばず seed をトークンから導出 → 保存値を読むには追加クエリが要る（Q1 の論点）。決定点: `get_likert_targets` の実装方式（★A=内部で get_session＝呼び出し側のシグネチャ不変ゆえ 3 箇所集約が最も素直に完遂される）/ 分類は事前 SELECT 1 回（★B の meta.changes だけでは already_retired と not_found が区別できない）/ CLI は引数列挙 / 回帰全緑ブロッキング（**PU3-3 緑=禁止事項非違反の証拠**・**U3/U4b のテストを書き換えたら設計違反のシグナル**）
- [x] Code Generation（Part 1+2）— **承認済み・完了**（2026-07-17, 全 14 Step / 全 4 決定点 A）。`migrations/0004_item_retire.sql` + `list_active_items`（`list_items` 凍結）+ `retire_items`/`unretire_items` + `Session.likert_targets` 同一 batch 原子保存 + `get_likert_targets`（**3 箇所集約完遂**）+ `/admin/items/retire|unretire` + `scripts/pool_retire.py` + `ItemRetireRequest`/`RetireResult`。**unit+PBT 76 緑**（既存 61 + U5 15）/ **integration 実 D1 37/37 PASS**（U5 13 + 回帰 U2 9/U3 8/U4a 7・**0004 適用後**）。**変更禁止対象はすべて無変更**（wrangler.toml/deploy.yml/frontend/Item/ExportItem/**EXPORT_FORMAT_VERSION 1.0.0**/U3・U4b のコードとテスト）
  - **Part 1 からの逸脱 1 件**: **PU5-3/PU5-4 を PBT ではなく integration に配置**（SQL の意味論ゆえダブルで再現してもダブルを検証することにしかならない）。ダブル（`tests/fakes.py`）はワイヤリング検証専用（PU5-1/PU5-2）と責務を明記。**PU5-4 は BR-U5-02 の検出網として実 D1 で機能**（export の items 集合が縮まないことを実測）
  - **実装中の発見 2 件**: ①**D1 は Python None の bind を拒否**（既存コードが明記）→ SQL リテラル NULL の既存イディオムに合わせ `_session_insert_stmt` を分岐 ②**PBT-02 が `[]` と `None` の区別を炙り出した**（`[]`=Likert 対象なし確定 / `None`=旧セッション。潰すと全件導出フォールバックが走り**本来ないはずの Likert 対象が生える**）→ `get_session` を truthy 判定から `is not None` に修正
  - **実機で確証**: 「参照済み item は body 更新を拒否されるが**廃止はできる**」（BR-U5-05 の整理）を実 D1 で確認
  - **運用文書 3 冊に廃止手順を追記**（runbook §2-⑥-b + トラブルシュート 4 症状 / manual-p-rsch §4）
- [x] Build & Test — **承認済み・完了**（2026-07-17, Code Generation 内で実施）。unit+PBT **76 緑** + integration 実 D1 **37/37 PASS**（U5 13 + 回帰 U2 9/U3 8/U4a 7・migration 0004 適用後）。beta 検証・参加者 UI 目視は不要（新規ランタイム機構なし・画面不変）。**U5 完了**
- 調査で判明した設計の前提: ①削除 API も廃止フラグも未実装（＝設計上の意図: 凍結ガード BR-U4a-03 が更新すら拒否）②**エクスポートは body 非含有ゆえ廃止 item を残せる → 自己完結性 BR-U3-07 維持 → U4b 無改修で「過去結果は有効」が成立**③ペア列は開始時に一括保存＝「新規のみ反映」なら配信段の改修不要 ④**⚠️ Likert ターゲットは未保存・毎回導出 → プールを絞ると進行中セッションのターゲットが変わる**（Q2 の核心）⑤**⚠️ 廃止フラグ付与は UPDATE ＝凍結ガード BR-U4a-03 と正面衝突**（Q3 の核心）。波及: migration 0004 / U4a / U1 / U2 / U3（確認のみ）/ **U4b 無変更**

#### U6: 層拡張（下帯アンカー）+ 事前生成割当（追加要件 2026-07-20）
**背景**: 実データ確定（**n=38 / E=8 / J=228 / m=12**）。層別 = プロ作 10（N1〜N8 許諾待ち+S04・S10）/ **下帯アンカー 2（S03・S13）** / 編集・自作 14 / AI 生成 9 / ルールベース 3。
**決定済み**: 許諾は待たずに開始（NG なら U5 の `pool_retire`。エクスポートに本文は含まれないため収集済みデータに著作物は残らない）／**E=8 維持 + 事前生成リスト方式**。
- [x] Functional Design — **承認済み**（2026-07-20）。**逐次更新は (b) 推定の逐次更新として存続**と確定（設計メモ §4 の改訂対象は「再生成」の文言のみ）。Q1=B / Q2=D / Q3=A+2 / Q4=A′ / Q5=A′ / Q6=A / Q7=A。BR-U6-01〜19。**レビューで私の誤り 2 件が是正**: ①事実 #4（`select_likert_targets` は `likert_fixed_targets` 最優先→10件全指名でラウンドロビン不走行＝**Q2 はコード変更なしで解決**。当初は補充パスのみの部分読み）②Q4 の ★A が算術破綻（E=10 分割で 8 枠消化＝44 辺未消化で 12-正則が壊れる→**A′ 8スロット固定+補充トークン**）。**決定的事実**: **FR-03 が「適応的サンプリングは v1 不採用」と既決**（要件 L52/非目標表 L162）→ **完全静的化は既決要件への復帰**。**実測で確定した事実**: ①`items.layer` に **CHECK 制約が実在**→migration 0005 でテーブル再構築必須（「データ投入だけ」では済まない）②`ExportItem.layer`/`WinrateRow.layer` は **`str` で値域列挙なし**→**EXPORT_FORMAT_VERSION 版上げ不要**・U3/U4b 無対応 ③`pool_sufficiency` が `for layer in Layer` ゆえ「4層非空」が自動的に「5層非空」に ④**`select_likert_targets` は層ラウンドロビン**→5層化で下帯 2 件（プールの5%）が**較正アンカーの20%**を占め回帰を歪める ⑤`generate_pairs` の呼び出しは **`session.py:53` の 1 箇所のみ**＝外科的置換可 ⑥**同一ペア再提示ゼロは `used: set[frozenset]` で既にハード制約** ⑦練習ペアは本番と同一プール由来＝**初見性が損なわれる** ⑧**出現回数は `token`+`pair_index` から導出可能**＝スキーマ追加なしで共変量検証できる
- [x] NFR Requirements — **承認済み**（2026-07-20）。全 5 問 A + 追加 7 点。U6-NFR-01〜22 / TSD-U6-01〜10。**★レビューで BR 反映漏れを検出・追補**: ブロック単位の連結性が FD に存在しなかった（BR-U6-10 ②はプラン全体のみ）→ **BR-U6-20 を追補し BR-U6-10 ⑥ に収載**（BR-U6-13 (b) 推定逐次更新の前提）。実測では貪欲配分 30 試行でブロック1・2 とも成分 1 だが**構成上の保証ではない**ため PU6-7 として PBT 化。**🚨 実測でブロッキング級のリスクを検出**: **FD の 0005 DDL 案は実データがあると `FOREIGN KEY constraint failed` で失敗する**（`pairs` が `items` を FK 参照する行を持つ状態では `DROP TABLE items` 不可）。0002 が通ったのは「新規プロジェクトで既存行なし」だったため＝**0005 は初めて「データがある状態での親テーブル再構築」**。`PRAGMA foreign_keys=OFF`/`defer_foreign_keys=ON` はいずれも **D1 の migration 実行環境では効かない**（実測）→ **子行の退避方式**（`pairs_bak` 経由）で成功を確認（`retired_at` 保全・FK 整合・anchor/practice 投入可・不正層値の拒否維持）。**FD domain-entities の DDL を訂正済み**。副次確認: **D1 は migration を原子的にロールバックする**
- [x] NFR Design — **承認済み**（2026-07-20）。全 5 問 A + 追加 5 点。DP-U6-01〜08 / LC-U6-01〜14。**★レビューで BR 追補 3 件**: **BR-U6-21 内容制約の入力チャネル**（①〜⑥は形式制約だけで閉じており**タスク5 §3 の内容制約が生成器仕様から欠落**していた。禁止/忌避/濃縮/提示順の 4 種別を巡回グラフの幾何に写し、**制約ファイルを CLI 入力**に＝中身は研究側・器は U6。**実測で 3 目的の両立を確認**: 禁止辺 8 本違反 0 / 層間 0.706 / 濃縮 9-9 本）・**BR-U6-22 期待組成の入力検証**（anchor を REQUIRED_LAYERS から外した裏返し）・**BR-U6-15 に練習ペア全量再提示を追記**。**構造的影響**: LC-U6-02 `placement`（制約付き探索）と LC-U6-05 `sequencing`（順序付け）が独立 LC として必要に。**調査で判明**: ①**`scripts` は `backend` を一切 import していない**（全 CLI で確認）→ `plan_generate` が使う `POOL_LAYERS` は **`schema` に置くしかない**（配置が決定づけられる）②`pool_sufficiency` は「充足判定の唯一の実装」ゆえ置換は 1 関数内で完結させる ③**巡回グラフ `C_n(1..d)` は距離 1 の輪を含むため必ず連結**＝全体連結は構成的に保証可能。**★実測で決定的知見**: **層間比率は円周上の item 配置で決まる**（同じ辺集合・同じ正則次数でも **grouped 0.390 ❌ / interleave 0.728 ✅ / shuffle 0.772 ✅**）→ **配置は生成アルゴリズムの必須要件**（「たまたま通る」に委ねられない）
- [x] Infrastructure Design — **承認済み**（2026-07-20）。Q1=A′ / Q2=A+2 / Q3=A / Q4=A+2。**★レビューで私の ★A の欠陥を是正**: 「フォールバック版の item は activate 時に入れ替える」は **C を不採用にした理由（プール入替と凍結ガードの衝突）を穏やかに再導入**していた → **A′ = 両セットをリポジトリにコミットして固定（commit 履歴+ハッシュが証跡）・D1 には選択セットのみ投入**（**D1 内での切替の時間窓が存在しない**: activate ガードにより切替は収集開始前のみ + カットオーバーは許諾判明後ゆえ pool_ingest 時点で使用セット確定済み）。**BR-U6-12 を改訂**。**✅ セット別確定値**: 成立版 n=38/J=228/[29×4,28×4] / **フォールバック版 n=34/J=204/[26×4,25×4]**（pro6・予約は S02・S11・S12・S19 の 4 件）。**構成可能性を実測**（辺数 204 一致・gap=0・連結成分 1・充足通過・層間 0.716）。n=36 へ寄せない（均一分割は美観・自由在庫は温存確定・層割当の再議論回避）。**★`plan_generate` の入力は（プール・期待組成・制約ファイル）の三つ組でセット単位**＝制約ファイルもセット別（pivot 再走・N8 濃縮消滅・N 系隣接回避消滅）。差分は **migration 0005 + `/admin/plan`・`/admin/plan/activate` の POST 2 本 + `plan_generate`（非デプロイ）**。**U5 と決定的に違う点**: 0004 は安全な no-op 移行だったが **0005 は「データがある状態での親テーブル再構築」で適用タイミングに制約がある**（U6-NFR-04）＝インフラ面の重心。**調査で 2 論点を検出**: ①**`assignment_plan` に FK を張ると 0005 適用後に items 参照 FK が 2→4 本**に増え、将来の items 再構築の退避対象が増える負債になる ②**成立版/フォールバック版で参照 item 集合が異なるため、FK を張ると両方を `items` に置く必要があり期待組成 n=38 と衝突する** → ★A は **FK を張らず投入時にアプリ層で検証**（負債を増やさず両セットを独立投入できる）。加えて**運用順序の必然性**（プラン投入はプール確定後・トークン発行は activate 後＝束縛先が定まるため）を手順化
- [~] Code Generation Part 1（Planning）— **生成・承認待ち**（2026-07-20）。**19 Step**（これまでで最大: migration 0005 + 生成器 7 コンポーネント + API 2 本 + 引き当て置換 + 補充トークン + PBT 8 本）+ 決定点 6 問。決定点: CLI を生成/投入で分割（BR-U6-12 の「コミット」が間に挟まるため）/ LC 一対一のパッケージ分割 / 制約ファイルは JSON・`plan_set` 内包で誤適用防止 / **placement の目的関数は辞書式**（禁止=ハード → 層間はゲート到達で頭打ち → 濃縮最大化 → 忌避）/ プランは `plans/<set>/` にコミット（**gitignore 非該当を実測確認**）/ 回帰全緑ブロッキング
  - **事前生成の実現可能性を実測**: **J=228 は n=38 の 12-正則グラフ（38×12/2=228）と完全一致** → 構成して 8 評価者へ配分成功（**露出 gap=0.000**・評価者内同一項目 ≤3・同一ペア重複 0）。対比: オンライン方式は連結成分=1 は 20/20 達成も**相対 gap 最悪 0.66〜0.75**（露出 min=8/max=17＝**項目間 2 倍の精度差**）＝**較正 α=0.7 の境界上**（p=3/α=0.7/S=30 は n=95 での較正値ゆえ n=38 では保証されない）→ **事前生成により較正が不要になる**

### 🟡 OPERATIONS PHASE
- [x] **Operations — 方法論上は実行対象なし**（`aidlc-workflows/.../operations/operations.md`: "This phase is currently a placeholder"・"The AI-DLC workflow currently ends after the Build and Test phase in CONSTRUCTION"）。plan/質問/ゲートの規定は存在せず、**AI-DLC は U4b Build & Test 承認をもって完走済み**。
- [x] **運用 Runbook 作成**（2026-07-15）— 定義の Future Scope（production readiness / maintenance）に相当する実運用手順書 `aidlc-docs/operations/runbook.md`。初回セットアップ / デプロイ（品質ゲート順）/ 一巡手順（プール投入→発行→配布→参加→進捗→エクスポート→BT 集計→α 感度）/ 監視（wrangler tail・admin_log の秘匿方針）/ トラブルシューティング 9 症状 / 運用注意 / 未消化事項。実装済み CLI・API の一次情報に基づく
  - **作成時に運用地雷 1 件を発見・修正**: `scripts/token_issue.py` の docstring 使用例が `--url-template '.../s/{token}'` を示すが、フロントは `?token=` クエリを読み（U2-NFR-04）未知パスは 404（Infra Q2・SPA フォールバック不使用）＝**例をコピーすると全参加者が 404**。U4a 時点の例が U2 フロント確定後に未更新だったもの。docstring + `--url-template` help を `/?token={token}` に修正（ロジック不変）
- [x] **ペルソナ別説明書 2 冊**（2026-07-15）— Inception 定義（`inception/user-stories/personas.md`: P-EVAL 評価者 / P-RSCH 研究者の 2 ペルソナ）に忠実に作成。実装済みの実画面・実 CLI に基づく
  - `operations/manual-p-eval.md`（**参加者へ配布可能な本文**・平易な日本語・モバイル前提）: タスク概要/所要 25〜35 分・進め方（教示→練習→本番約 40 ペア→Likert→アンケート→完了）・中断再開・困ったとき 4 症状・プライバシー。**出自秘匿を最優先制約として本文は 4 層構成に一切触れない**（冒頭に研究者向け警告枠: 「AI と人間の比較」等と説明すると要求特性で実験の妥当性が壊れる旨・配布時は枠を削除）
  - `operations/manual-p-rsch.md`（研究者向け・**runbook と重複させず「全体像と結果の読み方」に特化**・手順は runbook へ導線）: 装置の意義（なぜ比較判定か）・できること×US-R01〜06・実験設計上の 3 約束（出自秘匿=人間側の運用が最後の穴 / 練習除外 / 露出均衡・層間比率）・充足条件の具体値・**結果の読み方**（暫定勝率 vs BT の違い=論文には BT・θ の 0 は平均・component 越えの比較禁止・bt_score=null は「弱い」ではない・非連結の意味・α 感度チェック）・Pain Point 対処・データ取扱い
  - `runbook.md` 冒頭に 3 文書の使い分け表を追加

## Current Status
- **Lifecycle Phase**: CONSTRUCTION 再開（**U6 = 追加要件 2026-07-20**）。U1〜U5 は CLOSE 済み・運用文書 4 冊完備
- **Current Stage**: **U6 層拡張+事前生成割当 — Code Generation Part 1（Planning）生成・承認待ち**（standardized 2-option GATE）
- **Units**: U1 基盤 / U2 参加者 / U3 研究者管理 / U4 スクリプト（実装順序 U1→U4a→U2→U3→U4b）**全て CLOSE**
- **Completed**: U1／U4a（2026-07-13）／U2（2026-07-14）／U3（2026-07-15）／**U4b（2026-07-15 完了）**
- **Next Stage**: U6 FD 承認 → NFR Requirements〈U6〉→ …（per-unit ループ）。**本番デプロイは U6 完了後**（migration 0005 を同時に載せられる）
- **Status**: U1〜U4b 完了（判定装置の一巡クローズ達成）。運用文書 3 冊完備（`operations/`）。**U5 = 著作権配慮による出題停止**の FD Part 2 生成（全 6 問 A / BR-U5-01〜13）。核心 3 点: **読み取り経路を関数分割で固定**（list_items 凍結 / list_active_items 新設）・**Likert ターゲットの保存化**（3 箇所の導出を単一アクセサに集約）・**凍結ガード BR-U4a-03 との整理**（body/layer 不変ゆえ対象外）。**U3/U4b 無変更・EXPORT_FORMAT_VERSION 1.0.0 据え置き**

## Open Gates / Blockers
（申し送り H-1/H-2/H-3 と同じ追跡方式）

- **G-1（✅ CLOSED, 2026-07-13）: 本番 smoke test 全 PASS = U1 最初の実デプロイの前提条件**
  - **結果**: `infrastructure-design.md §2.1` 第3回（GitHub Actions ubuntu-latest → `pywrangler deploy` → `*.workers.dev/smoke/all`）で**全 5 項目 PASS**（`smoke-test/result-prod.json`, CI artifact）。R-1/R-2 解消・TSD-02 本番確証。
  - **重要な構成変更**: **FastAPI → raw workers API + Pydantic v2**（F-4: FastAPI トップレベル import が起動 CPU 制限 10021 超過）。ハンドラは module-level `on_fetch(request, env)`（F-5）、`workers_dev=true`（F-6）、デプロイは CI 経由（F-1/F-3）。→ TSD-01 改訂・deployment-architecture.md 更新済み。
  - **フォールバック**: 案 B（PHP+SQLite）／TSD-02（pydantic v1/dataclasses）いずれも**発動せず**（フレームワーク差し替えで解消）。
  - **残タスク（ユーザー側・任意）**: Cloudflare 側 smoke Worker / D1（`nazokake-smoke`）の削除可（`smoke-test/` フォルダと workflow はリポジトリ残置＝本実装 CI 雛形）。`CLOUDFLARE_API_TOKEN` は本実装 CI 流用なら残置、しないなら失効。

## Residual Tasks（非ブロッキング）
- **RT-1: `.github/workflows/deploy.yml` の肉付け** — **✅ CLOSED（2026-07-13, U4a Code Generation で消化）**。`deploy.yml` を機能化: `uv sync → test（unit+PBT, 前置ゲート）→ d1 migrations apply --remote(0001+0002) → deploy`（tee パイプ不使用で終了コード保持）。`ADMIN_BASIC_*` は手元 `wrangler secret put`。実デプロイはユーザー環境（Cloudflare 認証）で実行。
