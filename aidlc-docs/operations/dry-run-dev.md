# 開発環境での実データ動作確認（ドライラン）手順書

**目的**: 本番デプロイ前に、**ローカル開発環境**で**実データ**（実際の刺激プール）を使い、判定装置の一巡（投入 → 発行 → 参加 → 進捗 → エクスポート → BT 集計）が意図どおり動くことを確認する。
**対象**: P-RSCH（研究者・運用者）。
**所要**: 30〜60 分（自動走行を使う場合）。

> **この手順書は実機で検証済み**（2026-07-20）。ダミー 95 件（pro30/ai20/edit30/rule15）+ 30 セッションで全工程を通し、**連結成分 1・全 95 件推定・較正成立**まで確認しています（§6 に実測値）。

---

## ⚠️ 実データを扱う前に（最重要）

実データには**未公表の作品本文**（`pro` 層は第三者の著作物を含みうる）と、進めると**参加者トークン**が生じます。**リポジトリに絶対に入れないでください。**

**ファイル名の規約を必ず守ってください** — `.gitignore` は**名前で**除外しています:

| 用途 | ✅ 安全な名前 | ⚠️ 危険な名前 |
|---|---|---|
| 刺激プール投入ファイル | `items_*.json` / `pool_*.json` | `mypool.json`・`data.json`（**追跡される**） |
| 配布トークン一覧 | `*.dist.txt` | `tokens.txt` |
| エクスポート | `export*.json` | `dump.json` |
| BT 結果 | `bt_result*.json` / `bt_a*.json` | `result.json` |

確認コマンド（**投入前に必ず実行**）:

```bash
git check-ignore -v items_real.json && echo "OK: 除外される"
```

何も出力されなければ**追跡対象**です。ファイル名を変えてください。

---

## 0. 事前準備（初回のみ）

### 0-1. ローカル認証情報

```bash
cp .dev.vars.example .dev.vars
# .dev.vars を編集（ローカル専用の値でよい）
#   ADMIN_BASIC_USER=devadmin
#   ADMIN_BASIC_PASSWORD=devsecret
```

`.dev.vars` は gitignore 済み。**本番の `wrangler secret` とは無関係**（ローカル専用）。

### 0-2. ローカル D1 にスキーマを作る

```bash
uv run pywrangler d1 migrations apply nazokake-judge --local
```

`0001`〜`0004` が適用されます（`--local` なので**本番 D1 には一切触れません**）。

### 0-3. 実データの用意

`items_real.json` を用意します（JSON 配列 または JSONL）:

```json
[
  {"item_id": "pro001", "layer": "pro",  "body": "〇〇とかけまして…"},
  {"item_id": "ai001",  "layer": "ai",   "body": "…"},
  {"item_id": "edit001","layer": "edit", "body": "…"},
  {"item_id": "rule001","layer": "rule", "body": "…"}
]
```

- **層ラベル必須**: `pro` / `ai` / `edit` / `rule`。
- **推奨構成 95 件**（`pro`30 / `ai`20 / `edit`30 / `rule`15）→ 根拠は `manual-p-rsch.md` §4。
- `body_ref` は任意（出自メモ）。

---

## 1. 起動

```bash
uv run pywrangler dev --port 8787
```

別ターミナルで疎通確認（**4 点とも通ること**）:

```bash
curl -s http://127.0.0.1:8787/health                                    # → {"status":"ok",...}
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/         # → 200（参加者フロント）
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/admin/   # → 401（未認証）
curl -su devadmin:devsecret -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/admin/  # → 200
```

以降のコマンド用に環境変数を設定します:

```bash
export ADMIN_API_BASE=http://127.0.0.1:8787
export ADMIN_BASIC_USER=devadmin
export ADMIN_BASIC_PASSWORD=devsecret
```

---

## 2. 一巡を通す

### ① プール投入

```bash
uv run python -m scripts.pool_ingest items_real.json
```

**確認**: `"ok": true` / `inserted` が件数どおり / **`sufficiency_warnings` が空**。
警告が出たら充足条件（総数 ≥27・4 層非空・(総数−最大層) ≥9）を満たしていません。

### ② トークン発行

```bash
uv run python -m scripts.token_issue 30 \
    --url-template 'http://127.0.0.1:8787/?token={token}' \
    --out tokens.dist.txt
```

