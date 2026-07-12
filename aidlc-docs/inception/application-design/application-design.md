# Application Design（統合） — nazokake-judge

**作成日**: 2026-07-12
**フェーズ**: INCEPTION / Application Design
**関連**: [components.md](./components.md) / [component-methods.md](./component-methods.md) / [services.md](./services.md) / [component-dependency.md](./component-dependency.md)

---

## 1. アーキテクチャ決定（案 A′）

**採用**: 静的フロント（バニラ JS） + **Cloudflare Python Workers（FastAPI）** + **D1**。PBT は **Hypothesis**。

**決定理由**:
- 案 A の骨格（Workers + D1、HTTPS 標準、無料枠、SQLite 互換）を維持しつつ実装言語を Python に統一。
- 割当ロジック・エクスポート・BT 集計・投入/発行がすべて Python となり、**データ契約を Pydantic モデルで単一定義・共有**できる（Q6=A）。
- PBT の Hypothesis は PBT-07（ジェネレータ）/PBT-08（縮小・シード再現）を標準機能でほぼ充足（requirements §6 の Python→Hypothesis と整合）。

**フォールバック**: 案 B（PHP + SQLite / Xserver）を温存。

## 2. 設計上のリスクと緩和（要 追跡）

| リスク | 内容 | 緩和策 | 追跡先 |
|---|---|---|---|
| **R-1: Python Workers の beta** | Python Workers は open beta（`python_workers` flag 必須）。FastAPI/ASGI・依存パッケージの互換性に不確実性。 | 規模小で TS 書換コスト限定。FastAPI+SQLite は Workers 外（VPS/PaaS）へほぼ無改修移設可。 | **Infrastructure Design / NFR Requirements で互換性を実地検証** |
| R-2: D1 の制約 | トランザクション/機能面の制約可能性。 | 小規模・単純スキーマで回避。Repository に I/O を集約し差し替え可能に。 | Infrastructure Design |
| R-3: 割当の研究妥当性 | 割当の偏りが BT 推定を汚染（XC-01）。 | 純粋関数化 + PBT-03 重点検証、露出カウント入力設計。 | Functional Design / Code Generation |

## 3. コンポーネント構成（レイヤ）

- **Frontend（静的・バニラ JS）**: C-FE-PART（参加者ウィザード）, C-FE-ADMIN（管理閲覧）
- **Backend（Python Worker/FastAPI）**: C-API, C-AUTH, C-SVC-SESSION, C-SVC-RESPONSE, C-SVC-SURVEY, C-SVC-ADMIN, C-SVC-EXPORT
- **Domain（純粋）**: C-DOM-ASSIGN（AssignmentEngine, XC-01）
- **Data/Shared**: C-REPO（D1 Repository）, C-SCHEMA（schema/）
- **Scripts（Python）**: token_issue（US-R05）, pool_ingest（US-R06）, bt_aggregate（US-R04）

詳細は [components.md](./components.md)。

## 4. 主要な設計判断（Application Design Q&A の反映）

| # | 判断 | 反映 |
|---|---|---|
| Q1 | 案 A′（Python Workers + D1, Hypothesis） | §1, 全体 |
| Q2 | フロントはバニラ JS（SSR 併用は Functional Design で画面別判断） | C-FE-PART |
| Q3 | **セッション開始時に割当を一括生成し DB 保存**（露出カウント読取→純粋関数→保存） | C-SVC-SESSION, C-DOM-ASSIGN |
| Q4 | サーバ DB 単一の真実 | 全 Service, C-REPO |
| Q5 | 管理/エクスポートは Basic 認証（wrangler secret） | C-AUTH |
| Q6 | schema/ 単一仕様 + Pydantic 共有 + 形式バージョン | C-SCHEMA, C-SVC-EXPORT |

## 5. 横断制約の設計への織り込み

- **XC-01（割当）**: AssignmentEngine を純粋関数 `(pool, exposure, seed, size) → pairs` として分離。DB I/O は SessionService/Repository。露出均衡は全セッション横断の不変条件、層ラベルを入力に。→ PBT-03。
- **XC-02（状態ラウンドトリップ）**: セッション状態は DB を権威とし、確定ペア列の保存/復元でラウンドトリップ性を担保。→ PBT-02。
- **XC-03（セキュリティ衛生）**: HTTPS（Workers 標準）、トークン推測困難性（token_issue）、パラメータ化クエリ（C-REPO）、CORS（C-API）。
- **XC-04（モバイル/日本語）**: C-FE-PART をモバイルファースト・日本語のみで実装。

## 6. 想定ディレクトリ構成（コード配置の目安 / Units・Code Generation で確定）

```
nazokake-judge/
├── frontend/        # 静的 HTML/JS（C-FE-PART, C-FE-ADMIN）
├── backend/         # Python Worker/FastAPI（C-API, C-AUTH, C-SVC-*）
│   └── domain/      #   AssignmentEngine（C-DOM-ASSIGN, 純粋）
├── schema/          # Pydantic モデル + D1 DDL + 形式バージョン（C-SCHEMA）
├── scripts/         # token_issue / pool_ingest / bt_aggregate（Python）
└── tests/           # PBT(Hypothesis) + example-based
```
（`aidlc-docs/` は文書のみ。アプリコードはワークスペース直下。）

## 7. トレーサビリティ要約
- 要件 FR-01〜10 / NFR-01〜09、ストーリー US-P01〜08 / US-R01〜06 / XC-01〜04 を各コンポーネントにマップ（[component-dependency.md](./component-dependency.md) 参照）。
- 未確定（後続で確定）: Likert/アンケート設問（プール確定後）、露出均衡の許容範囲・層間比率の具体値（Functional Design）、Python Workers 互換性（Infrastructure/NFR）。
