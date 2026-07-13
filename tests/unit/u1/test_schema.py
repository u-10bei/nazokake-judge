"""C-SCHEMA 単体テスト: モデル検証・トークン契約（U1-NFR-08）。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schema import (
    Choice,
    Item,
    Layer,
    generate_token,
    is_valid_token,
    validate_item,
    validate_judgment,
    TOKEN_MIN_LENGTH,
)


def test_item_requires_layer():
    """層ラベル欠落は投入拒否（BR-11）。"""
    with pytest.raises(ValidationError):
        validate_item({"item_id": "a", "body_ref": "r"})  # layer なし


def test_item_rejects_unknown_layer():
    with pytest.raises(ValidationError):
        validate_item({"item_id": "a", "layer": "unknown", "body_ref": "r"})


def test_item_accepts_all_layers():
    for layer in Layer:
        it = Item(item_id="x", layer=layer, body_ref="r")
        assert it.layer == layer


def test_item_is_frozen():
    it = Item(item_id="x", layer=Layer.PRO, body_ref="r")
    with pytest.raises(ValidationError):
        it.item_id = "y"  # frozen


def test_judgment_choice_enum():
    j = validate_judgment(
        {"token": "t" * TOKEN_MIN_LENGTH, "pair_id": "p", "choice": "A",
         "created_at": "2026-07-13T00:00:00Z"}
    )
    assert j.choice is Choice.A
    with pytest.raises(ValidationError):
        validate_judgment(
            {"token": "t", "pair_id": "p", "choice": "C", "created_at": "2026-07-13T00:00:00Z"}
        )


def test_token_contract():
    """生成トークンは契約（長さ・文字集合）に適合する（DP-05 / TSD-05）。"""
    for _ in range(50):
        tok = generate_token()
        assert is_valid_token(tok)
        assert len(tok) >= TOKEN_MIN_LENGTH


def test_token_contract_rejects_bad():
    assert not is_valid_token("")
    assert not is_valid_token("short")
    assert not is_valid_token("has space " + "x" * TOKEN_MIN_LENGTH)
    assert not is_valid_token("bad/char" * 4)  # '/' は URL-safe base64 外
