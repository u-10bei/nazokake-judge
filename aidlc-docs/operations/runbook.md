# nazokake-judge 運用 Runbook

**対象**: 研究者（装置の運用者）。**前提**: 全 5 ユニット完了（CONSTRUCTION CLOSE, 2026-07-15）。
**位置づけ**: AI-DLC の Operations は方法論上プレースホルダ（規定なし・Build & Test で完走）。本書はその Future Scope（production readiness / maintenance）に相当する**実運用手順書**であり、実装済みの CLI/API に基づく。

> **文書の使い分け**（ペルソナ定義 = `../inception/user-stories/personas.md`）
> | 文書 | 対象 | 内容 |
> |---|---|---|
> | **本書 `runbook.md`** | P-RSCH 研究者 | **コマンド手順**・デプロイ・監視・トラブルシューティング |
> | `manual-p-rsch.md` | P-RSCH 研究者 | 装置の全体像・**結果の読み方**・実験設計上の約束 |
> | `manual-p-eval.md` | P-EVAL 評価者 | **参加者へ配布する説明書**（URL と一緒に渡す） |

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
- **段階投入可**: プール未充足でも投入自体は成功し `sufficiency_warnings` が出る（充足はトークン発行時に強制）。
- **終了コード**: 拒否 or クライアント検証不正があれば **1**。

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
