# U2 Domain Entities — 参加者セッション（participant）

**ユニット**: U2。U1 の永続エンティティ（`Item`/`Token`/`Session`/`Pair`/`Judgment`/`LikertResponse`/`SurveyResponse`/`SessionState`）を**再利用**し、参加者 API の**ビュー型（レスポンス）**と U1 への**波及変更**を定義する。ビュー型は `schema/` に追加し、Worker（`backend/participant/`）が返す（単一データ契約）。フロントはこれを消費する（frontend-components.md）。

---

## 1. 再利用する U1 永続エンティティ（変更なし）

| エンティティ | 用途（U2） |
|---|---|
| `Item`（`item_id, layer, body, body_ref`） | ペア本文表示（`body`, U4a 格納）・Likert 対象 |
| `Token`（`token, status, issued_at, last_active_at`） | 資格・状態（一方向 BR-09）・非アクティブ判定（BR-04） |
| `Session`（`token, phase, seed, exposure_snapshot, created_at`） | 新規開始で保存。`seed` は Likert/ペア列の監査再現（BR-U2-06） |
| `Pair`（`pair_id, index, item_left, item_right, is_practice`） | 確定 PairSequence。`is_practice` はサーバ判定の根拠（BR-U2-08） |
| `Judgment`（`token, pair_id, choice, created_at`） | 冪等判定（練習含む, BR-U2-07） |
| `LikertResponse`（`token, target_ref, rating, created_at`） | Likert 評定。`target_ref = item_id`（BR-U2-14） |
| `SurveyResponse`（`token, answers, created_at`） | アンケート（暫定 dict, BR-U2-20） |
| `SessionState`（`pairs, next_index`） | XC-02 論理単位。再構成専用・別 blob 非永続（BR-U2-22） |

---

## 2. U1 エンティティへの波及変更（U2 スコープに含む）

### 2.1 `AssignmentParams` の拡張（Q3 機構）
| フィールド | 変更前 | 変更後（U2 波及） |
|---|---|---|
| `likert_fixed_targets` | （なし） | **`list[str] | None = None`** = Likert 固定アンカーの item_id 列。`select_likert_targets` が優先採用し、不足は seed 層均等補充（BR-U2-15） |

- 他フィールド（`session_pairs`/`practice_pairs`/`likert_items`/`k`/`cross_layer_min_ratio`/`inactive_threshold_hours`）は変更なし。
- 方針（全固定/混合/全ランダム）はプール凍結時に `likert_fixed_targets` の値で選択（Negotiable, BR-U2-19）。

### 2.2 `likert_responses` テーブルの冪等化（Q8）
| 変更 | 内容 |
|---|---|
| `migrations/0003_*.sql` | `likert_responses` に **`UNIQUE(token, target_ref)`** 追加（初回不変の冪等化, BR-U2-17）。新規プロジェクトのため既存行の移行問題なし |

- `survey_responses` は既に PK=token（upsert 可, BR-U2-21）。追加 migration 不要。
- `judgments` は既に `UNIQUE(token, pair_id)`（DP-02, 再利用）。

---

## 3. 参加者 API ビュー型（schema/ に追加・レスポンス契約）

### SessionView（`GET /api/session` の主レスポンス）
| フィールド | 型 | 意味 |
|---|---|---|
| `status` | `'unused' | 'in_progress' | 'completed'` | `token.status`（unused は開始処理後 in_progress で返す） |
| `phase` | `'practice' | 'judging' | 'likert' | 'survey' | 'done'` | `derive_phase` の結果（5 状態, BR-U2-01） |
| `next_pair` | `PairView | None` | practice/judging で次に提示するペア（本文込み） |
| `next_likert` | `LikertTargetView | None` | likert で次に評定する対象 |
| `progress` | `{ done: int, total: int }` | **本番判定のみ**（BR-U2-13） |
| `practice` | `{ done: int, total: int }` | 練習の別カウント |

