# U5 NFR Requirements Plan — 出題停止（item retirement）

**ユニット**: U5（著作権配慮による出題停止・追加要件 2026-07-17）
**目的**: U5 の非機能要件を確定する。U5 は **既存インフラ上の列追加 2 本 + 読み取り経路の分割**であり、新規の公開面・外部依存・性能要求を持たない。固有論点は **(i) 「新規のみ反映／結果は有効」という要件の両輪を構造で守れているかの検証戦略**、**(ii) migration 0004 の安全性と後方互換**、**(iii) 著作権対応の証跡（監査ログ）**。
**前提（既決）**: 拡張 opt-in は U1〜U4b と共通（Security Baseline=No / Resiliency=No / **PBT=Partial**、強制 PBT-02/03/07/08/09）。FD 全 6 問 A・BR-U5-01〜13 確定（`construction/u5/functional-design/`）。**U3/U4b 無変更・`EXPORT_FORMAT_VERSION` 1.0.0 据え置き**。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-requirements.md`（U5-NFR-NN）/ `tech-stack-decisions.md`（TSD-U5-NN）を生成します。

## 生成予定の成果物（Part 2）
- [ ] `construction/u5/nfr-requirements/nfr-requirements.md`（U5-NFR-NN + 非目標）
- [ ] `construction/u5/nfr-requirements/tech-stack-decisions.md`（TSD-U5-NN）

---

## NFR カテゴリ適用性（U5）
| カテゴリ | 適用 | 備考 |
|---|---|---|
| **Data / Migration** | **適用（最重要）** | migration 0004（列追加 2 本・いずれも NULL 許容）。既存行・既存セッションを壊さないこと。→ Q1 |
| **Testability** | **適用（PBT 中心）** | 要件の両輪（新規のみ反映 / 結果は有効）を PBT で反例探索。**BR-U5-02 の禁止事項を踏んだら落ちる網**を張れるかが肝。→ Q2 |
| **Compatibility（後方互換）** | **適用** | 旧セッション（`likert_targets IS NULL`）のフォールバック。`EXPORT_FORMAT_VERSION` 据え置き＝U3/U4b 無変更の保証。→ Q1 / Q3 |
| **Observability / 監査** | **適用（著作権対応ゆえ昇格）** | `admin_log` が**廃止履歴の正**（BR-U5-13）。証跡が残らない経路（D1 直操作）を運用上排除。→ Q4 |
| **Security** | 既存流用（差分なし） | retire/unretire は既存 Basic 認証（AuthGuard）の背後。新規シークレット・新規公開面なし。パラメータ化クエリ。→ Q5 |
| **Performance** | **N/A** | プール約 95 件・UPDATE 数件・`WHERE retired_at IS NULL` の全走査。インデックス不要（FD domain-entities §1）。 |
| **Availability / Scalability / Resiliency** | **N/A** | 既存 Worker/D1 の運用に同じ。U5 固有の可用性要求なし。 |
| **Usability（CLI）** | 適用（限定） | `pool_retire` の出力（retired / already_retired / not_found の分類）と終了コード。→ Q4 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Data / Migration】migration 0004 の安全性・適用順・後方互換の位置づけ
- **★A（推奨）**:
  - **安全性**: `ALTER TABLE items ADD COLUMN retired_at TEXT` / `ALTER TABLE sessions ADD COLUMN likert_targets TEXT`。**いずれも NULL 許容**ゆえ **0002 のようなテーブル再構築は不要**・**既存行のデータ移送も不要**（既存 items は全て NULL=現役、既存 sessions は全て NULL=フォールバック）。
  - **適用順**: **migration → deploy** を厳守（Infra §4 の既存規約）。逆順では `retired_at` 前提のコードが旧スキーマに当たる。`deploy.yml` は versioned 自動適用ゆえ**ワークフロー無変更**（0001〜0004 が順に適用される）。
  - **後方互換フォールバックの位置づけ**: **本番は未デプロイ**のため、初回デプロイに 0004 を同梱すれば**旧セッション（`likert_targets IS NULL`）は実在しない**。それでも**フォールバックは実装・検証する**（NFR として要求）。理由: (i) 将来 U5 を「稼働後」に適用する場合に進行中セッションが必ず生じる、(ii) フォールバックの有無が「新規のみ反映」の保証そのもの、(iii) 実装コストが低く保険として合理的。
- **B**: フォールバックを省略（旧セッションは存在しない前提）。→ 稼働後適用で進行中セッションが壊れる。デプロイ順序に暗黙の前提を作る。不採用。

[Answer]:

### Q2【Testability・最重要】PBT/unit の振り分け — 要件の両輪に網を張る
FD で **BR-U5-02 の禁止事項**（`list_items()` 自体に active フィルタを足す）を明文化したが、**明文は実装を強制しない**。テスト側にも網を張るかを決める。

- **★A（推奨）**: **要件の両輪それぞれに PBT を立てる**（PBT-03 不変条件が主）:
  - **PU5-1（新規セッションから消える）**: 廃止済み item X を含むプールで新規セッションを開始 → **ペア列・練習ペア・Likert ターゲットのいずれにも X が現れない**（BR-U5-02a/02b）。
  - **PU5-2（旧セッションは不変）**: `likert_targets IS NULL` のセッションで、**廃止の前後で Likert ターゲットが一致**する（BR-U5-04 フォールバック＝「新規のみ反映」の保証）。
  - **PU5-3（冪等）**: retire/unretire を**複数回適用しても状態が同一**、かつ再廃止で**初回の `retired_at` が保持**される（BR-U5-06）。
  - **PU5-4（export は縮まない・★BR-U5-02 の直接の検出網）**: 廃止の前後で **export の `items` 集合が不変**であり、**judgments の item ⊆ items（自己完結性）が保たれる**（BR-U5-10）。→ **`list_items()` にフィルタを足す劣化実装をしたら落ちる**。
  - **ジェネレータ（PBT-07）**: **廃止済み / 現役が混在するプール**を生成する（「廃止ゼロ件」だけを引くジェネレータでは PU5-1/4 の反例探索が無意味になる）。
  - **unit（example）**: 参照済み item の廃止が成功する（凍結ガードを通らない, BR-U5-05）／`pool_ingest` 再投入で `retired_at` 不変（BR-U5-08）／`not_found`・`already_retired` の分類／充足を割ったら `token_issue` 拒否（BR-U5-09）／`admin_log` の出力。
- **B**: unit のみ（example ベース）。→ **PU5-1/PU5-4 は「特定の 1 例で通る」ことしか示せない**。廃止件数・層構成・参照状況の組合せで劣化実装が生き残る。不採用。

[Answer]:

### Q3【互換性】`EXPORT_FORMAT_VERSION` 据え置き・U3/U4b 無変更の保証
- **★A（推奨）**: **U5 は export の形式を一切変えない**ことを NFR で固定する（BR-U5-10）:
  - `ExportItem` は `item_id` + `layer` のまま（**`retired_at` を出さない**）、`EXPORT_FORMAT_VERSION` は **1.0.0 据え置き**。
  - 保証手段は **既存 PU3-3（自己完結性 PBT）+ 既存 U4b テスト群を無改修で緑に保つこと**（＝形式が変わっていない証拠）。**U5 のために U3/U4b のテストを書き換えたら、それは形式を変えた証拠**＝設計違反のシグナルとして扱う。
  - 将来 retired の分析が必要になった時点で版上げ（1.1.0）+ U4b 改修を別途行う。
- **B**: 先回りして `retired_at` を出し版上げ（1.1.0）。→ U4b 波及（`extra="forbid"` + 版検証が既定エラー）。「それまでの結果は有効」を無改修で満たせる利点を手放す。不採用。

[Answer]:

### Q4【Observability / 監査・Usability】著作権対応の証跡
- **★A（推奨）**:
  - **`admin_log` の記録を必須 NFR に昇格**（BR-U5-11/13）。`item_retire` / `item_unretire` に **対象 `item_id` 列挙・件数・結果**を出す。**これが廃止履歴の正**（`retired_at` は現在状態のみ）。
  - **本文（`body`）はログに出さない**（既存の秘匿方針を維持）。
  - **D1 直操作を運用上排除**: 証跡が残らないため、廃止は **API/CLI 経由を正**とする（runbook に明記）。
  - **CLI の Usability**: `pool_retire` は結果を **retired / already_retired / not_found に分類表示**。**終了コード**: 正常（部分的な `already_retired`・`not_found` を含む）は **0**、認証失敗・通信失敗・入力不正は **非 0**（U4a CLI の既存規約に合わせる）。
    - 論点: **`not_found` が 1 件でもあれば非 0 にするか**。→ **★A では 0 のまま**（`not_found` は「既に存在しない＝目的は達成」なので失敗ではない。ただし stderr に警告を出す）。
- **B**: `not_found` を非 0 にする。→ タイポ検出には有利だが、冪等な再実行（既に消えている状態）が失敗扱いになり運用が回らない。

[Answer]:

### Q5【Security・その他カテゴリの適用性確認】
- **★A（推奨）**:
  - **Security = 既存流用・差分なし**: retire/unretire は**既存 AuthGuard（Basic 認証）の背後**の `/admin/*`（U4a の単一チョークポイント）。**新規シークレット・新規公開面・CORS 変更なし**。クエリは**全パラメータ化**（`item_id IN (...)` のバインド）。参加者 API（`/api/*`）には一切触れない。
  - **Performance / Availability / Scalability / Resiliency = N/A**（プール約 95 件・UPDATE 数件・インデックス不要）。
  - **回帰の完了基準**: **U1/U2/U3/U4a/U4b の既存 unit+PBT を全緑**に保つことをブロッキング条件とする（特に **PU3-3 が緑 = BR-U5-02 の禁止事項を踏んでいない証拠**）。integration は U2/U3 の既存シナリオ（実 D1）を回して migration 0004 適用後も壊れないことを確認。
- **B**: いずれか導入 / 回帰を U5 分のみに限定。→ 規模に対し過剰、または回帰見落とし。不採用。

[Answer]:

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-requirements.md`（U5-NFR-NN）/ `tech-stack-decisions.md`（TSD-U5-NN）を生成 → 標準 2 択（Request Changes / Continue → **NFR Design〈U5〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
