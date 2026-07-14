# U2 Business Logic Model — 参加者セッション（participant）

**ユニット**: U2。参加者 API（`/api/*`, `entry.py` 配線）＋ `backend/participant/`（SessionService / ResponseService / SurveyService の薄いオーケストレーション）＋ Likert 対象選定の新規純関数（`backend/domain/`）＋ フロント（`frontend/`, 別文書 frontend-components.md）で構成。技術非依存の業務ロジックを記述する。

**設計原理**: U1/U4a が土台を提供済みのため、U2 サービス層は**薄い**。状態の真実は DB 実データにあり（H-2 と一貫）、サービスは「読み取り → 導出 → 冪等書込 → SessionView 合成」を行う。**クライアント申告値は信用しない**（H-3）。

---

## 1. 構成要素（責務境界）

| 要素 | 配置 | 役割 | 新規/拡張 |
|---|---|---|---|
| 参加者エンドポイント | `backend/participant/` + `entry.py` | `/api/session`・`/api/judgment`・`/api/likert`・`/api/survey`（トークン=資格、Basic 認証なし, Q5=A） | 新規（U2） |
| `SessionService` | `backend/participant/` | `start_or_resume` / `get_state`（フェーズ導出・次ペア・進捗の合成）・完了遷移 | 新規（U2） |
| `ResponseService` | `backend/participant/` | `submit_judgment`（サーバ is_practice 判定・冪等, Q6=A） | 新規（U2） |
| `SurveyService` | `backend/participant/` | `submit_likert`（初回不変）/ `submit_survey`（upsert）（Q8=A） | 新規（U2） |
| `select_likert_targets` | `backend/domain/` | Likert 対象選定の純関数（fixed 優先 + seed 層均等補充, Q3=X） | **新規（U2, 純ロジック）** |
| フェーズ導出述語 | `backend/participant/` | DB カウントから 5 状態を導出（Q1=A） | 新規（U2） |
| 参加者系ログ | `backend/participant/` | トークン非出力の構造化ログ（AdminLog と同水準, Q5 補足） | 新規（U2） |
| Likert 冪等化 | `schema/`+`migrations/`+`backend/repo/` | `UNIQUE(token,target_ref)`・`migrations/0003_*.sql`・`insert_likert`/`upsert_survey` | **U1 波及（U2, Q8=A）** |
| `AssignmentParams` 拡張 | `schema/` | `likert_fixed_targets: list[str] | None` 追加（Q3 機構） | **U1 波及（U2, Q3=X）** |

- **依存方向**: フロント →(HTTPS, `/api/*`)→ 参加者エンドポイント → SessionService/ResponseService/SurveyService → `backend/domain`（generate_pairs / serializer / select_likert_targets）・`backend/repo`（Repository）→ D1。**層の逆流禁止**（`backend/participant` → domain/repo/schema の一方向）。
- 参加者エンドポイントは raw workers API + `on_fetch` 内ルーティング（F-4/F-5, U1/U4a と同規約）。`/admin/*` と別接頭辞 `/api/*`。

---

## 2. フェーズ状態機械（Q1=A — 5 状態・DB 導出）

**サーバ状態集合（`instruction` を除外）**: `practice → judging → likert → survey → done`。`sessions.phase` は開始時スナップショット（監査用）で、遷移判定の権威にしない。**現在フェーズは毎回 DB から導出**する。

### 2.1 導出述語（`derive_phase`）
確定 PairSequence（`pairs`）・判定行（`judgments`）・Likert 行・Survey 行・トークン状態から算出:

```
入力: pairs（is_practice 含む）, answered_pair_ids, likert_targets, likert_answered_refs, survey_exists, token.status

if token.status == 'completed':            → done
practice_pairs   = [p for p in pairs if p.is_practice]
production_pairs = [p for p in pairs if not p.is_practice]

if not all(p.pair_id in answered_pair_ids for p in practice_pairs):
    → practice          # 練習ペアに未回答が残る（練習 0 件なら instruction を UI 前置）
elif not all(p.pair_id in answered_pair_ids for p in production_pairs):
    → judging           # 本番ペアに未回答が残る
elif not all(ref in likert_answered_refs for ref in likert_targets):
    → likert            # Likert 対象に未評定が残る
elif not survey_exists:
    → survey            # アンケート未提出
else:
    → done              # 全部揃い（このとき mark_complete 済みのはず, §5）
```

