"""backend/repo/ — LC-03 Repository（唯一の I/O 境界, C-REPO）。

D1 への読み書きを集約する Worker 内専用モジュール（実行時 D1 アクセスは Worker に
集約, H-1=(c)）。全メソッドはパラメータ化クエリ（BR-12 / DP-04）。
"""

from backend.repo.repository import Repository

__all__ = ["Repository"]
