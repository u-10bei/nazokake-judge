# U1 Domain Entities — 共有基盤

**スコープ**: 技術非依存のドメインモデル。永続化の具体（D1 の型・DDL）は Infrastructure Design / Code Generation。
**関連**: XC-01（割当）, XC-02（状態）, US-R06（層ラベル）, 追加規則 1/2。

---

## エンティティ

### Item（作品）
| 属性 | 型 | 説明 |
|---|---|---|
| `item_id` | ID | 一意 |
| `layer` | enum(pro/ai/edit/rule) | **必須**（US-R06、XC-01 層間比率の前提） |
| `body_ref` | ref | 作品本文への参照（本文はリポジトリ管理外, NFR-08） |

### Token（参加者トークン）
| 属性 | 型 | 説明 |
|---|---|---|
| `token` | 推測困難文字列 | US-R05 で発行（XC-03 エントロピー） |
| `status` | enum(unused/in_progress/completed) | 状態遷移は BR-09 |
| `issued_at` | timestamp | 発行時刻 |
| `last_active_at` | timestamp | 最終操作時刻（非アクティブ判定 BR-04 に使用） |

### Session
| 属性 | 型 | 説明 |
|---|---|---|
| `token` | FK(Token) | 1:1 |
| `phase` | enum(instruction/practice/judging/likert/survey/done) | 進行段階 |
| `seed` | int | **サーバ生成・保存**（Q4=B, 監査・完全リプレイ用） |
| `exposure_snapshot` | map(item_id→count) | 割当時に参照した露出カウントのスナップショット（Q4=B, リプレイ用） |
| `created_at` | timestamp | |

- **XC-02 ラウンドトリップ対象**: 「Session の進捗を復元するのに必要な状態」= 確定済み PairSequence + 既回答から導出できる再開位置。`seed`/`exposure_snapshot` は監査用の付随情報でラウンドトリップの必須対象ではない（H-3 で確定した対象定義に沿う）。

### PairSequence / Pair
セッション開始時に確定保存される順序付きペア列（Q3=A の一括生成）。
| Pair 属性 | 型 | 説明 |
|---|---|---|
| `pair_id` | ID | セッション内一意 |
| `index` | int | セッション内の提示順 |
| `item_left` | FK(Item) | **A（先/上）に提示する作品** |
| `item_right` | FK(Item) | **B（後/下）に提示する作品** |
| `is_practice` | bool | 練習試行か（**サーバが index/構成から決定**, H-3。クライアント申告に依存しない） |

- **追加規則 2（位置カウンターバランス）**: `item_left`/`item_right` は割当時に**一様ランダムで順序決定・記録**する。判定の `choice`（A/B）は「left/right のどちらを選んだか」を意味し、分析側は `item_left`/`item_right` から位置効果を検証できる。

### Judgment（ペア判定）
| 属性 | 型 | 説明 |
|---|---|---|
| `token` | FK | |
| `pair_id` | FK | |
| `choice` | enum(A/B) | A=item_left, B=item_right |
| `created_at` | timestamp | |
- **冪等性**: (`token`,`pair_id`) 一意（BR-08）。練習試行は集計対象外。

### LikertResponse
| `token`, `target_ref`（作品/項目）, `rating`(int), `created_at` | BT 較正アンカーとして区別保存（US-P05, FR-06） |

### SurveyResponse
| `token`, `answers`(構造), `created_at` | 事後アンケート。設問はプール確定後に確定（暫定構造） |

### ExposureCounts（導出値・非永続）
- **保持しない**（H-2 導出方式, Q5=A）。`item_id → 露出回数` を、確定済み PairSequence（**非アクティブ in_progress を除外**, BR-04）から集計して算出。

---

## 関係（ER 概要）

```
Item 1---* Pair(left/right)      （1 作品は多数のペアに出現）
Token 1---1 Session
Session 1---* Pair (PairSequence, 順序)
Token 1---* Judgment            （pair ごとに高々 1, 冪等）
Token 1---* LikertResponse
Token 1---1 SurveyResponse
ExposureCounts = derive(全確定 PairSequence − 非アクティブ)   （導出）
```

## 申し送り（後続ユニットへ）
- **位置情報の波及**: `item_left`/`item_right`（Pair）と `choice` の意味を、**US-R02 エクスポート形式（U3）・schema/（U1 の Pydantic モデル）・US-R04 BT 集計（U4b）**に反映する。エクスポートに位置情報を含め、分析側で位置効果を検証可能にする（追加規則 2）。→ U3/U4 の Functional Design で拾う。
