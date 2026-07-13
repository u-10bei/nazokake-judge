"""Hypothesis の settings profile を dev/ci で分離（TSD-07 / PBT-08）。

  dev : examples 少なめ・高速（開発中の反復用）
  ci  : examples 多め・deadline 無効・print_blob=True・固定シード（再現可能実行）

環境変数 HYPOTHESIS_PROFILE で選択（既定 dev）。CI では HYPOTHESIS_PROFILE=ci。
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

settings.register_profile("dev", max_examples=25)
settings.register_profile(
    "ci",
    max_examples=200,
    deadline=None,
    print_blob=True,        # 反例の blob を出力（PBT-08）
    derandomize=True,       # 固定シードで決定論的実行（統計的性質の flaky 化防止, U1-NFR-13）
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))
