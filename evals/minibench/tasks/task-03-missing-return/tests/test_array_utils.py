from src.array_utils import find_max


def test_find_max_basic():
    assert find_max([1, 5, 3, 2]) == 5


def test_find_max_negative():
    assert find_max([-10, -5, -20]) == -5
