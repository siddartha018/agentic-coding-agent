import pytest
from src.validation import validate_positive


def test_validate_positive_number():
    assert validate_positive(5) == 5


def test_validate_negative_raises_value_error():
    with pytest.raises(ValueError):
        validate_positive(-5)


def test_validate_zero_raises_value_error():
    with pytest.raises(ValueError):
        validate_positive(0)
