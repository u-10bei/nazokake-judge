"""bt_aggregate（U4b）— BT 集計スクリプトのパッケージ。

LC-U4b-01〜07 をファイル一対一で分割し、統計ロジックは副作用なし純関数
（aggregate / graph / mm / calibrate / assemble）、副作用（I/O・終了コード）は CLI
（__main__）に集約する（DP-U4b-02/03）。オフライン pure-Python・追加依存なし
（標準ライブラリのみ, BR-U4b-13）。`schema/`（ExportBundle 入力・BTResult 出力）のみ依存。
"""