- **教示（instruction）の扱い（Q1 補足）**: 「教示を読み終えたか」は判定行から導出不能。よって**サーバ状態からは外し**、UI 規約「`phase=practice` かつ練習判定 0 件 → クライアントが教示画面を前置」で表現。再開時の教示再表示は無害。
- **線形性の保証**: 導出は「先に来るフェーズの未完があればそこへ戻す」ため、順序外送信（例: judging 未完で survey 送信）に対しても常に**正しい現行フェーズ**を返せる（Q11 のフェーズ外再同期の基盤）。

### 2.2 SessionView（サービスの出力・サーバ権威）
```
SessionView = {
  status:   'unused' | 'in_progress' | 'completed',   # token.status
  phase:    'practice' | 'judging' | 'likert' | 'survey' | 'done',  # derive_phase
  next_pair: PairView | None,     # judging/practice で次に提示するペア（本文込み）
  next_likert: LikertTargetView | None,  # likert フェーズで次に評定する対象
  progress: { done: int, total: int },   # 本番判定のみ（Q7=A）
  practice: { done: int, total: int },   # 練習の別カウント
}
PairView = { pair_id, index, left: {item_id, body}, right: {item_id, body}, is_practice }
```
- `next_pair` は `next_unanswered_index`（既存, フェーズ内の未回答先頭）で決定。本文は `Item.body`（U4a で D1 格納）を Repository から取得。

---

## 3. start_or_resume フロー（US-P01 / US-P08, `GET /api/session?token=`）

```
1. トークン検証: repo.get_token(token)
     None → SessionView 相当のエラー（無効トークン, Q11）: status なし・エラー表示
2. status 分岐:
   (a) completed → status=completed の SessionView（完了画面, US-P07/P01）。以降新規回答なし
   (b) in_progress → 【再開】§3.1 の状態再構成 → SessionView
   (c) unused → 【新規開始】§3.2 のセッション確定 → SessionView
3. touch_token(token, now)（last_active_at 更新, BR-04 鮮度維持）は開始/再開/各送信で実施
```

### 3.1 再開（in_progress, Q2=A — DB 行から毎回再構成）
- `pairs`（確定 PairSequence）・`judgments`（回答済み pair_id 集合）を読む。
- `derive_phase` で現在フェーズ、`next_unanswered_index` で次ペアを導出。
- **永続化した `SessionState` blob は使わない**（単一の真実）。`SessionState = pairs + next_index` は XC-02/PBT-02 の論理単位としてのみ存在（§6）。
- 既回答ペアは重複提示しない（導出で保証, US-P08）。

### 3.2 新規開始（unused）
```
a. exposure = repo.read_exposure_counts(now, inactive_threshold_hours)   # H-2 導出
b. pool     = repo.list_items()                                          # body 込み
c. seed     = 決定論シード生成（監査リプレイ可能な値。生成方法は Code Generation で確定）
d. pairs    = generate_pairs(pool, exposure, seed, params)               # 先頭 practice_pairs 件が練習
e. session  = Session(token, phase=practice, seed, exposure_snapshot=exposure, created_at=now)
f. repo.save_pair_sequence(session, pairs)   # Session + PairSequence を単一 batch で原子確定（DP-01）
g. repo.mark_token_in_progress(token, now)   # 一方向 unused→in_progress（BR-09）
h. SessionView を合成（phase=practice, next_pair=先頭ペア）
```
- **Likert 対象は保存しない**（Q3-b=A）: 必要時に `select_likert_targets(pool, seed, params)` で都度導出（§4）。`seed` は session に保存済みなので再現可能。

---

## 4. Likert 対象選定（Q3=X — 機構を実装・方針は後日）

`generate_pairs` は Likert 対象を返さない。新規純関数を `backend/domain/` に追加:

