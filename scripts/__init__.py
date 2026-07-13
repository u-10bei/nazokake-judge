"""scripts/ — 運用 CLI（U4 系）。Worker 外の pure-Python。

U4a: pool_ingest / token_issue。管理 API（`/admin/*`）を HTTPS + Basic で叩く（H-1(c)）。
D1 に直接触れない。認証情報は環境変数 ADMIN_BASIC_USER / ADMIN_BASIC_PASSWORD。
"""
