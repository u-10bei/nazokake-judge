# U3 Business Logic Model — 研究者・管理（admin）

**ユニット**: U3。管理エンドポイント（`/admin/*` に追加）＋ AdminService / ExportService（`src/backend/admin/`）＋ 管理 UI（Worker 埋め込み配信）＋ Repository の集計読み取り拡張で構成。**既存の Basic 認証チョークポイント（DP-U4a-01）を再利用**し、参加者データを研究者向けに集計・出力する。

**設計原理**: 集計 SQL は Repository に集約（I/O 境界一貫・パラメータ化クエリ, XC-03）、AdminService/ExportService は Repository 結果を**ビュー/バンドル型へ整形する薄い層**（Q6=A）。**練習は集計・出力から常に除外**（本番のみ, US-P02）。

---

## 1. 構成要素（責務境界）

| 要素 | 配置 | 役割 | 新規/拡張 |
|---|---|---|---|
| 管理エンドポイント | `src/backend/admin/api.py`（`handle_admin` 拡張） | `GET /admin/`（UI）・`/admin/progress`・`/admin/winrates`・`/admin/export` | 拡張（U3） |
| AdminService | `src/backend/admin/` | 進捗（ProgressView）・暫定勝率（WinrateRow[]）の整形 | 新規（U3） |
| ExportService | `src/backend/admin/` | ExportBundle 組立・形式版付与・CSV 直列化 | 新規（U3） |
| 管理 UI | `src/backend/admin/`（埋め込み HTML/JS） | 進捗 + 暫定勝率 + エクスポート。**Worker が返す**（assets 非配置, BR-U3-02） | 新規（U3） |
| AuthGuard（再利用） | `src/backend/admin/auth.py` | Basic 認証チョークポイント（DP-U4a-01） | 再利用（U4a） |
| AdminLog（再利用） | `src/backend/admin/log.py` | 秘匿ログ | 再利用（U4a） |
| Repository 集計拡張 | `src/backend/repo/repository.py` | 進捗カウント・勝率集計・エクスポート join の読み取り | U1 拡張（U3） |

- **依存方向**: ブラウザ →(HTTPS+Basic)→ `handle_admin`（AuthGuard）→ AdminService/ExportService → Repository → D1。層の逆流禁止。
- 管理系は raw workers API + `handle_admin` 内の手動ディスパッチ（F-5）。認証は `/admin/*` 一本（DP-U4a-01）。

---

## 2. 進捗モニタリング（US-R01, `GET /admin/progress`）

```
1. AuthGuard（Basic, 401 で弾く）
2. Repository.progress_counts() で集計:
     tokens_issued    = COUNT(tokens)
     tokens_started   = COUNT(tokens WHERE status IN ('in_progress','completed'))
     tokens_completed = COUNT(tokens WHERE status='completed')
     judgments_total  = COUNT(judgments j JOIN pairs p USING(token,pair_id) WHERE p.is_practice=0)  ← 本番のみ
     likert_total     = COUNT(likert_responses)
     survey_total     = COUNT(survey_responses)
3. AdminService が ProgressView に整形して返す（JSON）
```
- **本番のみ**の判定数（練習除外）で進捗の意味を一貫させる（BR-U3-04）。

## 3. 暫定勝率テーブル（US-R03, `GET /admin/winrates`）

```
1. AuthGuard
2. Repository.provisional_winrates() で単一集計:
     本番判定（is_practice=0）を pairs と join し、item ごとに
       matches = 出現した本番比較数（item_left か item_right に現れた回数）
       wins    = 選ばれた回数（choice=A→item_left の勝ち / choice=B→item_right の勝ち）
       winrate = wins / matches （matches=0 は winrate=0）
     item の layer を付与
3. AdminService が WinrateRow[] に整形（layer・matches 降順等の並びは UI 側）
```
- **非 BT の簡易表示**である旨を UI に明示（US-R03 / BR-U3-05）。**軽量な単一集計**（US-R03「実装は軽量」）。

