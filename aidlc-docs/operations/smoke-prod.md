# 本番前スモーク — 使い捨てステージングでの参加者フロー確認

**目的**: 本番デプロイの前に、**参加者フローが実インフラ（Cloudflare Workers + D1・実回線・実スマホ）で
動く**ことを確認する。
**方針**: 本番とは**別 Worker・別 D1** に本体アプリをデプロイして確認し、**終わったら丸ごと削除**する。
**本番 D1 を一切触らない**のが要点（捨てプールを本番に入れて `reset` する方式より安全）。

> **なぜ既存の `smoke-test/` ではないのか**: あれは infra 5 項目（fastapi/pydantic/d1/batch）専用の
> 最小 Worker で、参加者フローは載っていない（G-1 で役目を終えた）。本書は**本体アプリ**を使う。

---

## 前提と全体像

```
[D1作成] → [staging へデプロイ] → [捨てプール投入] → [ブラウザで確認] → [丸ごと削除]
```

- **`wrangler.toml` に `[env.staging]` を用意済み**（別 Worker `nazokake-judge-staging` + 別 D1
  `nazokake-judge-stg`）。`database_id` だけ手順①で埋める。
- **捨てプールは 27 件必要**（本番デプロイ先に関係なく、**トークン発行が充足ゲート BR-U4a-12 を
  通す**ため。既定 `session_pairs=40` で `総数≥27 / 4層非空 / (総数−最大層)≥9` を要求）。
- 認証が要るコマンド（`d1 create`・`deploy`・`secret put`・`delete`）は**すべて運用者が実行**する。

---

## 0. 捨てプールキットを用意する

`plans/_smoke/` に**入力3ファイル（`composition.json` / `constraints.json` / `practice.json`）は
コミット済み**。本文を含む**プール本体だけ**を手元で生成する（`pool_*.json` は gitignore）:

```bash
uv run python - <<'PY'
import json
prod=[]
for lay,n in [("pro",7),("ai",7),("edit",7),("rule",6)]:      # 計 27（ゲート充足）
    for i in range(1,n+1):
        prod.append({"item_id":f"SMK-{lay}{i:02d}","layer":lay,
                     "body":f"【スモーク確認用ダミー】{lay}-{i} とかけまして\n本番投入前の疎通確認用です。"})
prac=[{"item_id":"SMK-pr1","layer":"practice","body":"【練習ダミー】その1"},
      {"item_id":"SMK-pr2","layer":"practice","body":"【練習ダミー】その2"}]
json.dump(prod+prac, open("plans/_smoke/pool_smoke.json","w"), ensure_ascii=False, indent=1)
print("pool_smoke.json を生成（本番27 + 練習2）")
PY

# プラン生成（★--blocks 1: スモークに逐次推定は不要。単一ブロック＝巡回グラフゆえ必ず連結）
uv run python -m scripts.plan_generate --pool plans/_smoke/pool_smoke.json \
    --composition plans/_smoke/composition.json \
    --constraints plans/_smoke/constraints.json \
    --practice plans/_smoke/practice.json \
    --blocks 1 --out-dir plans/_smoke --seed 1
#   → [ok] 露出gap=0 連結成分=1 ブロック連結=[1] … / n=27 E=2 J=54 m=4
```

**構成の意図**: n=27（ゲート最小）・E=2（2スロット＝1人27ペア）・m=4。`--blocks 2`（既定）だと
n=27/m=4 では分割が疎すぎて連結できない（PU6-7 の型）ので **`--blocks 1`** を使う。

---

## 1. staging D1 を作る（運用者）

```bash
uv run pywrangler d1 create nazokake-judge-stg
#   → 出力の database_id を wrangler.toml の [[env.staging.d1_databases]] に貼る
#     （使い捨てなのでコミットしなくてよい。むしろコミットしない方がよい）
uv run pywrangler d1 migrations apply nazokake-judge-stg --remote --env staging
#   → 0001〜0005 が staging D1 に適用される
```

## 2. staging へデプロイ（運用者）

```bash
uv run pywrangler deploy --env staging
#   → Worker 名 nazokake-judge-staging、URL は出力末尾に出る:
#     https://nazokake-judge-staging.<subdomain>.workers.dev

# 管理 API 用の Basic 認証を staging Worker にも設定（本番とは独立）
uv run pywrangler secret put ADMIN_BASIC_USER    --env staging
uv run pywrangler secret put ADMIN_BASIC_PASSWORD --env staging
```

疎通確認:

```bash
HOST=https://nazokake-judge-staging.<subdomain>.workers.dev
curl -s $HOST/health   # → {"status":"ok","schema":"0005_layer_anchor_plan.sql"}
```

## 3. 捨てプールを投入（本番と同じ CLI・`--base-url` を staging に向ける）

```bash
export ADMIN_API_BASE=$HOST
export ADMIN_BASIC_USER=...        # 手順2で設定した値
export ADMIN_BASIC_PASSWORD=...

uv run python -m scripts.pool_ingest plans/_smoke/pool_smoke.json     # inserted=29 / 警告なし
uv run python -m scripts.plan_ingest plans/_smoke --activate          # ✅ ハッシュ照合 OK
uv run python -m scripts.token_issue 2 \
    --url-template "$HOST/?token={token}" --out /tmp/smk_tokens.txt    # 2スロット=2本
```

## 4. ★ブラウザで参加者フローを確認（本書の主目的）

`/tmp/smk_tokens.txt` の URL を開く。`manual-p-eval.md` の目視項目に対応:

- [ ] 教示 → 「練習をはじめる」で進む
- [ ] **練習バナーが「1 / 1」**（このキットは練習1ペア。プランが効いている証拠）
- [ ] **ダミー本文が読める**（改行・レイアウト崩れがない）
- [ ] 本番進捗が **「本番 ○ / 27」**
- [ ] **スマホ幅で 2 作品が読める**（開発者ツールのモバイル表示 or 実機で開く）
- [ ] Likert が **3 問**（このキットは likert_targets 3 件）
- [ ] 事後アンケート → 完了画面まで到達
- [ ] **途中でタブを閉じ、同じ URL を開き直すと続きから再開**（`localStorage`・実ドメインで確認）

> ここが実データ dry-run（`dry-run-dev.md` §3.5・dev で完走済み）では確認できない部分＝
> **実ドメイン配信・実回線・実スマホでの見え方**。ロジックは dev で検証済みなので、ここでは
> 「本番同等の環境で崩れないか」に集中する。

## 5. ★丸ごと削除（運用者・確認が済んだら必ず）

```bash
npx wrangler delete --name nazokake-judge-staging     # Worker を削除
npx wrangler d1 delete nazokake-judge-stg             # 使い捨て D1 を削除
```

- `wrangler.toml` の `[env.staging]` は**残置してよい**（次回の本番前スモークで再利用）。
  `database_id` の行だけ `REPLACE_WITH_STAGING_D1_ID` に戻すか、次回作成時に上書きする。
- **本番（`nazokake-judge` / `ab3e84bc-…`）には一切触れていない**——これが本方式の要点。

---

## チェックリスト（本番デプロイに進む前）

- [ ] staging で `/health` が `schema:0005` を返した
- [ ] **ブラウザで 1 セッション完走**・上記の目視項目すべて OK
- [ ] staging Worker と D1 を**削除した**
- [ ] → 本番デプロイへ（`runbook.md` §1）。本番の事前確認（`pairs=0` か）を忘れずに
