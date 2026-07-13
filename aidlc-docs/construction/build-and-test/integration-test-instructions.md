# Integration Test Instructions — U1 Repository × 実 D1

## Purpose
Repository（LC-03, 唯一の I/O 境界）を**実 D1**に対して実行し、実 DDL（`migrations/0001_init.sql`）
の下で SQL・バインディング・batch 原子性・冪等セマンティクスを検証する。純粋ロジックは PBT で
別途検証済みのため、本統合テストは「Repository ↔ D1」の境界に集中する。

ハーネス: `tests/integration/`（使い捨て pywrangler worker。`GET /run` が全シナリオを JSON で返す）。

## Test Scenarios
| # | シナリオ | 検証内容 | 根拠 |
|---|---|---|---|
| 1 | `save_pair_sequence`（コミット） | Session + PairSequence が単一 batch で全保存 | DP-01 |
| 2 | `save_pair_sequence`（原子性） | batch 途中失敗（PK 重複）で**全ロールバック**・半端ペア列を残さない | DP-01 / TSD-03 |
| 3 | `insert_judgment`（冪等） | ON CONFLICT DO NOTHING + 既存 choice 返却（再送で値不変・1 行） | DP-02 / TSD-04 |
| 4 | `read_exposure_counts` | `updated_exposure` オラクルと一致（非アクティブ除外込み） | H-2 / P-5 |

## Setup & Run
```bash
cd tests/integration
rm -rf src/schema src/backend && cp -r ../../schema src/schema && cp -r ../../backend src/backend
uv sync
uv run pywrangler d1 migrations apply nazokake-it --local
uv run pywrangler dev --port 8788 &
curl -s http://127.0.0.1:8788/run | python3 -m json.tool
```
CI（本番同型ランタイム）で行う場合は deploy → `/run`（`smoke-test-deploy.yml` と同型）。

## Expected Results
- **overall_pass = true**（全 4 項目 PASS）。実績 `tests/integration/result-integration.json`（2026-07-13, miniflare）。

## Cleanup
```bash
pkill -f pywrangler   # dev 停止（ローカル D1 状態は .wrangler/ に残る=gitignore）
```