## 4. エクスポート（US-R02, `GET /admin/export`）

```
1. AuthGuard
2. format=json（既定・U4b 正本）:
     Repository.export_rows() で 4 セクションを収集:
       items     = SELECT item_id, layer FROM items
       judgments = 本番のみ（is_practice=0）: token, pair_id, pairs.idx AS pair_index,
                   item_left, item_right, choice, created_at
       likert    = token, target_ref, rating, created_at
       surveys   = token, answers(JSON), created_at
     ExportService が ExportBundle{ schema_version=EXPORT_FORMAT_VERSION,
       exported_at=now, items, judgments, likert, surveys } を組み、JSON を返す
       （Content-Disposition: attachment; filename=export-<ts>.json）
   format=csv&entity=<judgments|likert|surveys|items>:
     当該セクションのみを CSV 直列化して返す（目視用途, BR-U3-06）
3. **練習は SQL で除外**（出力段保証・U4b にフィルタ責務を残さない, BR-U3-03）
```
- `schema_version`=1.0.0 を付与し、US-R04（U4b）入力契約を固定（BR-U3-07）。**items で U4b が層情報を自己完結取得**（投入 JSON を第二入力にしない）。**body は非格納**（未公表刺激, NFR-08）。

---

## 5. Testable Properties（U3 Code Generation / Build & Test で検証）

| ID | プロパティ | 対応 |
|---|---|---|
| **PU3-1** | 練習除外の出力段保証: 練習判定を含むデータで export → **judgments に is_practice 由来の行が 1 件も混入しない**（本番のみ） | BR-U3-03 / US-P02 |
| **PU3-2** | winrate 定義整合: `provisional_winrates` の matches/wins が judgments×pairs の実 join と一致、`winrate=wins/matches`（matches>0） | BR-U3-05 |
| **PU3-3** | ExportBundle 自己完結: judgments に現れる全 item_id が items セクションに存在（U4b が層を解決可能） | Q1 / BR-U3-07 |
| **PU3-4** | 進捗カウント整合: tokens_issued≥started≥completed、judgments_total は本番のみ | BR-U3-04 |
| **PU3-5** | 認証境界: Basic 認証なし/誤りで `/admin/progress`・`/winrates`・`/export`・`/`（UI）すべて 401 | BR-U3-01 / XC-03 |

- 純粋な整形（CSV 直列化・ProgressView/WinrateRow 変換・ExportBundle 組立）は example ベース単体テスト、D1 集計は integration（実 D1・`/admin/*` 越し）で検証（NFR で振り分け）。

---

## 6. U1/U4a 公開面の利用 / 拡張

| 公開面 | U3 での利用 |
|---|---|
| `check_basic` / `unauthorized`（auth.py） | 管理境界の再利用（新規認証を作らない） |
| `handle_admin`（api.py） | GET ルート（progress/winrates/export/UI）を追加ディスパッチ |
| `admin_log`（log.py） | 集計・エクスポート操作の秘匿ログ（トークン・本文非出力） |
| `EXPORT_FORMAT_VERSION` | ExportBundle の schema_version |
| Repository（+ 集計読み取り追加） | progress_counts / provisional_winrates / export_rows |
| schema（+ ビュー/バンドル型追加） | ProgressView / WinrateRow / ExportBundle |

---

## 7. U4b への申し送り（重要）
- **ExportBundle（domain-entities 正本）が BT 集計（US-R04）の入力仕様**。U4b はこれを**変換なしで**読み込む。
- **契約変更は `schema_version` の版上げを伴う**（形式を変えたら `EXPORT_FORMAT_VERSION` を上げ、影響を明記）。
- 練習は既に除外済み・items で層解決可能・pair_index で順序効果分析可能・item_left/right+choice で位置バイアス分析可能。U4b はフィルタ/結合の追加責務を持たない。
