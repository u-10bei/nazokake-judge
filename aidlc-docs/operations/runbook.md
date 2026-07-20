# nazokake-judge 運用 Runbook

**対象**: 研究者（装置の運用者）。**前提**: 全 5 ユニット完了（CONSTRUCTION CLOSE, 2026-07-15）。
**位置づけ**: AI-DLC の Operations は方法論上プレースホルダ（規定なし・Build & Test で完走）。本書はその Future Scope（production readiness / maintenance）に相当する**実運用手順書**であり、実装済みの CLI/API に基づく。

> **文書の使い分け**（ペルソナ定義 = `../inception/user-stories/personas.md`）
> | 文書 | 対象 | 内容 |
> |---|---|---|
> | **本書 `runbook.md`** | P-RSCH 研究者 | **コマンド手順**・デプロイ・監視・リセット・トラブルシューティング |
> | `dry-run-dev.md` | P-RSCH 研究者 | **本番前のドライラン**（ローカル + 実データで一巡を確認） |
> | `manual-p-rsch.md` | P-RSCH 研究者 | 装置の全体像・**結果の読み方**・実験設計上の約束 |
> | `manual-p-eval.md` | P-EVAL 評価者 | **参加者へ配布する説明書**（URL と一緒に渡す） |
>
> **初めて本番に出す前に** → `dry-run-dev.md` でローカル一巡を通してから §1 のデプロイへ。

## 判定装置の一巡

```
① プール投入(U4a) → ② トークン発行(U4a) → ③ 配布 → ④ 参加(U2) →
⑤ 進捗監視(U3) → ⑥ エクスポート(U3) → ⑦ BT 集計(U4b) → 新作の位置確認
```

---

## 0. 初回セットアップ（一度きり）

```bash
# 1) 実 D1 作成（smoke 用 nazokake-smoke とは別）→ database_id を wrangler.toml に転記
npx wrangler d1 create nazokake-judge
#    現在の wrangler.toml: database_id = "ab3e84bc-1d1a-443b-ad02-911c31ec4d6f"

# 2) 管理 Basic 認証を手元から一回きり登録（CI では設定しない = 二重管理回避）
npx wrangler secret put ADMIN_BASIC_USER
npx wrangler secret put ADMIN_BASIC_PASSWORD

# 3) GitHub Secrets（CI 用）: CLOUDFLARE_API_TOKEN（Workers Scripts:Edit + D1:Edit）/ CLOUDFLARE_ACCOUNT_ID
```

**ローカル開発**: `.dev.vars`（gitignore）に `ADMIN_BASIC_USER` / `ADMIN_BASIC_PASSWORD`（雛形 = `.dev.vars.example`）。

## 1. デプロイ

GitHub Actions `deploy` ワークフローを**手動実行**（`workflow_dispatch`）。順序が品質ゲート:

```
uv sync → pytest tests/unit tests/pbt（HYPOTHESIS_PROFILE=ci）→ d1 migrations apply --remote → pywrangler deploy
```

- **テスト失敗ならデプロイされない**（migrations/deploy は後続ステップ）。
- migrations: `0001_init` / `0002_item_body` / `0003_likert_unique`（適用済みなら no-op）。
- デプロイ後の確認:
  ```bash
  curl -s https://<host>/health                    # → {"status":"ok",...}
  curl -s -o /dev/null -w '%{http_code}\n' https://<host>/            # → 200（index.html）
  curl -s -o /dev/null -w '%{http_code}\n' https://<host>/nope        # → 404
  curl -s -o /dev/null -w '%{http_code}\n' https://<host>/admin/      # → 401（未認証）
  ```

---

## 2. 運用手順（一巡）

環境変数は全 CLI 共通:
```bash
export ADMIN_API_BASE=https://<host>          # または各コマンドに --base-url
export ADMIN_BASIC_USER=...
export ADMIN_BASIC_PASSWORD=...
```

### ① プール投入（pool_ingest）

```bash
uv run python -m scripts.pool_ingest items.json --base-url "$ADMIN_API_BASE"
```

