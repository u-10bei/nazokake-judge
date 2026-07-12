# Components — nazokake-judge

**アーキテクチャ**: 案 A′（静的フロント + Cloudflare **Python** Workers / FastAPI + D1）
**設計レベル**: 高レベル（責務・インターフェース）。詳細業務ルールは Functional Design（per-unit）。

コンポーネントを 4 レイヤに整理する。

```
[ Frontend (静的・バニラ JS) ]   Participant UI / Admin UI
            │ HTTP(S)/JSON
[ Backend (Python Worker/FastAPI) ]  API層 + 各 Service + AuthMiddleware
            │
[ Domain (純粋ロジック) ]        AssignmentEngine (XC-01)
            │
[ Data / Shared ]                D1 Repository  ←  schema/ (Pydantic + DDL)
            ▲
[ Scripts (Python, scripts/) ]   token_issue / pool_ingest / bt_aggregate
```

---

## L1. フロントエンド（静的・バニラ JS）

### C-FE-PART: Participant UI
- **目的**: 評価者の線形ウィザード（US-P01〜P08）を提供する。
- **責務**:
  - トークン URL でのアクセスと状態別画面遷移（未使用/進行中/完了）。
  - 教示・練習試行・A/B 判定・進捗表示・ブリッジ Likert・事後アンケート・完了画面の描画。
  - 各操作をバックエンド API に送信し、**表示用の一時状態のみ**を保持（権威はサーバ、Q4=A）。
  - モバイルファースト（A/B 縦積みでも可読）、日本語のみ。
- **インターフェース**: バックエンド REST API（JSON）を消費。SSR（Jinja2）併用は画面ごとに Functional Design で判断可。

### C-FE-ADMIN: Admin UI
- **目的**: 研究者向けの進捗・暫定勝率の閲覧（US-R01, US-R03）。
- **責務**: 進捗（発行/開始/完了数・総回答数）と暫定勝率テーブルの表示。Basic 認証の背後。
- **インターフェース**: 管理用 API（Basic 認証必須）を消費。

---

## L2. バックエンド（Python Worker / FastAPI）

### C-API: API Gateway / Router
- **目的**: HTTP ルーティングと入出力（Pydantic による検証）。
- **責務**: エンドポイント定義、リクエスト/レスポンスの型検証、エラー整形、CORS 設定（XC-03）。
- **インターフェース**: 各 Service を呼び出す。

### C-AUTH: AuthMiddleware
- **目的**: 管理エンドポイントの Basic 認証（Q5=B, US-R01/R03/R02）。
- **責務**: `Authorization` ヘッダ検査、シークレット（wrangler secret / 環境変数）との照合。参加者 API は対象外。

### C-SVC-SESSION: SessionService
- **目的**: セッションのライフサイクル（開始・取得・再開）。US-P01, US-P07, US-P08。
- **責務**: トークン検証、状態判定（未使用/進行中/完了）、**セッション開始時に AssignmentEngine を 1 回呼びペア列を確定し DB 保存**（Q3=A）、再開位置（未回答の先頭）算出。

### C-SVC-RESPONSE: ResponseService
- **目的**: ペア判定回答の保存。US-P03。
- **責務**: 回答の冪等保存（同一トークン・同一ペアは 1 件、US-P03）、逐次保存（FR-05）、練習試行の除外（US-P02）。

### C-SVC-SURVEY: SurveyService
- **目的**: ブリッジ Likert（US-P05）・事後アンケート（US-P06）の保存。
- **責務**: Likert 回答と BT 較正アンカーとしての区別保存、アンケート回答保存。設問構成は暫定（プール確定後に確定）。

### C-SVC-ADMIN: AdminService
- **目的**: 進捗集計（US-R01）と暫定勝率テーブル（US-R03）。
- **責務**: 発行/開始/完了数・総回答数の集計、作品ごとの対戦数・暫定勝率の算出（簡易・非 BT）。

