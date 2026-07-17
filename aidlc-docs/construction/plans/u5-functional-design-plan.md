# U5 Functional Design Plan — 出題停止（item retirement）

**ユニット**: U5（新規・全 5 ユニット完了後の追加要件）。
**背景・要件**: **著作権上の配慮**により、投入済み作品の一部を**今後出題しない**必要が生じた。運用者の確定要件:
- **物理削除は不要**（行は残してよい）
- **それまでの判定結果は有効のまま**（過去データを毀損しない）
- **進行中セッションへの反映は不要**（新規セッションのみ反映すればよい）

**目的**: 論理削除（廃止フラグ）で「新規セッションから出題されない」状態を作る。**過去の判定・BT 集計は不変**。

**前提（既決・U1〜U4b で確定）**: 案 A′（Python Workers + D1）。共有インフラは U1 所有。`items` は `item_id`/`layer`/`body`/`body_ref`。凍結ガード BR-U4a-03（参照済み item への UPDATE 拒否）。ExportBundle 正本（BR-U3-07・**body 非含有**）。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に Part 2 成果物を生成します。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-17, 全 6 問 A）
- [x] `construction/u5/functional-design/business-rules.md`（BR-U5-NN）
- [x] `construction/u5/functional-design/business-logic-model.md`（廃止フローと参照先の分離）
- [x] `construction/u5/functional-design/domain-entities.md`（`items` スキーマ差分 = migration 0004・`sessions` 差分）

---

## 調査で判明した事実（設計の前提・実装確認済み）

| # | 事実 | 出典（確認済み） |
|---|---|---|
| 1 | **削除 API も廃止フラグも存在しない**。管理 API は `POST /admin/items` / `POST /admin/tokens` + GET のみ | `src/backend/admin/api.py` |
| 2 | **エクスポートは `body` を含まない**（`ExportItem` = `item_id`+`layer`）→ **廃止 item を export に残しても著作権リスクなし**・自己完結性（BR-U3-07）を保てる → **U4b は無改修で過去結果が有効**（要件と完全整合） | `src/schema/admin_views.py` |
| 3 | **ペア列はセッション開始時に一括生成・保存**（`generate_pairs`→`save_pair_sequence`）→ 進行中セッションは固定リストを持つ＝**「新規のみ反映」なら配信段の改修は不要** | `src/backend/participant/session.py` |
| 4 | ⚠️ **Likert ターゲットは保存されず毎回導出**（`build_view` が `select_likert_targets(pool, seed, params)` を都度実行）→ **プールを絞ると進行中セッションのターゲットが変わる**＝「新規のみ反映」の約束が破れる | `src/backend/participant/session.py` / `domain/likert.py` |
| 5 | `sessions` は `token`/`phase`/`seed`/`exposure_snapshot`/`created_at`。**likert_targets は未保存** | `migrations/0001_init.sql` |
| 6 | ⚠️ **凍結ガード BR-U4a-03 は参照済み item への UPDATE を拒否**（投入全体を中断）。廃止フラグの付与は UPDATE ＝**正面衝突**。しかも廃止したい item はまさに参照済み | `repo/repository.py` / `u4a/functional-design/business-rules.md` |
| 7 | 割当・Likert 選定・充足判定はすべて `list_items()`（items 全件・フィルタなし） | `session.py` / `survey.py` / `admin/api.py` |

**波及範囲**: migration 0004 / U4a（廃止の入口・凍結ガードの整理）/ U1（割当・充足の母数）/ U2（Likert 導出の安定化）/ U3（export は全件のまま＝確認のみ）/ **U4b は無変更**。

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【スキーマ表現】廃止をどう持つか
- **★A（推奨）**: **`items.retired_at TEXT`**（NULL=現役 / ISO8601=廃止時刻）。`ALTER TABLE items ADD COLUMN retired_at TEXT` で足せる（NULL 許容ゆえ **0002 のようなテーブル再構築は不要**）。**いつ廃止したかが残る**＝著作権対応の経緯を DB 自体が持つ（監査証跡）。
- **B**: `is_active INTEGER NOT NULL DEFAULT 1`。真偽のみで**時刻が残らない**。著作権対応は「いつ止めたか」が問われうるため不利。
- **C**: 別テーブル `retired_items`。JOIN が全経路に増える割に利点が薄い。

[Answer]:A

### Q2【最重要】Likert ターゲットの安定化 — 「新規のみ反映」をどう守るか
**問題**（事実 #4）: `build_view` は新規・進行中を区別せず毎回プールから Likert ターゲットを導出する。`list_items()` を active でフィルタすると、**進行中セッションのターゲットが変わり**、回答済み参照との整合とフェーズ判定が壊れる。ペア列（保存済み＝安定）と非対称なのが原因。

- **★A（推奨）**: **Likert ターゲットをセッション開始時に確定・保存する**（`sessions.likert_targets TEXT` = JSON 配列を migration 0004 で追加）。`build_view` は**保存値を読む**。
  - **ペア列と同じ「開始時確定」原則に揃う**＝導出と保存の非対称性という設計の歪み自体を解消（今回の要件がなくても正しい形）。
  - **進行中セッションは完全に不変**＝要件「新規のみ反映」をデータ構造で保証（規約でなく構造で守る）。
  - **後方互換**: 既存の進行中セッションは `likert_targets IS NULL` → 従来どおり全 items から導出にフォールバック（移行中のセッションを壊さない）。
  - 副次: XC-02（セッション状態のラウンドトリップ）とも整合。
- **B**: `build_view` の導出は全 items のまま・新規セッション生成時のみ active でフィルタ。→ **build_view は導出しかせず新規/既存を区別できない**ため実質不可能。
- **C**: ターゲットが変わるのを許容。→ 回答済み参照との不整合・フェーズ判定破綻。不採用。