- **入力**: JSON 配列 または JSONL。各レコード = `{item_id, layer, body, body_ref?}`。
- **層ラベル（必須）**: `pro`（プロ作品）/ `ai`（AI 生成）/ `edit`（編集・自作）/ `rule`（ルールベース生成）。欠落・不正は投入拒否。
- **初期投入の件数**: **95 件 = `pro`30 / `ai`20 / `edit`30 / `rule`15**（要件 FR-08。かつ**割当アルゴリズムの α/S 較正を実施した構成**ゆえ大きく外さない）。→ 根拠は `manual-p-rsch.md` §4
- **段階投入可**: プール未充足でも投入自体は成功し `sufficiency_warnings` が出る（充足はトークン発行時に強制）。
- **終了コード**: 拒否 or クライアント検証不正があれば **1**。

### ①-b プラン生成 → 投入 → 有効化（U6・事前生成割当）

**U6 以降、トークン発行の前にプランの有効化が必要です**（発行時に `(plan_set, plan_index)` を
束縛するため。**先に発行すると束縛先が未定**になります）。

```bash
# 生成（D1 に触れずファイルを書くだけ）→ verification.md を確認 → **コミット**
uv run python -m scripts.plan_generate --pool items_real.json \
    --composition plans/primary/composition.json \
    --constraints plans/primary/constraints.json \
    --out-dir plans/primary --seed 20260720
git add plans/primary && git commit -m "plan: primary set fixed"

# 投入 → 有効化（★content_hash を再計算して照合してから POST。不一致なら投入せず exit 1）
uv run python -m scripts.plan_ingest plans/primary --activate
```

**生成と投入が別 CLI なのは、間に `git commit` が挟まるため**（BR-U6-12）。1 コマンドだと
コミット前のプランを投入でき、「コミットされたものが投入された」という証跡が成立しません。

**⚠️ 有効化は収集開始前に限られます** — 判定が 1 件でも入ると **409 で拒否**されます
（プランセットの切替は実験の作り直しに相当するため）。切り替えたい場合は §2.5 の方法A で
回答データをリセットしてください。

**⚠️ migration 0005 の適用は「発行済み未消化トークンが無い時点」に限ります**（U6-NFR-04）。
→ 手順の一巡は `dry-run-dev.md` §3.5 で dev リハーサルできます。

### ② トークン発行（token_issue・充足ゲートあり）

```bash
uv run python -m scripts.token_issue 30 \
    --base-url "$ADMIN_API_BASE" \
    --url-template 'https://<host>/?token={token}' \
    --out tokens.dist.txt
```

> ⚠️ **配布 URL は `https://<host>/?token={token}` が正**。フロント（`frontend/app.js`）は `?token=` クエリを読む。`/s/{token}` 等の未知パスは **404**（SPA フォールバック不使用）。

- **発行時充足ゲート（BR-U4a-12）**: プール未充足なら API が発行拒否 → `[error] 発行拒否` + **exit 1**。
- **充足条件**（既定パラメータ: `session_pairs=40`, `k=3`, `cross_layer_min_ratio=0.65`）:

  | # | 条件 | 既定での具体値 |
  |---|---|---|
  | ① | 総数 ≥ `ceil(2×session_pairs/k)` | **総数 ≥ 27** |
  | ② | 4 層すべて非空 | pro/ai/edit/rule に各 1 件以上 |
  | ③ | `(総数−最大層件数)×k ≥ ceil(cross×session_pairs)` | `(総数−最大層)×3 ≥ 26` |

- **出力**: 配布用 URL 一覧（stdout + `--out` ファイル）。**`tokens.dist.txt` は gitignore 対象＝リポジトリに入れない**。

### ③ 配布

`tokens.dist.txt` の URL を参加者へ 1 人 1 本配布。トークンが資格そのもの（＝URL を知る人が参加できる）ため取り扱い注意。

### ④ 参加（U2・参加者側）

参加者はブラウザで URL を開くのみ。トークンは `localStorage` に保存され、以降は再訪でも復元。**サーバ権威**（画面はサーバの `SessionView.phase` に従う）。

