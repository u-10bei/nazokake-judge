# Services — nazokake-judge

サービス層のオーケストレーションと境界。バックエンド（Python Worker/FastAPI）に配置。各サービスは C-REPO 経由でのみ永続化にアクセスし、C-DOM-ASSIGN（純粋ロジック）を必要時に呼ぶ。

---

## サービス定義

### SessionService（C-SVC-SESSION）
- **責務**: セッションのライフサイクル。トークン状態に応じた開始/再開/完了。
- **オーケストレーション（セッション開始, US-P01+Q3=A）**:
  1. C-REPO `get_token` でトークン検証・状態判定。
  2. 未使用なら C-REPO `read_exposure_counts` → C-DOM-ASSIGN `generate_pairs(pool, exposure, seed, size)` → C-REPO `save_pair_sequence` でペア列確定・保存 →（露出カウント更新の反映方針は Functional Design で確定。**H-2**）。

> **H-2（Functional Design で確定・推奨あり）**: `read_exposure_counts` の実現には「専用カウンタテーブルを持つ」案と「`save_pair_sequence` 済みデータから毎回集計導出する」案がある。前者は更新漏れ・二重更新でペア列と乖離するリスクを持つ。後者は単一の真実（Q4=A）が露出カウントにもそのまま及び、本規模では導出コストが無視できるため**導出方式を推奨**。`AssignmentEngine.updated_exposure` 純粋関数は PBT のモデルとして残す（本番が導出方式でも無駄にならない）。詳細は application-design.md §8。
  3. `SessionView`（次ペア・進捗・フェーズ）を返す。
- **再開（US-P08）**: 保存済みペア列の未回答先頭を次ペアとして返す（DB が単一の真実）。

### ResponseService（C-SVC-RESPONSE）
- **責務**: ペア判定の冪等保存（US-P03）。
- **オーケストレーション**: C-REPO `insert_judgment`（重複検知）→ 次ペア算出。練習試行は集計対象外フラグで保存または破棄。

### SurveyService（C-SVC-SURVEY）
- **責務**: Likert（US-P05）・事後アンケート（US-P06）の保存。BT 較正アンカーとして Likert を区別。

### AdminService（C-SVC-ADMIN）
- **責務**: 進捗（US-R01）・暫定勝率（US-R03）。読取専用集計。AuthMiddleware の背後。

### ExportService（C-SVC-EXPORT）
- **責務**: schema/ 準拠のエクスポート（US-R02）。US-R04 と同一形式。AuthMiddleware の背後。

---

## オーケストレーション: 代表フロー

**参加者の 1 ペア判定**
```
Participant UI --submit--> C-API --> Auth: none --> ResponseService
   --> C-REPO.insert_judgment (冪等) --> SessionService.get_state --> next_pair
   --> C-API --> Participant UI (次ペア描画)
```

**セッション開始（割当確定）**
```
Participant UI --start(token)--> C-API --> SessionService.start_or_resume
   --> C-REPO.get_token / read_exposure_counts
   --> AssignmentEngine.generate_pairs (純粋)
   --> C-REPO.save_pair_sequence --> SessionView
```

**研究者エクスポート → BT 集計（装置の一巡の後半）**
```
Admin UI --export--> C-API --> AuthMiddleware(Basic) --> ExportService
   --> C-REPO(read) --> ExportBundle(schema/ 準拠, versioned)
（オフライン）scripts/bt_aggregate(ExportBundle) --> BTResult
```

---

## サービス境界の原則
- **純粋/副作用の分離**: 割当計算（AssignmentEngine）は純粋、DB I/O は Repository、両者を Service が接続（Q3=A の「テスト対象＝本番パス」を担保）。
- **単一の真実**: セッション状態・回答はサーバ DB が権威（Q4=A）。
- **データ契約の共有**: エクスポート/集計/投入は schema/ の Pydantic モデルを共有（Q6=A）。
- **認証境界**: 参加者 API は無認証（トークンで識別）、管理/エクスポートは Basic 認証（Q5=B）。
