# U2 Logical Components — 参加者セッション（participant）

**方針**: U2 は U1 の公開面（schema / Repository / domain / LogEmitter / serializer）と U4a が投入したデータを消費・拡張し、**参加者 API 境界（`backend/participant/`）と静的フロント（`frontend/`）を追加**する。専用インフラ部品（queue/cache/CB/lock/scale）は導入しない（DP-U2 非採用表）。層の逆流禁止（`backend/participant` → domain/repo/schema の一方向）。

---

## 論理コンポーネント一覧

### LC-U2-01: ParticipantApi（`backend/participant/` + `entry.py`）
- **役割**: 参加者エンドポイント境界。`on_fetch` 内で `/api/session`・`/api/judgment`・`/api/likert`・`/api/survey` を手動ディスパッチ（raw workers API, F-5）。**入口でトークン検証チョークポイント**（DP-U2-01）、**共通レスポンスヘルパで no-store + 統一封筒**（DP-U2-04/07）。
- **フロー**: token 検証（DP-U2-01）→ サービス呼び出し（LC-U2-02〜04）→ view 写像（LC-U2-05）→ no-store 応答 + 更新後 SessionView（DP-U2-07）。
- **依存**: LC-U2-02〜05、U1 `Repository`（+U2 拡張）、`schema`（ビュー型）、LC-U2-06（ログ）。

### LC-U2-02: SessionService（`backend/participant/`）
- **役割**: `start_or_resume` / `get_state` / 完了遷移。新規開始（`generate_pairs` → `save_pair_sequence` → `mark_token_in_progress`）、再開（DB 行から `derive_phase` + `next_unanswered_index` で再構成）。**`derive_phase` を純粋述語として保持**（DB カウントは Repository で集めて引数で渡す, DP-U2-05）。
- **依存**: U1 `Repository`・`generate_pairs`・`select_likert_targets`（LC-U2-07）・`serializer`・`schema`。

### LC-U2-03: ResponseService（`backend/participant/`）
- **役割**: `submit_judgment`。`pair_id` のトークン帰属・`is_practice` をサーバ判定（H-3）、`insert_judgment` で冪等保存、`SubmitResult` 合成。
- **依存**: U1 `Repository`（`insert_judgment`）・`schema`。

### LC-U2-04: SurveyService（`backend/participant/`）
- **役割**: `submit_likert`（`(token,target_ref)` 初回不変）/ `submit_survey`（PK=token upsert + **完了順序のサーバ確認** → `mark_token_completed`）。
- **依存**: U1 `Repository`（+`insert_likert`/`upsert_survey`/完了確認集計, LC-U2-... = Repository 拡張）・`schema`。

### LC-U2-05: ViewSerializer（`backend/participant/`, 出自秘匿の強制点）
- **役割**: **domain→view の写像を 1 箇所**に集約（DP-U2-02）。`Item`→`ItemView={item_id,body}`、`Session`+`pairs`+`judgments`→`SessionView`、`Pair`→`PairView`（本文込み・出自なし）。`layer`/`body_ref`/`seed`/`exposure_snapshot` を構造的に落とす。
- **依存**: `schema`（domain モデル + ビュー型）。純粋（副作用なし）。

### LC-U2-06: ParticipantLog（横断, `backend/participant/log.py`）
- **役割**: 参加者操作の**秘匿ログ強制点**（DP-U2-03）。U1 `emit` を許可フィールド限定で呼ぶラッパ。**トークン生値・本文を構造的に排除**、相関は**トークンハッシュ（SHA-256 先頭 8 文字・単一ユーティリティ）**。
- **依存**: U1 `backend.log.emit`。U4a AdminLog と対をなす。

### LC-U2-07: LikertSelector（`backend/domain/`, 純粋）
- **役割**: `select_likert_targets(pool, seed, params) -> list[str]`。`likert_fixed_targets` 優先 + seed 層均等補充。決定論（P-6）・副作用なし（DP-U2-05）。PBT 対象（PU2-6）。
- **依存**: `schema`（Item/AssignmentParams）のみ。`generate_pairs` と同居。

