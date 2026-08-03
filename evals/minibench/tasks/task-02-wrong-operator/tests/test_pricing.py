from src.pricing import discount_price


def test_twenty_percent_discount():
    assert discount_price(100, 20) == 80


def test_fifty_percent_discount():
    assert discount_price(200, 50) == 100
