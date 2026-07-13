"""LC-04 SessionState Serializer — XC-02 の状態シリアライズ。

ラウンドトリップ対象（H-3）: 確定 PairSequence + 再開位置（次の未回答 index）。
seed / exposure_snapshot は監査用でラウンドトリップ対象外（SessionState に含めない）。

`deserialize(serialize(state)) == state`（P-4, PBT-02）。純粋（I/O は Repository 経由）。
"""

from __future__ import annotations

from schema import Pair, SessionState


def serialize(state: SessionState) -> str:
    """SessionState を JSON 文字列へ（可読・監査リプレイ突合容易, Q2=A）。"""
    return state.model_dump_json()


def deserialize(data: str) -> SessionState:
    """JSON 文字列を SessionState へ復元する。"""
    return SessionState.model_validate_json(data)


def next_unanswered_index(pairs: list[Pair], answered_pair_ids: set[str]) -> int:
    """回答済み pair_id 集合から次の未回答 index を導出する（再開位置, US-P08）。

    サーバが保存済みペア列上の位置から算出し、クライアント値は信用しない。
    """
    for pair in sorted(pairs, key=lambda p: p.index):
        if pair.pair_id not in answered_pair_ids:
            return pair.index
    return len(pairs)  # 全回答済み