### ⑤ 進捗監視（U3）

- **ブラウザ**: `https://<host>/admin/`（Basic 認証）→ 進捗サマリ + 暫定勝率テーブル + エクスポートボタン。
- **CLI**:
  ```bash
  curl -su "$ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD" "$ADMIN_API_BASE/admin/progress"
  curl -su "$ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD" "$ADMIN_API_BASE/admin/winrates"
  ```
- `progress` = `tokens_issued/started/completed` + `judgments_total`（本番のみ）/ `likert_total` / `survey_total`。
- `winrates` は**暫定・非 BT**（正式なスコアは ⑦ の BT 集計）。

### ⑥ エクスポート（U3）

```bash
# JSON（BT 集計の入力・ExportBundle 正本）
curl -su "$ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD" \
     -o export.json "$ADMIN_API_BASE/admin/export?format=json"

# CSV（entity 必須。未指定は 400）
curl -su "$ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD" \
     -o judgments.csv "$ADMIN_API_BASE/admin/export?format=csv&entity=judgments"
#   entity ∈ items | judgments | likert | surveys
```

- **練習ペアは出力段で除外済み**（U4b は再フィルタしない）。
- **`body`（作品本文）はエクスポートに含まれない**（未公表刺激の秘匿・型で排除）。
- `exported_at` がスナップショット識別子。**取得と推定は分離**（ファイルに固定してから集計する＝同一 `export.json` → 同一結果）。

### ⑥-b 作品の出題停止 / 復活（U5・必要時）

**著作権上の配慮**などで、投入済み作品を**今後出題しない**ようにする（**論理削除**）。

```bash
# 出題停止
uv run python -m scripts.pool_retire i001 i002

# 復活（誤操作の回復）
uv run python -m scripts.pool_retire i001 --unretire
```

**反映範囲（重要）**:

| 対象 | 廃止後 |
|---|---|
| **新規セッション** | 廃止 item は**ペア列・練習・Likert のいずれにも出ない** |
| **進行中セッション** | ⚠️ **そのまま出題され続ける**（ペア列は開始時に確定済み）。露出が止まるのは**完了 or 非アクティブ 48h まで** |
| **エクスポート / BT 集計** | **従来どおり**（廃止 item も `items` に残る・**過去の判定結果は有効**） |
| **token_issue** | 母数から除かれる。充足を割ったら**発行拒否**（→ 補充する） |

- **物理削除ではありません**（行は残る）。`pairs` の FK と ExportBundle の自己完結性のため、物理削除は**してはいけません**。
- **D1 直操作（`wrangler d1 execute` での UPDATE）は使わないでください**——**監査ログが残りません**。廃止は **API/CLI 経由が正**（著作権対応の証跡）。
- **廃止履歴は `wrangler tail` の `item_retire` / `item_unretire`** が正（DB の `retired_at` は現在状態のみ）。
- 冪等: 既に廃止済みなら no-op（**初回の廃止時刻を保持**）。存在しない `item_id` は警告のみで exit 0。
- 廃止済み item を `pool_ingest` で再投入しても**廃止のまま**（復活は `--unretire` のみ）。

→ 詳細と設計上の理由: `manual-p-rsch.md` §4 / `../construction/u5/code/README.md`

### ⑦ BT 集計（U4b）

```bash
uv run python -m scripts.bt_aggregate export.json --out bt_result.json

# α 感度チェック（実データ適用時は推奨）
uv run python -m scripts.bt_aggregate export.json --alpha 0.5 --out bt_a0.5.json
uv run python -m scripts.bt_aggregate export.json --alpha 2.0 --out bt_a2.0.json
```

