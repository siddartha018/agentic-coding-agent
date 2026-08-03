from src.slicer import get_middle_elements


def test_get_middle_five_elements():
    assert get_middle_elements([1, 2, 3, 4, 5]) == [2, 3, 4]


def test_get_middle_four_elements():
    assert get_middle_elements([10, 20, 30, 40]) == [20, 30]