```
select_likert_targets(pool: list[Item], seed: int, params: AssignmentParams) -> list[str]  # item_id 列
  1. fixed = params.likert_fixed_targets or []          # プールに実在する item_id のみ採用
  2. targets = [t for t in fixed if t in pool_ids]      # 順序保持・重複排除
  3. 不足分 (params.likert_items - len(targets)) を seed 由来で層均等ランダム補充
       - 各層から round-robin で未選択項目を Random(seed) で抽選（層網羅を優先）
       - fixed と重複しない
  4. len == min(params.likert_items, len(pool)) を返す
```
- **決定論**: 同一 `(pool, seed, params)` → 同一結果（P-6）。監査リプレイ可能。
- **params 拡張**: `AssignmentParams.likert_fixed_targets: list[str] | None = None`（U1 波及, §7）。
- **方針は Negotiable**: 全固定 / 混合 / 全ランダムをプール凍結時に `likert_fixed_targets` の設定で選択。現時点は機構のみ確定（理由: 固定アンカーの選択はプールの中身を見て決めるべき）。
- **较正の設計意図（記録）**: 全ランダムだと 1 項目 3〜5 評定で項目平均が不安定＋評価者効果が項目平均に交絡。固定アンカー方式（全員同一項目）は 1 項目≈40 評定で安定し較正がクリーン。

---

## 5. 送信フロー（判定 / Likert / アンケート）

### 5.1 submit_judgment（US-P03, `POST /api/judgment`, Q6=A）
```
1. repo.get_token → 無効/completed は拒否（Q11）
2. pair = pairs から pair_id を検索（repo 経由）
     - そのトークンに属さない / 存在しない pair_id → 拒否（業務エラー封筒）
     - is_practice はこの pairs 行から判定（クライアント申告不使用, H-3）
3. choice ∈ {A,B} を検証（無回答・不正は拒否, US-P03）
4. kept = repo.insert_judgment(token, pair_id, choice, now)   # ON CONFLICT DO NOTHING + 既存 choice 返却
     - saved = (kept == choice) 初回、duplicate = 再送で既存と一致
5. touch_token(now)
6. derive_phase で更新後フェーズ・next_pair・progress を再導出
7. SubmitResult = { saved, duplicate, choice: kept, next_pair, phase, progress } を返す
```
- 練習判定も保存（Q4=A）。集計除外は下流（U3/U4b）が `pairs.is_practice` で行う。

### 5.2 submit_likert（US-P05, `POST /api/likert`, Q8=A）
```
1. トークン検証・phase 前提（likert 到達可能性）
2. target_ref が当該セッションの Likert 対象（select_likert_targets）に含まれるか検証
3. rating ∈ [1,7] 検証
4. repo.insert_likert(token, target_ref, rating, now)   # ON CONFLICT(token,target_ref) DO NOTHING
     → 初回不変（再送は既存 rating 返却。評定修正 UI なし, Q8 補足）
5. derive_phase 再導出 → 次の likert 対象 or survey へ
```

### 5.3 submit_survey（US-P06/P07, `POST /api/survey`, Q9/Q12=A）
```
1. トークン検証
2. answers は暫定 dict（必須キー存在チェック程度の緩い検証, Q9）
3. repo.upsert_survey(token, answers, now)              # PK=token で upsert（再送・修正で 1 行）
4. 完了判定（Q12=A）: 本番判定全件 ∧ Likert 全対象評定 ∧ survey 行あり を repo で確認
     → 満たせば repo.mark_token_completed(token, now)（in_progress→completed, BR-09）
     → 満たさなければ completed にしない（未完のフェーズを SessionView で返す, 順序保証）
5. SessionView（status=completed なら完了画面）を返す
```

---

## 6. XC-02 ラウンドトリップ（Q2=A, H-3 クローズ）

- **永続化は DB 行のみ**（sessions + pairs + judgments）。`SessionState`（`pairs + next_index`）は「保存前後で論理的に等価」を保証すべき**論理単位**として `serialize`/`deserialize`（既存）で扱い、PBT-02 で検証。
- 再開は毎回 DB 行から `SessionState` を再構成（`next_index = next_unanswered_index(pairs, answered_pair_ids)`）。別 blob は持たない。
- **これをもって H-3 の宿題（ラウンドトリップ対象の確定 = DB 行の復元）はクローズ**。

