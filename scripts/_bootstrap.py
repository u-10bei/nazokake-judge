"""src/ レイアウト（F-8）対応の import ブートストラップ。

CLI（`scripts/*.py`）は `schema`（src/ 配下）を import するため、本モジュールを
**最初に** import して `src/` と リポジトリルートを `sys.path` へ足す。これにより
`python -m scripts.token_issue` でも `python scripts/token_issue.py` でも解決できる。
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_ROOT, "src"), _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
