from src.calculator import sum_first_n


def test_sum_first_three():
    assert sum_first_n(3) == 6


def test_sum_first_five():
    assert sum_first_n(5) == 15
