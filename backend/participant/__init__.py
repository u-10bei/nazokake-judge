"""backend/participant/ — U2 参加者フロー（線形ウィザードのオーケストレーション）。

U1/U4a の公開面（schema / Repository / domain: generate_pairs・select_likert_targets・
serializer）を消費する。**層の逆流禁止**（participant → domain/repo/schema の一方向）。

構成:
  - phase.py    : derive_phase（純粋述語・DB カウントから 5 状態を導出, DP-U2-05）
  - log.py      : ParticipantLog（秘匿ラッパ + token_hash, DP-U2-03）
  - view.py     : ViewSerializer（domain→view 写像・出自秘匿の一点集約, DP-U2-02）
  - session.py  : SessionService（start_or_resume / get_state）
  - response.py : ResponseService（submit_judgment）
  - survey.py   : SurveyService（submit_likert / submit_survey + 完了順序確認）
  - api.py      : ParticipantApi（/api/* ルーティング・トークン検証・no-store・統一封筒）
"""
