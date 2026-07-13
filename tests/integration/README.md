# U1 Repository 実 D1 統合テスト（Build & Test）

純粋ロジックは PBT（`tests/pbt/`）で検証済み。本ハーネスは **Repository を実 D1 に対して
実行**し、実 DDL（`migrations/0001_init.sql`）の下で SQL/バインディング/原子性/冪等性を検証する。

smoke-test と同じ隔離パターン（`main` の dir=`src/` のみバンドル、`node_modules`/`.venv` は
親）。DRY のため本体ソース（`schema/` `backend/`）は git 管理せず、実行前に親からコピーする。

## 検証項目（`GET /run`）
1. `save_pair_sequence` — Session + PairSequence を単一 batch で原子コミット（DP-01）
2. `save_pair_sequence` 原子性 — batch 途中失敗（PK 重複）で全ロールバック（半端ペア列を残さない）
3. `insert_judgment` — ON CONFLICT DO NOTHING + 既存 choice 返却で冪等（DP-02）
4. `read_exposure_counts` — `updated_exposure` オラクルと一致（H-2, 非アクティブ除外）

## 実行手順
```bash
cd tests/integration

# 1. 本体ソースを隔離コピー（gitignore 対象）
rm -rf src/schema src/backend
cp -r ../../schema  src/schema
cp -r ../../backend src/backend

# 2. 依存導入 + ローカル D1 マイグレーション
uv sync
uv run pywrangler d1 migrations apply nazokake-it --local

# 3. dev 起動して実行
uv run pywrangler dev --port 8788 &
curl -s http://127.0.0.1:8788/run | python3 -m json.tool

# CI（本番同型ランタイム）で行う場合は smoke-test-deploy.yml と同様に deploy → /run。
```

## 実行実績
- 2026-07-13 ローカル（miniflare, pywrangler dev）で **全 4 項目 PASS**（`result-integration.json`）。
