# plans/ — 事前生成割当プラン（U6）

**このディレクトリは追跡対象（gitignore 非該当）です。** プランは **`item_id` のみで作品本文を
含まない**ためコミットできます——そして **コミットすることが要件**です（BR-U6-12: 両セットを
リポジトリで固定し、**commit 履歴 + 内容ハッシュ**を証跡とする）。

```
plans/
  primary/    ← 許諾が成立した場合（n=38）
  fallback/   ← N1〜N8 の許諾が下りなかった場合（n=34）
```

**⚠️ どちらか一方だけを D1 に投入します**（Infra Q1=A′）。両方を投入する設計にすると
プール入替と凍結ガードが衝突するため、**2 セット要件の充足場所は D1 ではなくリポジトリ**です。

---

## 入力は「三つ組」でセット単位

| ファイル | 出どころ | 中身 |
|---|---|---|
| **プール** (`items_*.json`) | 実データ | ⚠️ **gitignore 対象**（本文を含むため） |
| **期待組成** (`composition.json`) | 設計定数 | ✅ **記入済み**（下表） |
| **制約** (`constraints.json`) | 研究側（タスク5 §3） | ⛔ **雛形のまま — 記入が必要** |
| **練習ペア** (`practice.json`) | 研究側 | ⛔ **要作成** — `--practice` で渡す。**省略するとエラーにならず「練習なし」で生成される** |

（「三つ組」は**整合検証の単位**を指します。練習ペアは検証対象外の付加入力ですが、
**実験には必須**です——`[["PR1","PR2"], …]` の形式で標準 3 ペア。）

→ **提供元向けの記入手引き**: `aidlc-docs/operations/manual-p-data.md`

三つ組は**セット別で流用できません**。制約ファイルは `plan_set` を内包し、期待組成と
一致しなければ**明示失敗**します（成立版の制約をフォールバック版に誤適用する事故を防ぐ）。

### 確定済みの設計定数（記入済み）

| | primary | fallback |
|---|---:|---:|
| n（item 数） | **38** | **34** |
| E（スロット = 評価者数） | 8 | 8 |
| J（本番ペア総数） | **228** | **204** |
| m（1 item あたり比較回数） | 12 | 12 |
| スロット配分 | [29×4, 28×4] | [26×4, 25×4] |
| 層 | pro 10 / anchor 2 / edit 14 / ai 9 / rule 3 | pro **6** / anchor 2 / edit 14 / ai 9 / rule 3 |

fallback は **N1〜N8（8 件）を落とし、予約の S02・S11・S12・S19（4 件）を投入**して n=34。
J = n × m ÷ 2（228 = 38×12÷2 / 204 = 34×12÷2）。

---

## `constraints.json` の記入

**プレースホルダのままでは実行できません**（`forbidden_pairs に自己ペア: <item_id>` で停止）。
**`item_id` はすべて実プールに存在する必要があります**。

| キー | 種別 | 意味 |
|---|---|---|
| `likert_targets` | — | **ちょうど 10 件**。ブリッジ Likert の固定アンカー。**この 10 件が全評価者に共通で提示**され、θ を Likert 尺度へ写す較正点になる |
| `forbidden_pairs` | **ハード** | 同一評価者に**絶対に並べない**ペア（pivot 衝突など）。違反があれば生成失敗 |
| `discouraged_pairs` | ソフト | できれば避けたいペア。**違反してもエラーにせずレポートのみ** |
| `enrichment` | ソフト | `{anchor, counterparts, target}` — その anchor と counterparts の比較を **target 本以上**作る（重点的に見たい対比） |
| `avoid_adjacent_groups` | 提示順 | 同一グループの item を**スロット内で隣接させない**（直前の記憶による引きずりを避ける） |

**未知キーは拒否されます** — typo で制約が黙って無効化されるのを防ぐためです
（`forbidden_pair` と単数で書いても静かに無視されると、禁止辺が効かないまま生成されます）。

**内容制約が無くても生成は通ります**（`likert_targets` 10 件だけ埋めて他を `[]` にする）。
実測: 合成 n=38 プール・制約なしで **attempt=0（初回）で成立**——gap=0 / 連結成分 1 /
ブロック連結 [1,1] / 層間 0.763 / 最大出現 3 / 同一ペア 0。**まず制約なしで通してから
研究側の制約を足す**進め方が安全です（制約の記入ミスと生成の難しさを切り分けられる）。

---

## 使い方

```bash
# 生成（D1 に触れずファイルを書くだけ）
uv run python -m scripts.plan_generate \
    --pool items_real.json \
    --composition plans/primary/composition.json \
    --constraints plans/primary/constraints.json \
    --practice plans/primary/practice.json \
    --out-dir plans/primary --seed 20260720

# verification.md を確認してから **コミット**
git add plans/primary && git commit -m "plan: primary set fixed"

# 投入 → 有効化（★content_hash を再計算して照合してから POST）
uv run python -m scripts.plan_ingest plans/primary --activate
```

生成物 `plan.json` / `plan.meta.json` / `verification.md` も**コミット対象**です
（これが「コミットされたものが投入された」という証跡の実体）。

**⚠️ 順序**: プラン生成は**プール確定後**（プランはプールから構成される）。トークン発行は
**activate 後**（先に発行すると `(plan_set, plan_index)` の束縛先が未定）。
