# Unit / PBT Test Execution — U1

純粋ロジック（domain / schema / serializer）は Worker ランタイム外の pure-Python として実行する（TSD-07）。

## 実行
```bash
# dev（高速）
HYPOTHESIS_PROFILE=dev uv run --group dev pytest tests/unit tests/pbt -q
# ci（examples 多め・deadline 無効・固定シード）
HYPOTHESIS_PROFILE=ci  uv run --group dev pytest tests/unit tests/pbt -q
```

## テスト内訳
- `tests/unit/u1/test_schema.py` — Pydantic モデル検証・トークン契約（BR-11 / DP-05 / TSD-05）。
- `tests/unit/u1/test_serializer.py` — XC-02 ラウンドトリップ（example）・`next_unanswered_index`。
- `tests/unit/u1/test_layering.py` — **層の逆流禁止**（U1-NFR-15）を静的検証。
- `tests/pbt/test_assignment_properties.py` — P-1〜P-7（Hypothesis, PBT-02/03/07/08）。
  - P-1 は**本番規模プール（95 件）**で評価（α=0.7 / S=30 / 重み指数 p=3, 較正確定 2026-07-13）。
- `tests/pbt/generators.py`（ドメインジェネレータ PBT-07）/ `calibration.py`（α/S 較正=DP-08 共有ループ）。

## 期待結果
- **19 passed / 0 failed**（dev・ci 両プロファイル, 2026-07-13 実績）。
- 反例時はシード + 縮小入力が出力される（ci: `print_blob=True`, PBT-08）。
