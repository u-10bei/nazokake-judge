# U4a Business Rules — token_issue / pool_ingest

U1 の BR-01〜12 を前提に、U4a 固有の規則を **BR-U4a-NN** で番号付けする。パラメータは U1 と共有（session_pairs=40 / practice=3 / k=3 / cross_layer_min_ratio=0.65, Negotiable）。

---

## 刺激プール投入（pool_ingest）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U4a-01** | 各 record は**層ラベル必須**（`layer ∈ {pro,ai,edit,rule}`）。欠落・不正はその item を拒否（`schema.validate_item` + DB `CHECK`）。 | BR-11 / XC-01 |
| **BR-U4a-02** | 各 record は**本文 `body` 非空必須**（Q5=X）。欠落は拒否。`body` は D1 に格納し U2 が表示に使う。 | Q5=X |
| **BR-U4a-03（プール凍結ガード・必須）** | **`pairs` / `judgments` から参照済みの `item_id` への UPDATE は拒否**。error ログ（該当 `item_id` を列挙）+ **投入全体を中断**（部分適用しない）。新規 `item_id` の INSERT は常に可。判定後の本文・層の書換で過去判定の解釈が壊れる（研究データ完全性）ことを防ぐ＝実験計画の「刺激プール凍結」のコード強制。 | Q4（ガード必須化） |
| **BR-U4a-04（冪等 upsert）** | **未参照**の `item_id` は `ON CONFLICT(item_id) DO UPDATE` で再投入=更新可（べき等）。同一入力の再実行は同一状態。 | Q4 |
| **BR-U4a-05（プール充足の充足判定・三点セット）** | 本番セッション構成可能性の判定式。**評価対象＝マージ後の見込みプール（既存 items ∪ 入力）**（段階投入の途中状態を正しく評価するため）。次の**すべて**を満たすこと: <br> ① `総数 ≥ ceil(2 × session_pairs / k)`（ペア構成の最小数） <br> ② **4 層すべて非空** <br> ③ `(総数 − 最大層の件数) × k ≥ ceil(cross_layer_min_ratio × session_pairs)`（層間ペアの供給可能性） <br> **pool_ingest では未達でも `warning` ログ（不足内訳）+ 投入は実行**（段階投入を妨げない）。ハードなゲートは token_issue（BR-U4a-12）。 | Q6 / XC-01 |
| **BR-U4a-09（原子投入）** | `insert_items` は **D1 batch で all-or-nothing**（半端投入なし）。事前検証・ガードを通過してから 1 batch。 | Q2 / DP-01 |

**BR-U4a-05 の補足（③の意図）**: 「各層 ≥ 1」だけでは層間比率を保証しない（例: pro 92 件 + 他層各 1 件でも①②を通過し得る）。層間ペアは非最大層の項目を消費し各項目はセッション内 k 回まで出現可能なので、非最大層が供給できる層間ペア上限 `(総数 − 最大層件数) × k` が必要層間ペア数 `ceil(cross_layer_min_ratio × session_pairs)` 以上であることを要求する。

---

## トークン発行（token_issue）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U4a-06（一意・衝突処理）** | トークンは U1 `generate_token()`（128-bit, base64url）で生成。発行手順: **(i) 既存トークン集合を読み衝突を事前排除 → (ii) batch 投入 → (iii) DB PK 衝突で失敗したら全体を再生成しリトライ**。2^128 空間で実衝突はほぼ理論値だが規則として固定。 | Q7 / XC-03 / U1-NFR-08 |
| **BR-U4a-07（トークン秘匿）** | 配布用 URL 一覧ファイル・投入用 JSON は**リポジトリ非コミット**（gitignore）。本文・トークンは git に置かない。 | XC-03 / NFR-08 |
| **BR-U4a-10（発行時状態）** | 発行トークンは `status=unused`, `issued_at` セット, `last_active_at=NULL`。状態遷移は BR-09（一方向）に従う。 | domain-entities / BR-09 |
| **BR-U4a-12（発行時充足ゲート・真のゲート）** | **token_issue 実行時、現行 D1 プールが BR-U4a-05 の三点セット未達なら error（不足内訳）+ 発行拒否**。BR-05 の本来意図＝「参加者アクセス前に構成不能を弾く」を、参加者アクセスを可能にする**トークン発行の一点**に集約。これにより段階投入（BR-U4a-05 の warn）を妨げず、かつ**不完全なプールで実験が始まる事故を原理的に排除**する。 | Q6 / **BR-05（本来意図）** / XC-01 |

---

## 管理 API 境界（U4a 先行導入, Q1=A）

| ID | ルール | 根拠 |
|---|---|---|
| **BR-U4a-08（認証境界）** | 管理エンドポイント（`/admin/*`）は **Basic 認証必須**・**HTTPS 強制**。認証情報は環境変数 `ADMIN_BASIC_USER`/`ADMIN_BASIC_PASSWORD`（本番 `wrangler secret`、ローカル `.dev.vars`=gitignore）。認証境界は U2/U3 が再利用（一本化, H-1(c)）。 | Q1 / Q8 / App Design Q5=B |
| **BR-U4a-11（I/O 集約）** | scripts は D1 に直接接続せず、必ず管理 API 経由（H-1(c)）。D1 アクセスは Worker 内 Repository に集約（LC-03）。 | H-1(c) |

---

## 検証・エラー処理

| 状況 | 挙動 |
|---|---|
| 層ラベル欠落／不正 | 当該 item を `rejected` に（理由付き）、`ok=false`（BR-U4a-01） |
| 本文欠落 | 当該 item を `rejected` に（BR-U4a-02） |
| 参照済み item の更新試行 | **投入全体を中断**・error ログに `item_id` 列挙（BR-U4a-03） |
| プール充足不足（**ingest 時**） | マージ後プールで判定。`sufficiency_warnings` に不足内訳・**warning ログ + 投入は実行**（段階投入を妨げない, BR-U4a-05） |
| プール充足不足（**issue 時**） | 現行プールで判定。**error + 発行拒否**（真のゲート, BR-U4a-12） |
| 認証失敗 | 401（Basic 認証, BR-U4a-08） |
| トークン衝突 | 事前排除→batch→全体リトライ（BR-U4a-06） |
