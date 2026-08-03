from src.validator import is_valid_age


def test_adult_age():
    assert is_valid_age(18) is True
    assert is_valid_age(25) is True


def test_minor_age():
    assert is_valid_age(17) is False
    assert is_valid_age(10) is False
