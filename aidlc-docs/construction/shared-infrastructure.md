# Shared Infrastructure — nazokake-judge

**位置づけ**: 全ユニット（U1〜U4）が共有するインフラ・データ契約を集約する。U1 Infrastructure Design（Q3=A）で確定。
**原則**: 共有インフラの変更は全ユニットに波及する。ここを単一の真実とする。

---

## 1. 共有コンポーネント

| 共有物 | 実体 | 所有ユニット | 利用ユニット |
|---|---|---|---|
| **D1 データベース** | Cloudflare D1（SQLite 互換, マネージド） | U1（C-REPO / DDL） | U1（Repository）, U2（参加者フロー）, U3（管理/エクスポート）, U4（scripts, 管理 API 経由） |
| **schema/（データ契約）** | Pydantic モデル + D1 DDL(.sql) + エクスポート形式バージョン | U1（C-SCHEMA） | 全ユニット（backend / scripts が import） |

- **D1 と schema/ は全ユニット共有インフラ**。unit-of-work.md の依存構造（全ユニット → U1）と整合。
- **層の逆流禁止**: 上位ユニットは U1 の公開面のみ import。U1 から上位への依存は禁止。

---

## 2. 環境分離（全ユニット共通）

| 環境 | D1 | Compute |
|---|---|---|
| dev | ローカル D1 / miniflare | `wrangler dev` |
| prod | 本番 D1（単一） | Python Workers（実験用サブドメイン） |

- dev/prod の D1 を分離（実験データ汚染防止）。全ユニットが同じ環境分離に従う。

---

## 3. 共有アクセス規約

- **実行時の D1 アクセスは Worker に集約**（H-1 = (c) 確定）。scripts は Worker 管理 API（Basic 認証）経由。→ `u1/infrastructure-design/infrastructure-design.md` §4。
- **DDL 適用は `wrangler d1 migrations`**（versioned）。全ユニットの DDL 変更はここを通す。
- **F-7（D1 bind の整数上限, 全ユニット共通）**: D1 `.bind()` は **2^53−1 を超える整数を拒否**（`D1_TYPE_ERROR: bigint`）。DB に保存/バインドする整数（seed・カウンタ等）は 2^53 未満に収める（U2 seed=SHA-256 先頭 6 バイト=48bit で対処）。pure-Python/PBT では出ず integration でのみ露見。
- **F-8（バンドルの module root, 全ユニット共通）**: Python Workers は **`main` のディレクトリのみをモジュールルートにバンドル**する。絶対 import（`backend.…`/`schema.…`）を使うコードは `main` と同一ディレクトリ配下に置く＝**`src/` レイアウト**（本実装は `main="src/entry.py"` + `src/backend/` + `src/schema/`）。`frontend/`・`migrations/`・`scripts/`・`tests/` はルート据え置き。詳細＝F-1〜F-8（`u1/infrastructure-design/infrastructure-design.md` §2.1）。**U3/U4b の新規 backend コードも `src/` 配下に置くこと**。
- **シークレットは `wrangler secret`**（リポジトリ外）。ローカルは `.dev.vars`（gitignore）。
- **schema/ の import パス解決**: backend も scripts も import 可能なパスに配置（`pyproject.toml` packages 設定。Code Generation で確定）。

---

## 4. 後続ユニットへの申し送り

- **U2/U3**: D1 バインディング・schema/ を共有。API 層で CORS/HTTPS/Basic 認証を担保。
- **U4a/U4b**: scripts の実行時 D1 アクセスは **Worker 管理 API（Basic 認証）経由**（H-1 (c)）。Functional Design はこの前提で行う。
- **共有変更のルール**: D1 スキーマ・schema/ 契約の変更は本書と `schema/` の versioned migrations を通じて行い、影響ユニットを明記する。
