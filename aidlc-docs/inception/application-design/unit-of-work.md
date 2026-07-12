# Unit of Work — nazokake-judge

**分解方針**: 4 ユニット（論理モジュール、単一デプロイ）。bounded context に沿う。
**実装順序**: **U1 → U4a → U2 → U3 → U4b**（下記）。
**結合**: 同一コードベース内の直接 import。**層の逆流禁止**（U1 への一方向依存。上位は U1 の公開インターフェース＝schema/ の Pydantic モデル、Repository / AssignmentEngine の公開関数のみを import）。

---

## U1: 共有基盤 (foundation)
- **責務**: 全ユニットが依存するデータ契約と土台ロジック。
- **含むコンポーネント**: C-SCHEMA（Pydantic モデル + D1 DDL + エクスポート形式バージョン）、C-REPO（D1 Repository）、C-DOM-ASSIGN（AssignmentEngine, XC-01・純粋関数）。
- **公開インターフェース**: Pydantic モデル群、Repository の公開メソッド、`generate_pairs` / `updated_exposure`。
- **重点**: XC-01（露出均衡・層間比率, PBT-03）、XC-02（状態ラウンドトリップ, PBT-02）、SQLi 対策（XC-03）。
- **コード配置**: `schema/`（Pydantic + DDL）, `backend/domain/`（AssignmentEngine）, `backend/repo/`（Repository）。

## U2: 参加者セッション (participant)
- **責務**: 評価者の線形ウィザード（アクセス→教示→練習→判定→Likert→アンケート→完了/再開）。
- **含むコンポーネント**: C-FE-PART, C-SVC-SESSION, C-SVC-RESPONSE, C-SVC-SURVEY, C-API（参加者系エンドポイント）。
- **依存**: U1（Repository, AssignmentEngine, モデル）。
- **重点**: US-P01〜P08、XC-04（モバイル/日本語）、判定送信の冪等性（US-P03）、再開（US-P08）。
- **コード配置**: `frontend/`（参加者 UI）, `backend/participant/`。

## U3: 研究者・管理 (admin)
- **責務**: 進捗モニタリング・暫定勝率表示・エクスポート（Basic 認証背後）。
- **含むコンポーネント**: C-FE-ADMIN, C-SVC-ADMIN, C-SVC-EXPORT, C-AUTH, C-API（管理系エンドポイント）。
- **依存**: U1（Repository, モデル）。
- **重点**: US-R01/R02/R03、XC-03（Basic 認証・CORS）、エクスポート形式＝schema/ 準拠（US-R04 と一致）。
- **コード配置**: `frontend/`（管理 UI）, `backend/admin/`。

## U4: 運用スクリプト (ops-scripts)
- **責務**: トークン発行・プール投入・BT 集計。**実装上 2 段階に分割**。
  - **U4a（先行）**: `token_issue`（US-R05）, `pool_ingest`（US-R06, 層ラベル必須）。U2 の動作確認に必要なテストデータを供給。**H-1（scripts→D1 接続方式）をここで早期検証**。
  - **U4b（最後）**: `bt_aggregate`（US-R04）。U3 のエクスポート（schema/ 準拠）を入力に取るため全参加フロー完成後。
- **依存**: U1（モデル, 接続方式は H-1 で確定）、U4b は U3 のエクスポート形式に依存。
- **コード配置**: `scripts/`。

---

## 実装順序と根拠

```
U1 (基盤)
  → U4a (pool_ingest / token_issue)   … テストデータ供給 + H-1 早期検証
    → U2 (参加者セッション)
      → U3 (研究者・管理)
        → U4b (bt_aggregate)          … エクスポート(U3)が入力のため最後
```

- U1 を最初に：割当ロジックとデータ契約が全上位の前提。
- U4a を U2 の前に：pool_ingest がなければ U2 の判定フローを実データで確認できない。token_issue がなければアクセス（US-P01）を試せない。
- U4b を最後に：入力が U3 のエクスポートであり、参加フローが一巡してから。

## コード組織戦略（Greenfield）

```
nazokake-judge/
├── frontend/            # 静的 HTML/JS（U2 参加者 UI, U3 管理 UI）
├── backend/             # Python Worker/FastAPI
│   ├── domain/          #   AssignmentEngine（U1, 純粋）
│   ├── repo/            #   D1 Repository（U1）
│   ├── participant/     #   Session/Response/Survey + 参加者 API（U2）
│   └── admin/           #   Admin/Export + Auth + 管理 API（U3）
├── schema/              # Pydantic モデル + D1 DDL(.sql) + 形式バージョン（U1・共有）
├── scripts/             # token_issue / pool_ingest / bt_aggregate（U4）
└── tests/
    ├── unit/{u1,u2,u3,u4}/   # example-based（ユニット別）
    └── pbt/                  # Hypothesis（受入基準対応を name/docstring に明記）
```

- **schema/ の解決性**: backend も scripts も schema/ を import するため、両者から解決可能なインポートパスに置く（`pyproject.toml` の packages 設定で対応。詳細は Code Generation）。
- **層の逆流禁止**: `backend/participant`・`backend/admin`・`scripts` は `backend/domain`・`backend/repo`・`schema` に依存してよいが、逆（U1 が上位に依存）は禁止。

## テスト配置規約（Q5）

- `tests/unit/{u1..u4}/`: 各ユニットの example-based テスト。
- `tests/pbt/`: Hypothesis による PBT。各プロパティテストは対応する受入基準（例: XC-01 露出均衡、XC-02 ラウンドトリップ）を**テスト名・docstring に明記**（PBT-10 相補性・重点箇所追跡）。