- 既定: `--alpha 1.0` / `--max-iter 10000` / `--tol 1e-10`。**使用値は `BTResult.alpha` に記録**（監査）。
- **α は正の値のみ**（`--alpha 0` 以下はパラメータ不正で exit 1）。α=1.0 は観測 1 回のペアで擬似データが実データと同量＝比較的強い縮小のため、**{0.5, 1.0, 2.0} で順位の頑健性を確認**し論文付録の頑健性記述に使う。
- **出力**: `--out` 指定時は JSON→ファイル・人間可読テーブル→stdout。`--out` 省略時は JSON→stdout（パイプ可能）・テーブル→stderr。
- **読み方**: `bt_score`(θ) が BT 尺度の位置（最大連結成分内で Σθ=0）、`calibrated_score` は Likert 相当尺度、`rank` は推定対象内順位、`bt_score=null` は**推定対象外**（非連結の別成分 or 未出場）。`component` が異なる item 同士は**スコア比較不能**。

---

## 2.5 データのリセット（テスト後のクリーンアップ）

**まず大前提**: 本システムは **dev/prod で D1 を分離**する設計（`wrangler.toml` の `[env.prod]`）。**テストは dev、本番実験は fresh な prod** で回せば、そもそもリセットは不要です。以下は「**本番 D1 でテストしてしまった / 同じ D1 を使い回したい**」場合の手順です。

> **共通の注意**
> - `--remote` を付けると**本番 D1**、付けないと **local(dev) D1** に効きます。本番に効かせるときだけ `--remote`。
> - **`ADMIN_BASIC_*` シークレットは Worker 側**にあり、**D1 を消しても残ります**（再設定不要）。
> - **本番リセット用のエンドポイントは意図的に実装していません**（ボタン一つの全消去は事故のもと）。リセットは下記の `wrangler` 明示コマンドが正。
> - reset SQL の DELETE は **FK 安全な順（子 → 親）**。この順以外は FK 違反になる。

### 方法A：回答データだけ消す（プール温存・最も軽い）

同じ刺激プールで実験をやり直す。トークン・セッション・判定・Likert・アンケートを消し、`items` は残す → **トークン再発行だけで再開**。

```bash
npx wrangler d1 execute nazokake-judge --remote --file=scripts/reset-responses.sql
```

⚠️ `items.retired_at`（出題停止フラグ）も残ります。プールを完全初期化したいなら方法B。

### 方法B：全データを消す（プールごと完全リセット）

新しいプールで一から始める。全 7 テーブルを空にする（`items` も消す）。

```bash
npx wrangler d1 execute nazokake-judge --remote --file=scripts/reset-all.sql
```

→ その後 **プール投入（§2-①）→ トークン発行（§2-②）** から一巡をやり直す。
**スキーマ・migration はそのまま＝再デプロイ不要**（`d1_migrations` にも触れない）。

### 方法C：D1 データベースごと作り直す（最もクリーン・要再デプロイ）

テーブル定義ごと真っさらにしたい場合のみ。

```bash
npx wrangler d1 delete nazokake-judge          # 削除
npx wrangler d1 create nazokake-judge          # 再作成 → 新しい database_id が出る
# → wrangler.toml の database_id を新しい値に書き換える
npx wrangler d1 migrations apply nazokake-judge --remote   # 0001〜0004 を再適用
# → deploy.yml を手動実行して再デプロイ（§1）
```

**代償**: `database_id` が変わるので `wrangler.toml` 書き換え + **再デプロイが必須**。方法A/B で足りるなら不要。

### どれを選ぶか

| 状況 | 方法 |
|---|---|
| テストは dev でやる（推奨） | リセット不要 |
| 同じプールで本番やり直し | **方法A**（`reset-responses.sql`） |
| 新プールで本番やり直し | **方法B**（`reset-all.sql`） |
| テーブル定義ごと新品にしたい | 方法C |

---

## 3. 監視・ログ

```bash
npx wrangler tail                 # Worker の stdout（JSON 構造化ログ）を追う
```

- 管理操作は `admin_log` が JSON で出力（`admin_auth_failed` / `pool_ingest` / `pool_sufficiency_warning` / `token_issue` / `token_issue_blocked` / `admin_progress` / `admin_winrates` / `admin_export` 等）。
- **トークン・作品本文はログに出さない**（秘匿設計）。障害調査は `endpoint` / `result` / `count` で行う。

---

