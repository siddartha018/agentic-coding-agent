from src.parser import extract_price


def test_extract_basic_price():
    assert extract_price("Price: $50") == 50


def test_extract_price_with_context():
    assert extract_price("Total cost is $123 today") == 123
