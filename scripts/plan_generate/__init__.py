"""plan_generate（U6）— 事前生成割当プランの生成器パッケージ。

LC-U6-01〜07 をファイル一対一で分割する（U4b `bt_aggregate` と同型）:
  constraints  : 研究側入力の読込・検証（制約ファイル + 期待組成）
  placement    : ★制約付き円周配置探索（禁止/忌避/濃縮/層間）
  graph_build  : m-正則巡回グラフの構成（露出 gap=0・全体連結・同一ペア0 を構成で保証）
  partition    : E スロットへの分割（k 制約）
  sequencing   : スロット内の順序付け（隣接回避・練習を先頭に固定）
  verify       : BR-U6-10 の①〜⑥ + PU6-8 の検証（投入前ゲート）
  __main__     : CLI（構成 → 検証 → seed 再試行 → 上限で明示失敗）

**非デプロイ**（Worker バンドルに含めない）・**追加依存なし**（標準ライブラリのみ）。
`schema/` のみ依存（`scripts` は `backend` を import しない＝層の一方向依存）。
"""
