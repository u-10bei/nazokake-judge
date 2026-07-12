# Unit of Work Plan — nazokake-judge

**役割**: ソフトウェアアーキテクト
**目的**: Application Design のコンポーネントを、per-unit で設計・実装する作業単位（Unit of Work）へ分解する。
**デプロイ形態**: 単一デプロイ（1 つの Cloudflare Python Worker + 静的フロント + `scripts/`）。ユニットは**独立デプロイ単位ではなく論理モジュール**。
**開発体制**: 単独開発想定。Team Alignment 系の分割制約は N/A。
**状態**: Part 1 全 5 問回答済み・承認済み（会話で受領） → Part 2 生成実行。

---

## 生成成果物

- [x] `application-design/unit-of-work.md`（ユニット定義・責務・コード配置戦略）
- [x] `application-design/unit-of-work-dependency.md`（依存マトリクス）
- [x] `application-design/unit-of-work-story-map.md`（ストーリー → ユニット対応）
- [x] ユニット境界・依存の検証、全ストーリーの割当確認

---

## 提案・確定したユニット分割

| ユニット | 含むコンポーネント | 主なストーリー |
|---|---|---|
| **U1: 共有基盤 (foundation)** | C-SCHEMA, C-REPO, C-DOM-ASSIGN（XC-01） | XC-01, XC-02, US-R06 前提 |
| **U2: 参加者セッション (participant)** | C-FE-PART, C-SVC-SESSION, C-SVC-RESPONSE, C-SVC-SURVEY, C-API（参加者系） | US-P01〜P08 |
| **U3: 研究者・管理 (admin)** | C-FE-ADMIN, C-SVC-ADMIN, C-SVC-EXPORT, C-AUTH, C-API（管理系） | US-R01, US-R02, US-R03 |
| **U4: 運用スクリプト (ops-scripts)** | C-SCRIPT-TOKEN, C-SCRIPT-POOL, C-SCRIPT-BT | US-R04, US-R05, US-R06 |

---

## Part 1 回答サマリ（確定事項）

| Q | 決定 |
|---|---|
| Q1 | A: 4 ユニット（U1/U2/U3/U4）。U3+U4 統合や細分化は退ける |
| Q2 | X: 実装順序 **U1 → U4a(pool_ingest/token_issue) → U2 → U3 → U4b(bt_aggregate)**。H-1 を U4a 時点で早期検証 |
| Q3 | A: 直接 import + **層の逆流禁止**（U1 への一方向依存、上位は schema/ の Pydantic モデルと Repository/AssignmentEngine の公開関数に import） |
| Q4 | A: `frontend/ backend/(+domain/) schema/ scripts/ tests/`。schema/ は backend/scripts 双方から解決可能に（pyproject） |
| Q5 | X: `tests/unit/{u1..u4}/` 集約 + `tests/pbt/` 分離。各 PBT は対応受入基準（XC-01/XC-02）をテスト名・docstring に明記 |
