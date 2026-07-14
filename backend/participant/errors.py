"""参加者フローの業務エラー（統一封筒に載せる, BR-U2-29 / DP-U2-07）。

サービス層はこれを raise し、ParticipantApi が 200 + {ok:false, error, phase?} に写す
（資格不備＝無効トークンも同封筒。HTTP ステータスでの細分はしない）。
"""

from __future__ import annotations


class ParticipantError(Exception):
    """業務エラー（無効トークン・不正 pair/choice/rating・フェーズ外等）。"""

    def __init__(self, message: str, phase: str | None = None):
        super().__init__(message)
        self.message = message
        self.phase = phase
