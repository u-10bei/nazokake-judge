"""backend/domain/ — LC-02 AssignmentEngine（純粋）+ LC-04 SessionState Serializer。

副作用なし・DB I/O を持たない（I/O は LC-03 Repository に集約）。決定論（P-6）。
schema/ の型のみを import する。
"""

from backend.domain.assignment import (
    SessionExposure,
    derive_exposure,
    generate_pairs,
    updated_exposure,
)
from backend.domain.serializer import deserialize, serialize

__all__ = [
    "generate_pairs",
    "updated_exposure",
    "derive_exposure",
    "SessionExposure",
    "serialize",
    "deserialize",
]