### C-SVC-EXPORT: ExportService
- **目的**: 回答データの CSV/JSON エクスポート（US-R02）。
- **責務**: ペア判定・Likert・アンケートを **schema/ の Pydantic モデル準拠**で出力。形式バージョンを付す。US-R04 の入力形式と一致（Q6=A）。

---

## L3. ドメイン（純粋ロジック）

### C-DOM-ASSIGN: AssignmentEngine（XC-01）
- **目的**: ペア割当の純粋関数。
- **責務**: シグネチャ `(プール, これまでの露出カウント, シード) → ペア列`。露出均衡（全セッション横断の不変条件）と層間比率を満たす。層ラベルを入力に用いる。
- **品質**: **純粋関数**として実装し **PBT-03（不変条件）で重点検証**。副作用なし（DB 読み書きは SessionService 側）。
- **注記**: 「露出カウントの読取」「ペア列の保存」は SessionService が担い、本エンジンは計算に専念（テスト対象と本番パスを一致させる、Q3=A）。

---

## L4. データ / 共有

### C-REPO: D1 Repository
- **目的**: D1（SQLite 互換）への永続化の単一窓口。
- **責務**: 作品（層ラベル付き）、トークン、セッション、確定ペア列、ペア判定回答、Likert、アンケートの CRUD。パラメータ化クエリ（SQLi 対策・XC-03）。
- **インターフェース**: schema/ の DDL に準拠。

### C-SCHEMA: schema/（共有データ契約）
- **目的**: アプリと scripts/ が共有する単一の真実（Q6=A）。
- **責務**: (i) D1 用 DDL、(ii) **Pydantic モデル**（エクスポート形式の正）、(iii) エクスポート形式の**バージョン番号**。
- **利用**: Worker（ExportService 等）と scripts/ が同一モジュールを import。

---

## L5. スクリプト（Python, `scripts/`）

### C-SCRIPT-TOKEN: token_issue（US-R05）
- **目的**: 参加者トークンの発行・配布一覧生成。
- **責務**: 推測困難な一意トークンを指定数生成（XC-03）、配布用 URL 一覧出力、既存との衝突回避。

### C-SCRIPT-POOL: pool_ingest（US-R06）
- **目的**: 刺激プールの投入。
- **責務**: 作品本文 + **層ラベル（4 層・必須）** を DB へ登録。ラベル欠落は拒否。作品本文はリポジトリ管理外（NFR-08）。

### C-SCRIPT-BT: bt_aggregate（US-R04）
- **目的**: オフライン BT 推定。
- **責務**: ExportService のエクスポート（schema/ 準拠）を入力に Bradley–Terry 推定、全作品の品質スコア出力、Likert を較正アンカーとして解釈。

---

## コンポーネント一覧（要約）

| ID | 名称 | レイヤ | 主な関連ストーリー |
|---|---|---|---|
| C-FE-PART | Participant UI | Frontend | US-P01〜08 |
| C-FE-ADMIN | Admin UI | Frontend | US-R01, US-R03 |
| C-API | API Gateway/Router | Backend | 全 API |
| C-AUTH | AuthMiddleware | Backend | US-R01/R02/R03, XC-03 |
| C-SVC-SESSION | SessionService | Backend | US-P01/P07/P08 |
| C-SVC-RESPONSE | ResponseService | Backend | US-P03 |
| C-SVC-SURVEY | SurveyService | Backend | US-P05/P06 |
| C-SVC-ADMIN | AdminService | Backend | US-R01/R03 |
| C-SVC-EXPORT | ExportService | Backend | US-R02 |
| C-DOM-ASSIGN | AssignmentEngine | Domain | XC-01, FR-03 |
| C-REPO | D1 Repository | Data | 全永続化, XC-03 |
| C-SCHEMA | schema/ | Shared | US-R02↔R04, US-R06 |
| C-SCRIPT-TOKEN | token_issue | Scripts | US-R05 |
| C-SCRIPT-POOL | pool_ingest | Scripts | US-R06, XC-01 |
| C-SCRIPT-BT | bt_aggregate | Scripts | US-R04 |
