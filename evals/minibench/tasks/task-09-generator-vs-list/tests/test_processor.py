from src.processor import process_twice


def test_process_twice():
    result = process_twice([1, 2, -1, 3])
    # First pass: 1 + 2 + 3 = 6, Second pass: 1 + 2 + 3 = 6, Total = 12
    assert result == 12


def test_process_twice_all_positive():
    result = process_twice([5, 10])
    # First pass: 15, Second pass: 15, Total = 30
    assert result == 30
