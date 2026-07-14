# U2 Code Generation Summary — 参加者セッション（participant）

**生成日**: 2026-07-14。plan（`construction/plans/u2-code-generation-plan.md`, 全 6 決定点★A）を単一の真実として全 16 ステップを生成。

---

## 生成・変更ファイル

### schema/（U1 波及 + ビュー型）
- **変更** `schema/models.py`: `AssignmentParams.likert_fixed_targets: tuple[str,...] | None` 追加（default None・既存呼び出し不変）。
- **新規** `schema/views.py`: 参加者レスポンス契約 `ItemView`（`{item_id, body}` のみ＝出自秘匿を型で強制, DP-U2-02）/ `PairView` / `LikertScale` / `LikertTargetView` / `Progress` / `SessionView` / `SubmitResult` / `ApiError`。
- **変更** `schema/__init__.py`: 上記ビュー型を公開。

### migrations/
- **新規** `migrations/0003_likert_unique.sql`: `likert_responses` に `UNIQUE INDEX(token, target_ref)`（初回不変の DB 側冪等, BR-U2-17）。deploy.yml は versioned 自動適用で無変更。

### backend/domain/（純関数）
- **新規** `backend/domain/likert.py`: `select_likert_targets(pool, seed, params)`（fixed 優先 + seed 層均等補充・決定論, BR-U2-14/15）。`__init__` に公開（+ `next_unanswered_index` も再公開）。

### backend/repo/（U1 拡張）
- **変更** `backend/repo/repository.py`: `get_session` / `get_pairs` / `answered_pair_ids` / `answered_likert_refs` / `survey_exists`（読取）、`insert_likert`（ON CONFLICT DO NOTHING + 既存 rating 返却=初回不変）、`upsert_survey`（PK=token upsert）。全パラメータ化クエリ。

### backend/participant/（新規パッケージ）
- `phase.py`: `derive_phase`（純粋述語・5 状態導出）+ `is_complete`（完了順序判定）。
- `log.py`: `participant_log`（許可フィールド限定）+ `token_hash`（SHA-256 先頭 8 文字・単一規約, DP-U2-03）。
- `view.py`: ViewSerializer — domain→view 写像の一点集約（出自を落とす, DP-U2-02）。
- `session.py`: `start_or_resume` / `build_view`（サーバ権威の単一経路）/ `check_complete` / `seed_from_token`（**トークン由来決定論シード**, Q1=A）。
- `response.py`: `submit_judgment`（サーバ is_practice 判定・冪等）。
- `survey.py`: `submit_likert`（初回不変）/ `submit_survey`（upsert + 完了順序サーバ確認 → mark_completed）。
- `api.py`: ParticipantApi（`/api/*` ルーティング・トークン検証チョークポイント・no-store 共通ヘルパ・統一エラー封筒）。
- `errors.py`: `ParticipantError`（業務エラー）。
- **変更** `backend/entry.py`: `on_fetch` に `/api/*` 分岐追加（`/admin/*`・ヘルス維持）。

### frontend/（新規 SPA）
- `index.html`（アプリシェル）/ `app.js`（フェーズ駆動ウィザード・サーバ権威・楽観更新なし・localStorage はトークンのみ・軽いリトライ）/ `styles.css`（モバイルファースト・A/B 縦積み・日本語・合理的 a11y）。対話要素に `data-testid`（`{component}-{role}`）。
- **変更** `wrangler.toml`: `[assets] directory = "frontend"`（同一 Worker/同一オリジン配信, Infra Q1=A）。

### テスト
- **新規 PBT** `tests/pbt/test_likert_selection.py`（PU2-6）・`tests/pbt/test_phase.py`（PU2-3）。
- **新規 integration** `tests/integration/drive_u2.py`（`/api/*` 越し PU2-2/4/5/7/8 + 一巡）。`src/it_entry.py` に補助ルート（`/it/seed-token`・`/it/likert-rating`・`/it/exposure`）追加。

---

## API 一覧（参加者系・トークン=資格・全応答 no-store）
| メソッド パス | 用途 | レスポンス |
|---|---|---|
| `GET /api/session?token=` | start_or_resume + 状態 | SessionView |
| `POST /api/judgment` `{token,pair_id,choice}` | 判定（冪等） | SubmitResult |
| `POST /api/likert` `{token,target_ref,rating}` | Likert（初回不変） | SessionView |
| `POST /api/survey` `{token,answers}` | アンケート + 完了遷移 | SessionView |
| `GET /api/ping` | Step 1 beta 検証用 | `{ok,unit,route}` |

業務エラーは 200 + `{ok:false, error, phase?}`（DP-U2-07）。

---

## テスト実行実績（この環境）
- **unit + PBT: 33 passed**（ci プロファイル 200 examples）。U1 19 + U4a 系 + **U2 追加 PU2-3/6**。回帰緑（`AssignmentParams` 追加は default None で既存不変を確認）。
- **サービス層一巡（Fake Repository・pure-Python）**: practice→judging→likert→survey→done、判定冪等・Likert 初回不変・完了順序・出自秘匿（next_pair に layer なし）を確認。
- **全 Python 構文チェック（py_compile）**: OK。
- **PU2-1（serialize/deserialize ラウンドトリップ）**: 既存 `tests/pbt/test_serializer` 相当（U1 serializer, XC-02）で担保。

## ユーザー側で実施する実機検証（実行実績提示）
1. **beta 検証（Step 1, Infra §6-β）**: Static Assets × Python Workers — `/api/ping` が Worker 到達 / アセット `/` 配信 / deploy 同梱。想定外→是正 → C（Worker 埋め込み）→ B（Pages）。
2. **integration**（実 D1・miniflare）: `tests/integration/`（`cp` で本体同期 → `d1 migrations apply --local`（0001+0002+0003）→ `pywrangler dev` → `python drive_u2.py`）。PU2-2/4/5/7/8 + 一巡。

## 決定点の実装対応
| 決定点 | 実装 |
|---|---|
| Q1 seed=token 由来決定論（U1 FD Q4=B 生成方法の改訂） | `session.seed_from_token`。U1 側 business-logic-model §4 に改訂注記済み |
| Q2 derive_phase 配置 | `backend/participant/phase.py`（純粋述語） |
| Q3 SessionView サーバ全算出 | `session.build_view` + 送信レスポンスで再同期 |
| Q4 frontend 3 ファイル + data-testid | `frontend/{index.html,app.js,styles.css}` |
| Q5 beta 失敗時 是正→C→B | Step 1 に明記・配信手段のみ差替可能な構造 |
| Q6 回帰全緑ブロッキング | unit+PBT 33 緑で確認済み |
