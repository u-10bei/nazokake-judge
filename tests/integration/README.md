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

# 1. 本体ソースを隔離コピー（gitignore 対象）。本体は src/ レイアウト（F-8）。
#    entry.py は src/ 直下（backend/ の外）なので個別にコピーする。
rm -rf src/schema src/backend src/entry.py
cp -r ../../src/schema  src/schema
cp -r ../../src/backend src/backend
cp    ../../src/entry.py src/entry.py

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
- U4a: `drive_u4a.py`（`/admin/*` 越し PU4a-1/2/3a/3b/4/6）。
- U2: `drive_u2.py`（`/api/*` 越し 参加者フロー一巡 + PU2-2/4/5/7/8）。**migration は 0001+0002+0003 を適用**してから実行。

## U2 参加者フロー統合（drive_u2.py）
```bash
cd tests/integration
rm -rf src/schema src/backend src/entry.py && cp -r ../../src/schema src/schema && cp -r ../../src/backend src/backend && cp ../../src/entry.py src/entry.py
uv sync
uv run pywrangler d1 migrations apply nazokake-it --local     # 0001+0002+0003
uv run pywrangler dev --port 8788 &
python drive_u2.py | python3 -m json.tool                      # → result-u2-integration.json 相当
```
検証項目: セッション開始（出自秘匿）/ PU2-4 判定冪等 / PU2-2 再開の非重複 / PU2-8 完了順序 /
PU2-7 Likert 初回不変 / PU2-5 練習の集計除外 / 完了・再アクセス。