[Answer]:A

### Q3【凍結ガードとの関係】廃止は BR-U4a-03 の対象か
**問題**（事実 #6）: BR-U4a-03 は参照済み item への UPDATE を拒否＝**廃止フラグの付与も拒否**されてしまう。

- **★A（推奨）**: **廃止は凍結ガードの対象外**とし、**専用経路でのみ許可**する。根拠: 凍結ガードの目的は BR-U4a-03 が明記するとおり「**判定後の本文・層の書換で過去判定の解釈が壊れる**（研究データ完全性）」の防止。`retired_at` の付与は **`body`/`layer` を変えない**＝過去判定の解釈は一切壊れない。よってガードの趣旨に反しない。**`body`/`layer` の UPDATE は引き続き拒否**（凍結は維持）。
  - 実装上: `insert_items` の凍結ガードはそのまま。廃止は別関数・別エンドポイント（Q4）。
- **B**: 凍結ガードを緩めて `pool_ingest` から廃止も可能にする。→ 投入と廃止の責務が混ざり、ガードの穴になる。不採用。

[Answer]:A

### Q4【操作の入口】廃止をどう実行するか
- **★A（推奨）**: **専用 CLI `scripts/pool_retire.py` + `POST /admin/items/retire`**（U4a 管理 API に追加・既存 Basic 認証の背後）。入力 = `item_id` 列。**冪等**（既に廃止済みは no-op）。`admin_log` に記録（著作権対応の証跡）。**復活 `--unretire`** も対で用意（誤操作の回復・`retired_at=NULL`）。
- **B**: D1 直操作（`wrangler d1 execute ... UPDATE items SET retired_at=...`）。→ **監査ログが残らず**誤操作リスクも高い。著作権対応の証跡としては不適。
- **C**: `pool_ingest` にフラグ相乗り。→ Q3-B と同じ理由で不採用。

[Answer]:A

### Q5【充足判定の母数】active のみか全件か
- **★A（推奨）**: **active のみで判定**（① 総数 ≥ ceil(2×session_pairs/k) ② 4 層非空 ③ 層間供給）。**出題できない作品を母数に入れてはいけない**（入れると「発行はできるがペア生成が偏る/失敗する」状態を作る）。廃止の結果ゲートを割ったら**発行拒否が正しい挙動**＝補充を促す。
  - `pool_ingest` の `sufficiency_warnings`（マージ後の見込みプール, BR-U4a-05）も active ベースで評価。
- **B**: 全件で判定。→ 廃止しても発行できてしまい、実際には active 不足で割当が破綻。不採用。

[Answer]:A

### Q6【エクスポート】`retired_at` を ExportBundle に含めるか
**前提**: 廃止 item は **`items` に残し続ける**（事実 #2・自己完結性 BR-U3-07 に必須・body 非含有ゆえ著作権 OK）。これは決定事項。問うのは `retired_at` を**出すか**。

- **★A（推奨）**: **含めない**。理由: BT 集計は `retired_at` を使わない。含めると `ExportItem` の形式変更＝**BR-U3-07 により `EXPORT_FORMAT_VERSION` の版上げ必須**（1.0.0→1.1.0）→ **U4b の版検証が既定でエラー**になり U4b にも波及（`extra="forbid"`）。**U4b 無変更**という最大の利点（要件「過去結果は有効」を無改修で満たす）を手放す代償に見合わない。廃止の事実と時刻は D1・管理ログ・運用記録に残る。
- **B**: 含める（版上げ 1.1.0 + U4b 改修）。→ 分析側で「いつから出題停止か」が export 単体で分かる利点。ただし波及が U3/U4b に及ぶ。**将来 retired の分析が必要になった時点で版上げする**方が筋がよい。

[Answer]:A

---

**Part 2 生成時の追加反映（レビュー指摘 3 点・2026-07-17）**:
1. **読み取り経路の分割を「関数の分割」で BR に明文化**（BR-U5-02）: `list_items()` は全件のまま**凍結**・`list_active_items()` を**新設**。`list_items()` 自体にフィルタを足すと **(1) export の items が縮み PU3-3 違反→U4b 破壊**（＝「結果は有効」が壊れる）**(2) 旧セッションのフォールバック導出が変わり「新規のみ反映」が破れる**の**両輪が同時に壊れる**。MM 式・α 適用位置と同系の「テストで検出しにくい仕様は明文で固定」案件。
2. **`retired_at`=現在状態 / `admin_log`=履歴の正**（BR-U5-13）: unretire は NULL に戻すため廃止→復活→再廃止の履歴はカラム単体に残らない。役割分担を明記（追加実装なし）。
3. **練習試行の経路を調査**（BR-U5-02b）: 練習ペアは**別経路を持たない**（`generate_pairs` が `practice_pairs + session_pairs` を同一プール・同一呼び出しで生成し先頭を練習とするだけ, BR-10）→ **active フィルタが自動的に効き漏れなし**。`assignment.py` で確認済み。

**追加で判明した事実**: `select_likert_targets` の導出は **3 箇所**（`build_view` / `check_complete` / `submit_likert`）。一部だけ保存値に切り替えると**表示されたターゲットの送信が拒否される**不整合 → **単一アクセサ `get_likert_targets` に集約必須**（BR-U5-04）。`pairs.item_left/item_right` に **FK `REFERENCES items(item_id)`** があり物理削除は FK 違反（BR-U5-01 の構造的根拠）。

**次**: 標準 2 択（Request Changes / Continue → **NFR Requirements〈U5〉**）。
