"""D1（Cloudflare）アクセスの低レベルヘルパ。

本番 smoke test（G-1）で確認済みのイディオム:
  - `await db.prepare(sql).bind(...).run()/first()/all()`
  - `await db.batch(to_js_maybe([stmt, ...]))`（暗黙トランザクショナル=原子適用, DP-01）
  - D1 の返り値は JsProxy のことがあるため to_py で変換する。

Worker(Pyodide) ランタイム専用。ローカル/CI の pure-Python テストからは import しない
（Repository のテストは miniflare/ローカル D1 上で実行する, Build & Test）。
"""

from __future__ import annotations


def to_py(obj):
    """JsProxy → Python 値。既に Python 値ならそのまま返す。"""
    try:
        return obj.to_py()
    except AttributeError:
        return obj


def to_js_maybe(x):
    """D1.batch は JS 配列を期待するため可能なら変換する。"""
    try:
        from pyodide.ffi import to_js  # Worker ランタイムでのみ解決
        return to_js(x)
    except Exception:  # noqa: BLE001
        return x
