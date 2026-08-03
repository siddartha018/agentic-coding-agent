from src.stats import compute_average


def test_average_of_numbers():
    assert compute_average([1, 2, 3, 4]) == 2.5


def test_average_of_empty_list():
    assert compute_average([]) == 0
