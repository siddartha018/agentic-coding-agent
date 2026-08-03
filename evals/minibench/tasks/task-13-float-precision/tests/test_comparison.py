from src.comparison import are_equal


def test_floats_with_precision_issue():
    # Classic float precision issue: 0.1 + 0.2 != 0.3
    result = 0.1 + 0.2
    assert are_equal(result, 0.3) is True


def test_exact_floats():
    assert are_equal(1.0, 1.0) is True
