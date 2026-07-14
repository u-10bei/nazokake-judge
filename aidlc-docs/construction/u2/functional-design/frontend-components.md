# U2 Frontend Components — 参加者ウィザード UI（C-FE-PART）

**ユニット**: U2 フロント（`frontend/`）。**単一 HTML + バニラ JS の SPA ウィザード**（フレームワーク不使用・静的配信, Q10=A）。**状態はサーバ権威**（各遷移で SessionView を取得して描画）、クライアントは **localStorage にトークンのみ**保持。**モバイルファースト・A/B 縦積み・日本語のみ**（XC-04）。配信方法（Worker 静的返却 / Pages 併用）は Infrastructure Design で確定。本文書は UI 論理（階層・状態・操作フロー・検証・API 結合点）に集中する。

---

## 1. コンポーネント階層（画面＝フェーズ）

```
App（ルート・ルーティングはフェーズ駆動）
├─ TokenGate            … URL/localStorage のトークン解決・GET /api/session
├─ ErrorScreen          … 無効トークン（判定へ進めない, BR-U2-26/29）
├─ InstructionScreen    … 教示（UI 前置。phase=practice ∧ 練習判定 0 件, BR-U2-02）
├─ PracticeScreen  ─┐
├─ JudgingScreen   ─┴→ PairCompare（判定 UI の共通部品。練習/本番で同一・帯だけ変える）
│                       ├─ ItemCard(left=A/上)
│                       ├─ ItemCard(right=B/下)
│                       ├─ ChoiceButtons(A / B)
│                       └─ ProgressBar（本番のみ, BR-U2-13）
├─ LikertScreen         … LikertTargetView を 1 件ずつ・7 段階尺度
├─ SurveyScreen         … 事後アンケート（暫定設問 (i)〜(iv)）
├─ DoneScreen           … 完了（BR-U2-24/25）
└─ (共通) Toast/Retry    … 送信中/失敗/再試行の非ブロッキング表示
```

- **1 画面 = 1 フェーズ**。表示するフェーズは **SessionView.phase** が決める（クライアントは phase を判断しない＝サーバ権威, BR-U2-01/03）。
- `PracticeScreen`/`JudgingScreen` は `PairCompare` を共有し、練習は上部に「練習中（集計されません）」の帯を出す（BR-U2-09 の意図を明示）。

---

## 2. 状態管理（サーバ権威・薄いクライアント）

| 状態 | 置き場所 | 備考 |
|---|---|---|
| `token` | **localStorage** のみ | URL クエリから取得し保存（URL 消失時の再開補助, Q10）。クライアントが持つ唯一の永続状態 |
| `sessionView` | メモリ（描画のたびに更新） | 各 API 応答（SessionView / SubmitResult）で置換。**フェーズ・次ペア・進捗の真実はここ** |
| 選択中の choice / rating | コンポーネント一時状態 | 送信で確定・送信後に破棄 |
| 送信中フラグ | コンポーネント一時状態 | 二重送信抑止（ボタン無効化） |

- **クライアントはフェーズ遷移を自前で進めない**。送信 → レスポンスの SessionView.phase に従って再描画するだけ（順序外・フェーズ外はサーバが現行 phase を返し UI 再同期, BR-U2-03/29）。
- 判定・Likert・アンケートの本文/対象は SessionView が運ぶ（クライアントはプールを保持しない＝出自秘匿, domain-entities §4）。

---

## 3. ユーザー操作フロー（US-P01〜P08）

