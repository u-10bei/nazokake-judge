# U1 Logical Components — 共有基盤 (foundation)

**ユニット**: U1（C-SCHEMA / C-REPO / C-DOM-ASSIGN）
**方針**: U1 の論理コンポーネントは最小限。Resilience/Scalability が N/A のため、**queue / cache / circuit breaker 等の専用インフラ論理部品は導入しない**（Q5 適用性評価に同意）。U1 の部品は「純粋関数境界／唯一の I/O 境界／データ契約／ログヘルパ」に限る。

---

## 論理コンポーネント一覧

### LC-01: DataContract（`schema/`）— C-SCHEMA
- **役割**: 全ユニット共有のデータ契約。Pydantic モデル群 + D1 DDL(.sql) + エクスポート形式バージョン + トークン契約（DP-05）。
- **公開面（狭い）**: **モデル型 + 明示バリデート関数**のみ（DP-07）。実装（Pydantic v2 or フォールバック）は内部に隠蔽。
- **DDL に含む制約**: `Judgment` (`token`,`pair_id`) 一意（DP-02）、`Item.layer` NOT NULL（BR-11）、トークン長/文字集合（DP-05）。
- **依存**: なし（最下層）。

### LC-02: AssignmentEngine（`backend/domain/`）— C-DOM-ASSIGN
- **役割**: XC-01 の割当・純粋関数群。`generate_pairs` / `updated_exposure`。副作用なし（DB I/O を持たない）。
- **性質**: 決定論（同一 `(pool,exposure,seed,params)` → 同一出力, P-6）。テスト対象の中核（DP-08）。
- **依存**: LC-01（モデル型）のみ。

### LC-03: Repository（`backend/repo/`）— C-REPO
- **役割**: **唯一の I/O 境界**。D1 への読み書きを集約。
- **主メソッド（論理）**:
  - `save_session_bootstrap(...)`: Session + PairSequence + `exposure_snapshot` を**単一 batch で原子確定**（DP-01）。
  - `derive_exposure(...)`: 確定 PairSequence から集計、非アクティブ除外（DP-03）。
  - `upsert_judgment(...)`: `ON CONFLICT DO NOTHING` + 既存 `choice` 返却（DP-02）。
  - その他 CRUD はすべて**パラメータ化クエリ**（DP-04）。
- **依存**: LC-01（モデル）、LC-05（ログ）。D1 接続方式は Infrastructure Design（H-1）で確定。

### LC-04: SessionState Serializer（`backend/domain/` 内 or `schema/` 隣接）
- **役割**: XC-02 の状態シリアライズ。`serialize` / `deserialize`（確定 PairSequence + 再開位置）。ラウンドトリップ（PBT-02, P-4）の対象。
- **依存**: LC-01（モデル）。純粋（I/O は Repository 経由）。

### LC-05: LogEmitter（横断ユーティリティ）
- **役割**: 構造化ログの単一発行点 `emit(event, level, **fields)`（DP-06）。JSON を stdout。相関キー `session_id`/`token`。
- **依存**: なし（横断）。監視基盤・集約先は持たない（NFR-06）。

---

## 依存方向（層の逆流禁止）

```
             ┌────────────────────────────┐
上位ユニット  │ U2 participant / U3 admin / │
（U2/U3/U4）  │ U4 scripts                 │
             └─────────────┬──────────────┘
                           │ import（公開面のみ）
              ┌────────────▼─────────────┐
              │ LC-03 Repository (I/O 境界) │───► LC-05 LogEmitter
              │ LC-02 AssignmentEngine     │
              │ LC-04 SessionState Serializer│
              └────────────┬─────────────┘
                           │ import
                  ┌────────▼────────┐
                  │ LC-01 DataContract │  ← 最下層（依存なし）
                  │   (schema/)        │
                  └──────────────────┘
```

- **一方向依存**: 上位は U1 の**公開インターフェース**（LC-01 の狭い公開面、LC-02 の `generate_pairs`/`updated_exposure`、LC-03 の公開メソッド）のみ import。**U1 から上位への依存は禁止**（U1-NFR-15）。
- LC-02 / LC-04 は純粋（副作用なし）。副作用（D1 I/O）は LC-03 に集約。ログ（LC-05）は横断。

---

## 導入しない論理部品（意図的な非採用）

| 部品 | 非採用理由 |
|---|---|
| メッセージキュー | 非同期処理・バックプレッシャ要件なし（同期・小規模）。 |
| キャッシュ層 | `derive_exposure` は毎回集計で瞬時（U1-NFR-02）。キャッシュは整合リスクのみ増やす。 |
| サーキットブレーカ / リトライ | 外部依存の連鎖なし、Resilience = N/A（NFR-06）。 |
| 分散ロック | 同時開始のスナップショット競合は許容（Q8=A）。ロックは規模に対し過剰。 |

---

## 後続への申し送り
- **Infrastructure Design**: LC-03 の D1 接続方式（H-1）、`save_session_bootstrap` の D1 batch 具体 API、LC-01 の Pydantic 可用性検証（TSD-02）。
- **Code Generation**: LC-05 のフィールド規約、DP-08 ハーネスと `α`/`S` 較正ループの共有実装、`pyproject.toml` の packages 解決（`schema/` の import パス）。
