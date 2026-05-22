import pytest

from src.block import validate_repeat_amount


def test_repeat_amount_accepts_one():
    assert validate_repeat_amount("1") == 1


def test_repeat_amount_accepts_large_integer():
    assert validate_repeat_amount("42") == 42


def test_repeat_amount_rejects_zero():
    with pytest.raises(ValueError):
        validate_repeat_amount("0")


def test_repeat_amount_rejects_decimal():
    with pytest.raises(ValueError):
        validate_repeat_amount("1.5")


def test_repeat_amount_rejects_negative():
    with pytest.raises(ValueError):
        validate_repeat_amount("-1")
