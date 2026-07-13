# U1 Code — 共有基盤 (foundation) 生成サマリ

**ユニット**: U1（C-SCHEMA / C-DOM-ASSIGN / C-REPO + LogEmitter）
**生成日**: 2026-07-13（Code Generation Part 2）
**前提**: G-1 本番確定の実装規約（raw workers API + Pydantic v2 / module-level `on_fetch` / uv+pywrangler / CI デプロイ / `workers_dev=true`）。

---

## 1. 生成ファイル（アプリコードはワークスペース直下）

| 層 | ファイル | 役割 |
|---|---|---|
| **C-SCHEMA (LC-01)** | `schema/__init__.py` | 狭い公開面（DP-07）: モデル型 + 明示バリデート関数 |
| | `schema/models.py` | Pydantic v2 モデル（Item/Token/Session/Pair/PairSequence/Judgment/Likert/Survey/SessionState/AssignmentParams） |
| | `schema/tokens.py` | トークン契約（128-bit, `token_urlsafe(16)`, 文字集合）DP-05/TSD-05 |
| | `schema/version.py` | エクスポート形式バージョン |
| **C-DOM-ASSIGN (LC-02/04)** | `backend/domain/assignment.py` | `generate_pairs`（重み付き抽選+決定論）/ `updated_exposure`（P-5 オラクル）/ `derive_exposure`（H-2, 非アクティブ除外 BR-04） |
| | `backend/domain/serializer.py` | `serialize`/`deserialize`（XC-02 ラウンドトリップ）/ `next_unanswered_index` |
| **C-REPO (LC-03)** | `backend/repo/repository.py` | 唯一の I/O 境界。`save_pair_sequence`（D1 batch 原子確定 DP-01）/ `insert_judgment`（冪等 DP-02）/ `read_exposure_counts`（derive 委譲）/ `get_token`・`mark_token_*`・`list_items` |
| | `backend/repo/_d1.py` | D1 低レベルヘルパ（`to_py`/`to_js_maybe`, 本番実証イディオム） |
| **LogEmitter (LC-05)** | `backend/log.py` | `emit(event, level, **fields)` 構造化 JSON→stdout（DP-06） |
| **Deploy scaffold** | `backend/entry.py` | 最小 `on_fetch` ヘルス（**ルートは U2/U3 が配線** = API 層は U1 スコープ外） |
| **DDL** | `migrations/0001_init.sql` | 一意制約（DP-02）・NOT NULL（BR-11）・CHECK・FK |
| **Config** | `pyproject.toml` / `wrangler.toml` / `.dev.vars.example` / `.gitignore` / `.github/workflows/deploy.yml` | ツールチェーン・binding・CI |
| **Tests** | `tests/unit/u1/*` / `tests/pbt/*` / `tests/conftest.py` | 下記 §3 |

## 2. 公開面（上位ユニットが import してよい面）
- `schema`（`from schema import Item, Token, ..., generate_token, is_valid_token, EXPORT_FORMAT_VERSION`）。
- `backend.domain`（`generate_pairs` / `updated_exposure` / `derive_exposure` / `serialize` / `deserialize` / `SessionExposure`）。
- `backend.repo.Repository`（Worker 内専用。D1 binding を渡して使用）。
- `backend.log.emit`。
- **層の逆流禁止**（U1-NFR-15）: 上位は上記のみ import。U1 から上位への依存なし（`test_layering.py` で静的検証）。

## 3. テスト（実行は Build & Test。本ステージは生成まで）
- **PBT**（`tests/pbt/`, Hypothesis, TSD-07）: P-1（露出偏り累積）/ P-2（層間比率）/ P-3（セッション内制約）/ P-4（ラウンドトリップ）/ P-5（updated==derive オラクル）/ P-6（決定論）/ P-7（位置一様）。ドメインジェネレータ `generators.py`（PBT-07）、α/S 較正ハーネス `calibration.py`（DP-08 と共有ループ）。
- **unit**（`tests/unit/u1/`）: schema/トークン契約、serializer、層逆流禁止。
- **profile**: `HYPOTHESIS_PROFILE=dev|ci`（conftest）。ci=固定シード・examples 多め・deadline 無効。
- **本ステージでの実行実績**: `dev`/`ci` 両プロファイルで **18 passed**（ローカル pure-Python）。Repository の D1 依存テストは miniflare で Build & Test にて実施。

## 4. 実行/デプロイ
- テスト: `HYPOTHESIS_PROFILE=ci uv run --group dev pytest -q`。
- デプロイ: **CI（`.github/workflows/deploy.yml`）経由**（`uv run pywrangler d1 migrations apply --remote` → `deploy`）。`wrangler.toml` の `database_id` を実 D1 に設定。

## 5. 未確定 → Build & Test 申し送り
- **α/S 較正**: `calibration.py` の `ALPHA_PROVISIONAL=0.5`/`S_PROVISIONAL=30` は暫定。較正シミュレーション（同一累積ループ共有）で確定し `business-rules.md` パラメータ表に追記。述語形は固定。
- **Repository D1 テスト**: miniflare/ローカル D1 での冪等性・原子性の実行。
- **暫定パラメータ**（session_pairs=40/practice=3/likert=10/cross=0.65/k=3/inactive=48h）は Negotiable。