> ⚠️ **URL は `/?token={token}` が正**。`/s/{token}` のようなパスは **404** になります（SPA フォールバック不使用）。

**確認**: 30 本の URL が出力される。拒否された場合は `gate_errors` に不足内訳が出ます。

### ③〜④ 参加者フロー（**ここが本番の核心**）

**まず必ず 1 セッションはブラウザで手動確認してください。** 自動走行では UI の破綻に気づけません。

```bash
head -1 tokens.dist.txt    # この URL をブラウザで開く
```

**目視チェックリスト**:

- [ ] 教示画面が表示され「練習をはじめる」で進む
- [ ] **練習中バナー**（「練習中（この回答は集計されません）」）が出る
- [ ] **実データの本文が読める**（文字化け・改行崩れ・レイアウト破綻がない）
- [ ] 選択しないと「送信」が押せない
- [ ] 本番に入ると進捗「本番 ○ / 40」が更新される
- [ ] **スマートフォン幅でも 2 作品が読める**（ブラウザの開発者ツールでモバイル表示に切替）
- [ ] Likert 画面 → 事後アンケート → 完了画面まで到達する
- [ ] **途中でタブを閉じて同じ URL を開き直すと続きから再開**する（回答が消えない）

### ③′ 残りを自動で走らせる（BT 集計まで検証したい場合）

BT 集計の妥当性を見るには**複数セッション**が要ります（理由は §6）。残りのトークンを自動走行させます:

```bash
uv run python - <<'PY'
import json, urllib.request, random
BASE = "http://127.0.0.1:8787"
def get(p):
    with urllib.request.urlopen(f"{BASE}{p}") as r: return json.loads(r.read())
def post(p, d):
    req = urllib.request.Request(f"{BASE}{p}", data=json.dumps(d).encode(),
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r: return json.loads(r.read())

toks = [l.strip().split("token=")[-1] for l in open("tokens.dist.txt") if l.strip()]
rnd = random.Random(42)          # 再現可能にする
for n, t in enumerate(toks, 1):
    v = get(f"/api/session?token={t}"); s = 0
    while v.get("phase") not in ("done", None) and s < 80:
        s += 1; ph = v["phase"]
        if ph in ("practice", "judging") and v.get("next_pair"):
            v = post("/api/judgment", {"token": t, "pair_id": v["next_pair"]["pair_id"],
                                       "choice": rnd.choice(["A", "B"])})
        elif ph == "likert" and v.get("next_likert"):
            v = post("/api/likert", {"token": t, "target_ref": v["next_likert"]["target_ref"],
                                     "rating": rnd.randint(1, 7)})
        elif ph == "survey":
            v = post("/api/survey", {"token": t, "answers": {"experience": "some",
                     "proficiency": "3", "emphasis": "テスト", "age_band": "30s"}})
        else:
            v = get(f"/api/session?token={t}")
    if n % 10 == 0: print(f"  {n}/{len(toks)} 名完了")
print("全セッション完了")
PY
```

> **注意**: 選択は**ランダム**なので BT スコアの中身に意味はありません。ここで見るのは「**装置が回るか**」「**連結するか**」「**較正が成立するか**」です。

### ⑤ 進捗確認

```bash
curl -su "$ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD" "$ADMIN_API_BASE/admin/progress"
```

**確認**: `tokens_completed` が走らせた数と一致・`judgments_total` = 完了数 × 40（**練習の 3 件 × 人数は含まれない**）。

ブラウザで `http://127.0.0.1:8787/admin/` を開き、**管理 UI の目視確認**もしてください:

- [ ] 進捗サマリの数字が上記と一致
- [ ] 暫定勝率テーブルが表示される（**非 BT の注記**があること）
- [ ] エクスポートボタンでダウンロードできる

### ⑥ エクスポート

```bash
curl -su "$ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD" \
     -o export.json "$ADMIN_API_BASE/admin/export?format=json"
```

**確認（実データ特有の重要チェック）**:

```bash
uv run python -c "
import json; d = json.load(open('export.json'))
print('schema_version:', d['schema_version'])
print('items:', len(d['items']), 'judgments:', len(d['judgments']))
# ★ 作品本文が漏れていないこと（出自秘匿・著作権）
assert all(set(i.keys()) == {'item_id','layer'} for i in d['items']), 'body が漏れている！'
# ★ 自己完結性（judgments の item ⊆ items）
ids = {i['item_id'] for i in d['items']}
refs = {x for j in d['judgments'] for x in (j['item_left'], j['item_right'])}
assert refs <= ids, '自己完結性が壊れている！'
print('✅ body 非含有・自己完結性 OK')
"
```