### PairView（判定画面の表示単位）
| フィールド | 型 | 意味 |
|---|---|---|
| `pair_id` | str | 判定送信キー |
| `index` | int | セッション内提示順 |
| `left` | `ItemView` | A（上/先）= `item_left` |
| `right` | `ItemView` | B（下/後）= `item_right` |
| `is_practice` | bool | 表示上の練習明示（集計判定はサーバ内部, H-3） |

- **`ItemView` = `{ item_id: str, body: str }`**（本文のみ公開。`layer`/`body_ref` は参加者に出さない＝評価バイアス回避）。

### LikertTargetView（Likert 画面の表示単位）
| フィールド | 型 | 意味 |
|---|---|---|
| `target_ref` | str | 評定対象 item_id（送信キー） |
| `body` | str | 対象の謎かけ本文 |
| `scale` | `{ min: 1, max: 7 }` | 尺度範囲（`rating ∈ [1,7]`, BR-U2-18） |

### SubmitResult（`POST /api/judgment` のレスポンス, Q6）
| フィールド | 型 | 意味 |
|---|---|---|
| `saved` | bool | 今回保存されたか（初回 true） |
| `duplicate` | bool | 再送で既存と一致（冪等観測） |
| `choice` | `'A' | 'B'` | 保存されている（初回の）choice |
| `next_pair` | `PairView | None` | 次に提示するペア（なければ次フェーズへ） |
| `phase` | フェーズ enum | 更新後の導出フェーズ |
| `progress` | `{ done, total }` | 更新後の本番進捗 |

### 統一エラー封筒（業務エラー, BR-U2-29）
- 業務エラーは **HTTP 200 + `{ ok: false, error: str, phase?, ... }`**（U4a と同水準）。資格不備（無効トークン）は明確なエラー応答。`ok=true` の正常時は上記ビュー型を返す。

> 補足: `submit_likert` / `submit_survey` のレスポンスは、次アクション同期のため **SessionView（更新後）** を返す方針（Code Generation で最終形を確定）。

---

## 4. 参加者に**公開しない**フィールド（評価健全性・秘匿）

| 非公開 | 理由 |
|---|---|
| `Item.layer` / `Item.body_ref` | 出自（プロ/AI 等）が見えると評価バイアス（XC-01 の目的を損なう） |
| `Session.seed` / `exposure_snapshot` | 監査・内部再現用（参加者に不要） |
| `Pair` の元 item の帰属層 | 上と同じ |
| トークンの他者分・発行総数 | 参加者スコープ外（U3 の研究者機能） |

---

## 5. 永続化先（D1, U1 DDL + migration 0003）
- `sessions`（新規開始で 1 行, PK=token）、`pairs`（確定ペア列, PK=(token,pair_id)）、`judgments`（PK 相当 UNIQUE(token,pair_id)）。
- `likert_responses`（**UNIQUE(token,target_ref)** 追加, 0003）、`survey_responses`（PK=token, upsert）。
- 書き込みは Repository 経由のみ（U2 追加: `insert_likert` / `upsert_survey`、既存: `save_pair_sequence` / `insert_judgment` / `mark_token_*` / `touch_token`）。scripts/フロントは直接 D1 に触れない。

---

## 6. 関係図（データフロー）
```
[frontend SPA]  --GET /api/session?token=------→ SessionService.start_or_resume
                --POST /api/judgment {t,pid,ch}-→ ResponseService.submit_judgment
                --POST /api/likert {t,ref,r}----→ SurveyService.submit_likert
                --POST /api/survey {t,answers}--→ SurveyService.submit_survey
        (HTTPS, /api/*, Cache-Control: no-store, トークン=資格)
                                 │
                                 ▼
        [ Worker backend/participant/ (トークン検証・フェーズ導出) ]
            ├─ backend/domain: generate_pairs / select_likert_targets / serializer
            └─ backend/repo: Repository（save_pair_sequence / insert_judgment /
                             insert_likert / upsert_survey / read_exposure_counts / list_items）
                                 │ env.DB（batch=原子, パラメータ化クエリ）
                                 ▼
        [ D1: sessions / pairs / judgments / likert_responses / survey_responses / tokens / items ]
                                 │
        [frontend] ← SessionView / SubmitResult（本文込み・出自は非公開）
```
