# Build and Test Summary — U1 共有基盤（2026-07-13）

## Build Status
- **Build Tool**: uv + pywrangler（Python Workers バンドル）。
- **Build Status**: Success（依存解決・バンドル・ローカル D1 マイグレーション適用いずれも成功）。
- **Build Artifacts**: Worker バンドル（CI 時生成）、`migrations/0001_init.sql`。
- 対象範囲: **U1（共有基盤）**。U2/U3/U4 は未生成のため本サマリは U1 の範囲。

## Test Execution Summary

### Unit Tests + PBT（pure-Python, `tests/unit` + `tests/pbt`）
- **Total**: 19 / **Passed**: 19 / **Failed**: 0（dev・ci 両プロファイル）。
- カバー: schema/トークン契約、serializer（XC-02）、層逆流禁止（U1-NFR-15）、割当プロパティ P-1〜P-7。
- **P-1（露出均衡）は本番規模プール（95 件）で成立**（α=0.7 / S=30 / 重み指数 p=3, 較正確定）。実測 gap=9 < 閾値 17.7（約 2 倍マージン）。
- **Status**: Pass。

### Integration Tests（Repository × 実 D1, `tests/integration`）
- **Scenarios**: 4 / **Passed**: 4 / **Failed**: 0（miniflare, pywrangler dev）。
- save_pair_sequence 原子コミット / batch 途中失敗の全ロールバック（DP-01）/ insert_judgment 冪等（DP-02）/ read_exposure_counts == オラクル（H-2）。
- 生データ: `tests/integration/result-integration.json`。
- **Status**: Pass。

### Performance Tests
- **N/A**（U1-NFR-02: SLO なし。データ規模 〜50 セッション×43 ペア≈2,000 行で `derive_exposure` は瞬時）。

### Additional Tests
- **Contract Tests**: N/A（サービス間 API は U2/U3。データ契約は schema/ の Pydantic 検証で担保）。
- **Security Tests**: パラメータ化クエリ（BR-12, unit で担保）。認証は U3。全面強制は非適用（Q12=B）。
- **E2E Tests**: N/A（参加者フロー UI は U2）。

## Overall Status
- **Build**: Success。
- **All Tests（U1）**: Pass（unit+PBT 19、integration 4）。
- **Ready for Operations**: U1 は Ready。ただし本プロジェクトは per-unit ループのため、**次は U4a→U2→U3→U4b の実装**。Operations は全ユニット完了後。

## Next Steps
- U1 の Build & Test は完了。per-unit ループを進め **次ユニット U4a（token_issue / pool_ingest, 管理 API 経由 H-1(c)）** の Functional Design へ。
- 本実装デプロイ時は CI（`.github/workflows/deploy.yml`）経由。`wrangler.toml` の `database_id` を実 D1 に設定。