### ⑦ BT 集計

```bash
uv run python -m scripts.bt_aggregate export.json --out bt_result.json
```

**確認**: §6 の判断基準を参照。

---

## 3. U5（出題停止）の確認（該当する場合のみ）

著作権配慮での出題停止を使う予定なら、ここで挙動を確認しておきます:

```bash
# 停止
uv run python -m scripts.pool_retire pro001

# 新規セッションに出ないことを確認（新しいトークンで開始）
uv run python -m scripts.token_issue 1 --url-template 'http://127.0.0.1:8787/?token={token}' --out check.dist.txt
# → 開いて pro001 が出ないこと（本文で確認）

# エクスポートには残ることを確認（過去の判定は有効）
curl -su "$ADMIN_BASIC_USER:$ADMIN_BASIC_PASSWORD" -o export.json "$ADMIN_API_BASE/admin/export?format=json"
uv run python -c "
import json; d=json.load(open('export.json'))
print('pro001 は items に残る:', 'pro001' in {i['item_id'] for i in d['items']})"

# 復活
uv run python -m scripts.pool_retire pro001 --unretire
```

**期待**: 新規セッションには出ない / **エクスポートには残る**（これが正常）。

---

## 3.5 U6 カットオーバー手順のリハーサル（★実験前に一度通す）

U6（層拡張 + 事前生成割当）では **migration 0005 の適用タイミングに制約**があり、
**プラン投入 → activate → トークン発行の順序を誤ると静かに壊れます**。**dev で全順序を
一度リハーサル**してください。

```bash
# ⓪ 許諾成立/不成立の決定と使用セットを記録（研究側記録・admin_log 外）

# ① 0005 を「データがある状態」で適用できるか検証（U6-NFR-01/05）
#    ⚠️ 本番では「発行済み未消化トークンが存在しない時点」に限る（U6-NFR-04）
uv run pywrangler d1 migrations apply nazokake-judge --local
#    適用後検証 3 点:
uv run pywrangler d1 execute nazokake-judge --local --command "PRAGMA foreign_key_check"
uv run pywrangler d1 execute nazokake-judge --local --command \
  "SELECT (SELECT COUNT(*) FROM items) items, (SELECT COUNT(*) FROM pairs) pairs, \
          (SELECT COUNT(*) FROM items WHERE retired_at IS NOT NULL) retired"
#    → items / pairs の行数が適用前後で一致・retired_at 非 NULL 件数も一致すること

# ② プール投入（anchor 2 件と practice 素材を含む）
uv run python -m scripts.pool_ingest items_real.json

# ③ プラン生成 → **コミット**（D1 には触れない）
uv run python -m scripts.plan_generate --pool items_real.json \
    --composition plans/primary/composition.json \
    --constraints plans/primary/constraints.json \
    --out-dir plans/primary --seed 20260720
git add plans/primary && git commit -m "plan: primary set fixed"

# ④ 投入 → 有効化（plan.json / plan.meta.json を POST）
# ⑤ トークン発行（★ここで (plan_set, plan_index) が束縛される。④の後でなければ束縛先が未定）
uv run python -m scripts.token_issue 8 --url-template 'http://127.0.0.1:8787/?token={token}' --out tokens.dist.txt

# ⑥ 参加 → 進捗 → エクスポート → BT 集計（§2 の一巡）
```

**確認ポイント**:
- [ ] 0005 適用後の 3 点検証がすべて一致
- [ ] プラン生成が `verification.md` を出力し **gap=0 / 連結成分 1 / ブロック連結 [1,1]**
- [ ] 発行したトークンで開始すると**ペア列がプランと一致**（練習が先頭）
- [ ] **Likert がプラン記載の固定リストと一致**（ラウンドロビンに落ちていない）
- [ ] `plans/<set>/` を**コミット済み**（両セットの事前固定が commit 履歴とハッシュで残る）

---

## 4. 後片付け

### 4-1. ローカル D1 をリセット