## 4. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `token_issue` が `[error] 発行拒否` + exit 1 | プール未充足（BR-U4a-12） | `gate_errors` の不足内容を見て ① 総数 ≥27 ② 4 層非空 ③ 層間供給 を満たすまで `pool_ingest` を追加実行 |
| 参加者の URL が 404 | 配布 URL の形式誤り（`/s/{token}` 等） | `https://<host>/?token={token}` が正。`--url-template` を修正して再発行不要（URL を作り直すだけ） |
| `/admin/*` が 401 | Basic 認証未設定/誤り | `wrangler secret put ADMIN_BASIC_*` を確認。CLI は環境変数 `ADMIN_BASIC_USER/PASSWORD` |
| `/admin/export?format=csv` が 400 | `entity` 未指定 | `&entity=judgments` 等を付ける（json は bundle 全部で entity 不要） |
| `bt_aggregate` が `schema_version 不一致` で exit 1 | エクスポート形式の版が上がった | 意図的な版上げなら `--allow-version-mismatch`（warnings 付きで続行）。そうでなければコード側の `EXPORT_FORMAT_VERSION` と突き合わせる |
| `bt_aggregate` が `--alpha は正の値が必要` で exit 1 | α≤0 を指定 | α>0 を指定（0 以下は数学的に無効） |
| **廃止したのに参加者にまだ出題される** | **進行中セッション**は既存ペア列のまま（**仕様**, BR-U5-03） | 完了 or 非アクティブ 48h で止まる。即時停止は未実装 |
| **廃止後に `token_issue` が拒否される** | 現役プールが充足条件を割った（BR-U5-09） | `pool_ingest` で補充（総数 ≥27 / 4 層非空 / (総数−最大層) ≥9） |
| `pool_retire` で `not_found` 警告 | `item_id` のタイポ、または既に存在しない | exit 0（失敗ではない）。タイポなら正しい id で再実行 |
| **廃止した item が BT 結果にまだ出る** | **仕様**（過去の判定は有効, BR-U5-10） | 正常。解釈時に必要なら除外する（データは事実として保全） |
| BT 結果に「非連結」warning・多数の `bt_score=null` | 比較グラフが分断（データ不足） | 判定数を増やす。**成分をまたぐスコア比較はしない**。除外 item は `component` で確認 |
| `converged=false` | MM が反復上限内に未収束 | 結果は出る（exit 0）。`--max-iter` を増やすか `--tol` を緩める |
| 較正が `null`（スキップ） | アンカー<2 / θ 分散 0 / Likert 分散 0 / slope≈0 | 生 θ で解釈する。Likert 回答が増えれば自動的に成立 |
| デプロイが途中で失敗 | 品質ゲート（テスト）失敗 | ログでテスト失敗箇所を確認。**migrations/deploy には進んでいない**ので本番は無傷 |

---

## 5. 運用上の注意

- **秘匿**: 作品本文（`body`）はエクスポート経路に出ない。管理 UI は Worker 埋め込み配信で `frontend/`（公開アセット）に**置かない**。
- **token 非参照**: BT 集計は token を一切読まない・出力にも含めない（再識別リスクを構造的に排除）。
- **ローカル保管は運用責任**: `export.json` / `bt_result.json` / `tokens.dist.txt` はリポジトリ管理外。研究データとして各自で保全。
- **dev/prod の D1 分離**: 実験データ汚染防止。本番 D1 は `nazokake-judge`。
- **スナップショット運用**: 反復判定装置として複数時点で回す場合、`BTResult.source.exported_at` で結果ファイル単体から由来を追える（取り違え防止）。

---

## 6. 未消化の運用事項（非ブロッキング）

| 事項 | 内容 |
|---|---|
| **本番デプロイ** | `deploy.yml` は機能済み。実行はユーザー環境（Cloudflare 認証）で |
| **U2 beta 最終 CLOSE** | F-8 + catch-all 反映後の prod curl 疎通 3 点（`/`=200・未知=404・`/api`到達）。自明・疎通のみ |
| **G-1 残（任意）** | smoke Worker / D1（`nazokake-smoke`）は削除可。`smoke-test/` と workflow は CI 雛形として残置 |
