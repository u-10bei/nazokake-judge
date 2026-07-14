"""backend/admin/ — U4a が先行導入する管理 API 境界（LC-U4a-01/02/05）。

`/admin/*` エンドポイント（AdminApi）+ Basic 認証の単一チョークポイント（AuthGuard）+
秘匿ログ（AdminLog）。U2/U3 が同じ認証境界を再利用する。raw workers API（F-5）。
"""