```bash
# 全消し（プールごと）
uv run pywrangler d1 execute nazokake-judge --local --file=scripts/reset-all.sql

# 回答だけ消してプールは残す場合
uv run pywrangler d1 execute nazokake-judge --local --file=scripts/reset-responses.sql
```

> `--local` を付けている限り**本番 D1 には触れません**。

### 4-2. 実データファイルを消す

```bash
rm -f items_real.json tokens.dist.txt check.dist.txt export.json bt_result.json
git status --short          # ← 実データが残っていないことを必ず確認
```

---

## 5. 本番へ進む前のチェックリスト

- [ ] 疎通 4 点（`/health`・`/`=200・`/admin/`=401→認証で 200）
- [ ] プール投入で `sufficiency_warnings` が空
- [ ] トークン発行が成功し、**配布 URL がブラウザで開ける**
- [ ] **実データの本文がスマホ幅で読める**
- [ ] 中断 → 同じ URL で**続きから再開**できる
- [ ] 完了画面まで到達し `tokens_completed` が増える
- [ ] 管理 UI で進捗・勝率・エクスポートが動く
- [ ] **エクスポートに `body` が含まれない**・自己完結性 OK
- [ ] BT 集計が **`n_components=1`**（→ §6）
- [ ] ローカル D1 をリセットし、実データファイルを削除した

すべて緑なら **`runbook.md` §1 の本番デプロイ**へ進めます。

---

## 6. BT 結果の判断基準（★実測値つき）

**参加者数が少ないと BT はほとんど推定できません。** これは**バグではなく比較グラフが疎なため**です。実測値:

| 参加者数 | 判定数 | `n_components` | 推定対象 | 較正 | 1 作品の平均出場 |
|---:|---:|---:|---|---|---:|
| **1 名** | 40 | **30** | **4 / 95** ❌ | スキップ | 0.8 回 |
| **30 名** | 1200 | **1** ✅ | **95 / 95** ✅ | **成立**（92 アンカー） | **25.3 回** |

（プール 95 件 = pro30/ai20/edit30/rule15・既定パラメータ・2026-07-20 実測）

**判断**:

| 結果 | 意味 |
|---|---|
| **`n_components=1` / 推定対象 = 全件** | ✅ **正常**。装置が機能している |
| `n_components` が大きい / 多数が `bt_score=null` | ⚠️ **参加者数が足りないだけ**。1〜数名なら**当然こうなる**。実験としては 30 名規模で解消する |
| `converged=false` | `--max-iter` を増やすか `--tol` を緩める |
| `calibration: なし` | Likert アンカーが 2 件未満。参加者が増えれば自動的に成立 |

> **30 名という数字の根拠**: 割当アルゴリズムの α/S 較正が **S=30**（30 セッション累積で露出均衡を保証）で確定しているためです（`manual-p-rsch.md` §4）。上の実測はその想定と一致しました。

---

## 7. よくある詰まり

| 症状 | 原因 | 対処 |
|---|---|---|
| `pywrangler dev` が起動しない | 依存未導入 | `uv sync` |
| `/admin/*` が常に 401 | `.dev.vars` 未作成 / 値の不一致 | `.dev.vars` を作り、環境変数と揃える。**dev 起動を再起動** |
| CLI が「ベース URL を指定してください」 | `ADMIN_API_BASE` 未設定 | `export ADMIN_API_BASE=http://127.0.0.1:8787` |
| 配布 URL が 404 | `--url-template` の形式誤り | `'http://127.0.0.1:8787/?token={token}'`（`/s/` ではない） |
| `token_issue` が発行拒否 | プール未充足 | `gate_errors` を見て `pool_ingest` で補充 |
| `no such column: retired_at` | migration 未適用 | `pywrangler d1 migrations apply nazokake-judge --local` |
| 参加者画面が真っ白 | トークン不正 / D1 未初期化 | `/health` と `/api/session?token=...` を直接叩いて切り分け |
| BT が非連結だらけ | **参加者数不足（仕様）** | §6 参照。1 名では当然こうなる |

---

## 関連文書

| 文書 | 用途 |
|---|---|
| `runbook.md` | 本番の手順・デプロイ・監視・リセット |
| `manual-p-rsch.md` | 装置の全体像・**結果の読み方**・プール構成の根拠 |
| `manual-p-eval.md` | 参加者へ配布する説明書 |