```
起動: URL の ?token= を localStorage へ → GET /api/session
  ├ status=completed         → DoneScreen（再アクセス, BR-U2-25）
  ├ 無効/取得失敗             → ErrorScreen（BR-U2-26）
  └ status=in_progress/開始   → SessionView.phase で分岐:
       practice ∧ 練習 0 件   → InstructionScreen →（「練習を始める」）→ PracticeScreen
       practice（練習途中）    → PracticeScreen（再開時は教示スキップ可）
       judging                → JudgingScreen
       likert                 → LikertScreen
       survey                 → SurveyScreen
       done                   → DoneScreen

PracticeScreen/JudgingScreen（PairCompare）:
  A または B を選択（選択必須, BR-U2-12）→「送信」→ POST /api/judgment
    → SubmitResult.next_pair があれば次ペア描画 / なければ phase 更新で次画面
    → 送信失敗はクライアント再試行（サーバ冪等で二重登録なし, BR-U2-11/29）

LikertScreen:
  next_likert の本文を表示 → 1〜7 を選択 → POST /api/likert
    → 初回不変（再送は既存 rating, BR-U2-17）→ 次対象 or survey へ

SurveyScreen:
  暫定設問 (i)〜(iv) を入力 →「完了」→ POST /api/survey
    → サーバが全揃い確認 → completed → DoneScreen（BR-U2-24）
```

---

## 4. フォーム検証（クライアント側・サーバが最終権威）

| 画面 | 検証 | 対応ルール |
|---|---|---|
| PairCompare | A/B いずれか選択するまで「送信」無効（無回答送信防止） | BR-U2-12 / US-P03 |
| LikertScreen | 1〜7 のいずれか選択するまで送信無効 | BR-U2-18 |
| SurveyScreen | 暫定必須設問（(i)〜(iv)）の未入力は送信抑止（緩い・サーバも必須キー確認） | BR-U2-20 |
| 全画面 | 送信中はボタン無効化（二重送信抑止）、失敗時は再試行ボタン | BR-U2-29 |

- クライアント検証は UX 目的。**最終判定はサーバ**（choice/rating 範囲・pair 帰属・フェーズ整合, BR-U2-11/18/24）。

---

## 5. API 結合点（どの画面がどのエンドポイントを使うか）

| 画面 / 操作 | エンドポイント | 受け取り | 送り |
|---|---|---|---|
| 起動・再開・再描画 | `GET /api/session?token=` | SessionView | token（クエリ） |
| 判定送信 | `POST /api/judgment` | SubmitResult | `{token, pair_id, choice}`（body） |
| Likert 送信 | `POST /api/likert` | SessionView（更新後） | `{token, target_ref, rating}`（body） |
| アンケート送信 | `POST /api/survey` | SessionView（更新後） | `{token, answers}`（body） |

- **トークン受け渡し**: 起動時のみクエリ（配布 URL 由来）、以降の POST は **body 渡し**で統一（BR-U2-27）。
- 全 `/api/*` 応答は `Cache-Control: no-store`（トークン露出防御, BR-U2-27）。
- 業務エラーは 200 + `{ok:false, ...}`。UI は `ok` を見て Toast/ErrorScreen を出し分け（BR-U2-29）。

---

## 6. モバイルファースト・日本語（XC-04）

| 要件 | 実装方針 |
|---|---|
| A/B 縦積みで両作品が読みやすい | `ItemCard` を縦 2 枚（モバイル）、十分な行間・フォントサイズ。作品境界を明確化（US-P03） |
| 進捗の視認性 | `ProgressBar`（本番のみ）をモバイルでも見える固定位置に（US-P04） |
| タップしやすい選択 | `ChoiceButtons` は大きめのタップ領域、選択状態を明示 |
| 日本語のみ | 全 UI 文言・教示・設問を日本語で固定（英語切替なし） |
| レスポンシブ | モバイル基準 → PC は中央寄せ最大幅。フレームワーク不使用の素の CSS |

---

## 7. 実装メモ（Code Generation への申し送り）
- フレームワーク不使用（バニラ JS）。単一 HTML + モジュール JS + CSS。ビルド不要を基本とし、配信方法は Infrastructure Design で確定。
- ルーティングはハッシュ/履歴を使わずフェーズ駆動（SessionView.phase → 画面）。リロードは `GET /api/session` で状態復元（サーバ権威なのでクライアント状態喪失に強い）。
- 出自（layer/body_ref）は API が返さない（domain-entities §4）ため、フロントは本文（`body`）のみ描画。
- 送信リトライは指数バックオフ等を軽く実装（サーバ冪等が二重登録を防ぐ前提, BR-U2-11）。
- アクセシビリティ・文言の最終調整、Likert 設問文言・アンケート設問はプール凍結時に確定（Negotiable, BR-U2-19/20）。