### LC-U2-08: ParticipantFrontend（`frontend/`）
- **役割**: 単一 HTML + バニラ JS の SPA ウィザード。画面=5 フェーズ、**状態はサーバ権威**（SessionView 描画）、クライアントは localStorage にトークンのみ、**楽観更新なし**（DP-U2-07 / U2-NFR-09）。モバイルファースト・日本語・合理的 a11y（U2-NFR-07/08）。`fetch` で `/api/*`。
- **依存**: ParticipantApi（HTTPS, `/api/*`）。配信方法は Infrastructure Design。

### Repository 拡張（U1 LC-03 拡張, U2 波及）
- `insert_likert(token, target_ref, rating, now)`（`ON CONFLICT DO NOTHING` + 既存 rating 返却=初回不変）、`upsert_survey(token, answers, now)`（PK=token）、回答済み pair_id / Likert 済み target_ref / 完了確認用の集計読み取り。既存（`save_pair_sequence`/`insert_judgment`/`mark_token_*`/`touch_token`/`list_items`/`read_exposure_counts`）を再利用。**Worker 内専用**。

### DataContract 拡張（U1 LC-01 = `schema/`, U2 波及）
- **ビュー型追加**: `SessionView` / `PairView` / `ItemView`（={item_id,body}）/ `LikertTargetView` / `SubmitResult`。
- `AssignmentParams` に `likert_fixed_targets: list[str] | None = None` 追加。
- `likert_responses` に `UNIQUE(token, target_ref)`（migration 0003）。

---

## 依存方向（層の逆流禁止）

```
[ frontend/ SPA (LC-U2-08) ]  ──HTTPS, /api/* (no-store)──►  ┐
                                                             ▼
      ┌──────────── LC-U2-01 ParticipantApi (backend/participant/, entry.py) ────────────┐
      │  入口: トークン検証チョークポイント(DP-U2-01) / no-store+封筒(DP-U2-04/07)          │
      │   → LC-U2-02 SessionService   → LC-U2-05 ViewSerializer(出自秘匿)                  │
      │   → LC-U2-03 ResponseService  → LC-U2-06 ParticipantLog(秘匿・横断)                │
      │   → LC-U2-04 SurveyService                                                         │
      └───────────────┬──────────────────────────────┬──────────────────────────────────┘
                       │ import（公開面のみ）          │
          ┌────────────▼───────────┐      ┌───────────▼─────────────┐
          │ backend/domain          │      │ backend/repo Repository  │
          │  generate_pairs         │      │  (+insert_likert /       │
          │  select_likert_targets  │      │   upsert_survey / 集計)  │  ← Worker 専用
          │  serializer (LC-U2-07)  │      └───────────┬─────────────┘
          └────────────┬───────────┘                  │
                       │                    ┌──────────▼───────────┐
                       └───────────────────►│ LC-01 DataContract    │ ← 最下層（schema/, U2 でビュー型/params 拡張）
                                            └───────────┬───────────┘
                                                        │
                                                     [ D1 ]（migration 0003: likert UNIQUE）
```

- **一方向依存**: フロントは `/api/*` のみ、ParticipantApi は U1 公開面（Repository/domain/serializer/log）+ schema ビュー型。**U2 から上位（U3）への依存なし**、`derive_phase`/`select_likert_targets`/`ViewSerializer` は純粋（副作用は Repository に集約）。
- **出自秘匿は LC-U2-05 に一点集約**（型で排除, DP-U2-02）。**トークン秘匿は LC-U2-06 に一点集約**（DP-U2-03）。

---

## 後続への申し送り（Infrastructure Design / Code Generation）
- **Infrastructure Design（U2）**: `/api/*` ルート（U1/U4a と同一 Worker）・**フロント配信方法（Worker 静的返却 / Cloudflare Pages 併用）と CORS/配信オリジン**（同一オリジンなら CORS 不要、別オリジンなら許可元限定, TSD-U2-01）・migration 0003 の適用順。基盤は U1/U4a 共有（D1 + CI デプロイ）を流用するため差分は小さい見込み。
- **Code Generation**: `backend/participant/`（ParticipantApi + Session/Response/Survey Service + ViewSerializer + ParticipantLog + derive_phase）、`backend/domain/select_likert_targets`、`schema/` ビュー型 + `likert_fixed_targets`、migration 0003、Repository 追加メソッド、`frontend/` SPA、PBT（PU2-1/3/6）+ integration（PU2-2/4/5/7/8）。