---

## 7. U1/U4a 公開面の利用 / 拡張

| U1/U4a 公開面 | U2 での利用 |
|---|---|
| `generate_pairs` / `AssignmentParams` | セッション新規開始のペア列生成（再実装しない）。**`likert_fixed_targets` を params に追加** |
| `read_exposure_counts`（H-2 導出） | 新規開始時の露出入力 |
| `save_pair_sequence`（DP-01） | Session+PairSequence 原子確定 |
| `insert_judgment`（DP-02, 冪等） | 判定の冪等保存 |
| `get_token`/`mark_token_in_progress`/`mark_token_completed`/`touch_token` | トークン状態管理（BR-09） |
| `list_items`（body 込み, U4a） | ペア本文の表示データ |
| `serialize`/`deserialize`/`next_unanswered_index` | XC-02 論理単位・再開位置導出 |
| `Item.body`（U4a 格納） | 参加者 UI の謎かけ本文表示 |
| **Repository 追加（U2）** | `insert_likert`（初回不変）/ `upsert_survey`（PK token）/ 回答済み pair_id・likert 済み ref の読み取り |

---

## 8. Testable Properties（U2 Code Generation / Build & Test で検証）

| ID | プロパティ | 対応 |
|---|---|---|
| **PU2-1（XC-02/PBT-02）** | 任意の有効セッション状態で `deserialize(serialize(SessionState)) == SessionState`（論理等価） | XC-02 / Q2 |
| **PU2-2** | 再開の非重複: 数ペア回答済みの in_progress を再構成 → `next_pair` は未回答の先頭・既回答を再提示しない | US-P08 / Q2 |
| **PU2-3** | フェーズ導出の単調性: 送信を進めるほど `derive_phase` は practice→…→done を後戻りしない（各送信で前フェーズ未完なら現行に留まる） | Q1 |
| **PU2-4** | 判定冪等: 同一 (token,pair_id) に異なる choice を再送 → 保存は初回のみ・`duplicate=true`・既存 choice 返却 | US-P03 / DP-02 |
| **PU2-5** | 練習の集計除外整合: 練習判定を保存しても `derive_exposure` の露出は本番のみ（is_practice 除外） | US-P02 / Q4 |
| **PU2-6** | `select_likert_targets` 決定論・網羅: 同一 (pool,seed,params) → 同一結果、`likert_fixed_targets` を必ず包含、可能なら層網羅、件数 = min(likert_items, |pool|) | Q3 |
| **PU2-7** | Likert 初回不変: 同一 (token,target_ref) に異なる rating 再送 → 初回値保持 | Q8 |
| **PU2-8** | 完了順序保証: 本番/Likert/Survey のいずれか未完で `submit_survey` → completed にしない | Q12 |

- 統合テストは U1/U4a と同じ実 D1 ハーネス（`tests/integration/`）を流用（`/api/*` 越しに参加者フロー一巡を検証）。

---

## 9. U1 波及の変更スコープ（明示）

1. `schema/models.py`: `AssignmentParams.likert_fixed_targets: list[str] | None = None` 追加（Q3 機構）。
2. `migrations/0003_*.sql`: `likert_responses` に `UNIQUE(token, target_ref)` 追加（Q8）。
3. `backend/repo/repository.py`: `insert_likert`（ON CONFLICT DO NOTHING + 既存 rating 返却）・`upsert_survey`（PK token）・回答済み集合/Likert 済み ref の読み取りメソッド追加。
4. 関連テスト更新（`AssignmentParams` 追加フィールド・migration 0003）。

## 10. 後続への申し送り
- **U3**: 進捗モニタリング（発行/開始/完了・総回答数）・暫定勝率は `judgments`（練習除外）・`tokens` を集計。エクスポートは Likert/Survey/Judgment を schema/ 準拠で出力。
- **U4b**: エクスポート（U3）を入力に BT 集計。Likert を較正アンカーに使用。
- **プール凍結時（研究者運用）**: `likert_fixed_targets` の方針（全固定/混合/全ランダム）と Likert 設問文言・アンケート設問を確定。
