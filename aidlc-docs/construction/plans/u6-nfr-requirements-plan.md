# U6 NFR Requirements Plan — 層拡張 + 事前生成割当

**ユニット**: U6（追加要件 2026-07-20）。FD 全 7 問確定（Q1=B / Q2=D / Q3=A+2 / Q4=A′ / Q5=A′ / Q6=A / Q7=A・BR-U6-01〜19）。
**目的**: U6 の非機能要件を確定する。固有論点は **(i) migration 0005 の安全性**（★実測でブロッキング級の問題が判明）、**(ii) 事前生成プランの検証戦略**、**(iii) 後方互換と U3/U4b 無変更の保証**。
**前提（既決）**: 拡張 opt-in は U1〜U5 と共通（Security=No / Resiliency=No / **PBT=Partial**、強制 PBT-02/03/07/08/09）。**`EXPORT_FORMAT_VERSION` 1.0.0 据え置き・U3/U4b 無変更**。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-requirements.md`（U6-NFR-NN）/ `tech-stack-decisions.md`（TSD-U6-NN）を生成します。

## 生成予定の成果物（Part 2）
- [ ] `construction/u6/nfr-requirements/nfr-requirements.md`（U6-NFR-NN + 非目標）
- [ ] `construction/u6/nfr-requirements/tech-stack-decisions.md`（TSD-U6-NN）

---

## 🚨 実測で判明した最重要リスク（migration 0005）

**FD の domain-entities に書いた 0005 DDL 案は、実データがあると失敗します。** local D1 で検証しました。

### 検証内容と結果

`items` 2 件（うち 1 件 `retired_at` あり）+ `tokens` 1 + **`pairs` 1 行（`items` を FK 参照）** + `judgments` 1 の状態で 0005 案を実行:

| 方式 | 結果 |
|---|---|
| **FD 案どおり**（`CREATE items_new` → `DROP TABLE items` → `RENAME`） | ❌ **`FOREIGN KEY constraint failed`**（`pairs` が参照中の親を DROP できない） |
| `PRAGMA foreign_keys=OFF` を前置 | ❌ 同じエラー（**D1 の migration 実行環境では PRAGMA が効かない**） |
| `PRAGMA defer_foreign_keys=ON` を前置 | ❌ 同じエラー |
| **✅ 子行の退避方式**（下記） | ✅ **成功**（8 statements・データ/FK/`retired_at` すべて保全） |

**0002 が通ったのは「新規プロジェクトで既存行なし」だったため**（0002 のコメントにも明記）。**0005 は初めて「データがある状態での親テーブル再構築」になります。**

### 成功した方式（実機確認済み）

```sql
-- items を参照する FK は pairs の 2 本のみ（judgments の pair_id は FK ではない＝確認済み）
CREATE TABLE pairs_bak AS SELECT * FROM pairs;   -- 子行を退避
DELETE FROM pairs;                                -- 参照を外す
-- 親を再構築（retired_at の引き継ぎ必須）
CREATE TABLE items_new (... CHECK (layer IN ('pro','ai','edit','rule','anchor','practice')) ...);
INSERT INTO items_new SELECT item_id, layer, body, body_ref, retired_at FROM items;
DROP TABLE items;
ALTER TABLE items_new RENAME TO items;
INSERT INTO pairs (...) SELECT ... FROM pairs_bak;  -- 子行を復元
DROP TABLE pairs_bak;
```

**検証済み**: `retired_at` 保全 ✅ / `pairs` 復元 ✅ / `PRAGMA foreign_key_check` 違反なし ✅ / `anchor`・`practice` 投入可 ✅ / 不正層値の拒否維持 ✅

**副次的に確認**: **D1 は migration を原子的にロールバックする**（失敗時 `items_new` の残骸なし）。

---

## NFR カテゴリ適用性（U6）
| カテゴリ | 適用 | 備考 |
|---|---|---|
| **Data / Migration** | **適用（最重要・実測でリスク顕在化）** | 0005 は**データがある状態での親テーブル再構築**。FK・`retired_at`・原子性。→ Q1 |
| **Testability** | **適用（PBT 中心）** | プラン検証（BR-U6-10 の①〜⑤）を PBT 化。既存 P-1 を流用。→ Q2 |
| **Compatibility（後方互換）** | **適用** | `plan_index IS NULL` のフォールバック・`EXPORT_FORMAT_VERSION` 据え置き・U5 の `retired_at`/`likert_targets` 保持。→ Q3 |
| **Observability / 監査** | **適用** | プラン生成の決定論（seed 記録）・activate 操作の証跡。→ Q4 |
| **Security** | 既存流用（差分あり） | プラン投入・activate の経路をどこに置くか（admin API か D1 直か）。→ Q4 |
| **Performance** | **N/A** | プラン引き当ては PK 参照。実行時の抽選が**なくなる**ので軽くなる。 |
| **Availability / Scalability / Resiliency** | **N/A** | 既存 Worker/D1 の運用に同じ。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【★最重要・Data/Migration】0005 の方式と適用条件
**事実**: FD 案の DDL は**実データがあると FK 違反で失敗**する（上記実測）。PRAGMA による回避は D1 で効かない。

- **★A（推奨）**: **退避方式を採用**（上記の実機確認済み SQL）。加えて:
  - **`retired_at` の引き継ぎを Step に一行固定**（列を落とすと U5 の廃止状態が消失する）。
  - **`pairs` の全列を明示して復元**（`SELECT *` に依存せず列順の変化に強くする）。
  - **検証を NFR 化**: 「**データがある状態**での 0005 適用を integration で検証する」（空 DB でしか試さないと**本番/dev の実データで初めて失敗する**）。
  - **`practice` 層は 0005 に同載**（後から足すと再構築をもう一度やることになる）。
- **B**: 「0005 は空 DB でのみ適用する」と運用制約にする（本番未デプロイゆえ初回デプロイでは空）。→ dev/ドライラン環境や再適用で**必ず踏む**。運用制約に頼るのは脆い。
- **C**: `items` を再構築せず CHECK 制約を撤廃する。→ 層ラベルの妥当性検証を失う（BR-11 の趣旨に反する）。不採用。

[Answer]:

### Q2【Testability】プラン検証の PBT / unit 振り分け
BR-U6-10 の①〜⑤（露出 gap=0 / 連結成分 1 / k≤3 / 同一ペア 0 / 層間 ≥0.65）をどう検証するか。

- **★A（推奨）**: **プラン生成器に対する PBT**（PBT-03 不変条件が主）:
  - **PU6-1**: 生成プランは **全 item の出現がちょうど m**（露出 gap=0）
  - **PU6-2**: 比較グラフの**連結成分が 1**
  - **PU6-3**: 評価者内の **同一 item 出現 ≤ k**
  - **PU6-4**: **同一評価者に同一ペアが現れない**
  - **PU6-5**: **層間ペア比率 ≥ 0.65**
  - **PU6-6（決定論）**: 同一 (プール, E, J, seed) → **同一プラン**（BR-U6-11）
  - **ジェネレータ（PBT-07）**: n・E・J を**振って生成**する（n=38/E=8/J=228 の 1 点だけでは「その組合せでたまたま通る」ことしか示せない）。**12-正則が構成できない組合せ**（2J が n で割り切れない等）で**生成が明示的に失敗する**ことも検証。
  - **unit**: `POOL_LAYERS` による層フィルタ（`practice` が母数外）/ `plan_index` 引き当て / 補充トークンの引き継ぎ。
  - **integration（実 D1）**: **0005 をデータがある状態で適用**（Q1）・プラン投入 → セッション開始 → ペア列がプランと一致・**U2/U3/U4a/U5 の既存シナリオが緑**。
- **B**: 実データ 1 構成（n=38/E=8/J=228）の example のみ。→ 生成器の一般性が示せず、**将来 E や n を変えた瞬間に壊れる**。

[Answer]:

### Q3【後方互換】`plan_index IS NULL` と U3/U4b 無変更の保証
- **★A（推奨）**:
  - **`plan_index IS NULL` のトークンは従来どおりオンライン生成にフォールバック**（U6 以前に発行されたトークン／ドライラン用の即席トークン）。**実装し検証する**（U5 の `likert_targets IS NULL` フォールバックと同型）。
  - **`EXPORT_FORMAT_VERSION` は 1.0.0 据え置き**。保証手段は **U3/U4b の既存テストを無改修で緑に保つこと**＝形式が変わっていない証拠（**U5-NFR-04 と同型**）。**U6 のために U3/U4b のテストを書き換えたら設計違反のシグナル**。
  - **U5 の資産を壊さない**: 0005 再構築後も **`retired_at` が保持**され、`list_active_items()`／`pool_retire` が従来どおり動くことを検証する。
- **B**: フォールバックを省略（全トークンに `plan_index` を必須化）。→ ドライランで即席トークンを使えなくなる。既存の `/it/seed-token` 相当も壊れる。

[Answer]:

### Q4【Observability / Security】プラン投入・activate の経路
プランを D1 に入れる経路と、`is_active` を切り替える経路をどこに置くか。

- **★A（推奨）**: **管理 API 経由**（既存 AuthGuard の背後）:
  - `POST /admin/plan`（投入）/ `POST /admin/plan/activate`（有効化）。**`admin_log` に `plan_ingest` / `plan_activate` を記録**（**どのセットをいつ有効化したかの証跡**）。
  - **理由**: `pool_ingest`・`pool_retire` と**同じ流儀**（D1 直操作は証跡が残らないため運用上排除、U5-NFR-10 と同型）。プラン切替は**実験の同一性に直結する**操作ゆえ証跡が要る。
  - **activate は 1 セットのみ**を DB 制約 or アプリで保証（BR-U6-12）。
  - **収集開始後の activate 切替を拒否**するか（安全弁）は **NFR Design の決定点**。
- **B**: `wrangler d1 execute` で直接投入。→ **証跡が残らない**。プラン切替は実験の同一性を左右する操作なので不適。
- **C**: 投入は API・activate は D1 直。→ 経路が割れて運用が混乱。

[Answer]:

### Q5【その他カテゴリの適用性確認・回帰基準】
- **★A（推奨）**:
  - **Performance / Availability / Scalability / Resiliency = N/A**（プラン引き当ては PK 参照。**実行時の抽選がなくなるため軽くなる**）。
  - **Security = 既存流用**: 新規公開面は `/admin/*` 配下のみ（既存 Basic 認証背後）。参加者 API（`/api/*`）に新規公開面なし。全パラメータ化。
  - **回帰の完了基準**: **U1/U2/U3/U4a/U4b/U5 の既存 unit+PBT を全緑**にすることをブロッキング条件とする。**integration は 0005 適用後に U2/U3/U4a/U5 の既存シナリオを実 D1 で緑**にする。
  - **`generate_pairs` の既存 PBT（P-1）は緑のまま維持**（BR-U6-17 で残す方針ゆえ）。
- **B**: 回帰を U6 分のみに限定。→ 本ユニットは **`items` テーブル再構築 + 参加者フローの割当置換**という**最も侵襲的な変更**。不採用。

[Answer]:

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-requirements.md`（U6-NFR-NN）/ `tech-stack-decisions.md`（TSD-U6-NN）を生成 → 標準 2 択（Request Changes / Continue → **NFR Design〈U6〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
