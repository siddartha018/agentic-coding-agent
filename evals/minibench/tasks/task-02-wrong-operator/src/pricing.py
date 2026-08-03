def discount_price(price, discount_percent):
    """Calculate price after discount percentage is applied."""
    discount_amount = price * (discount_percent / 100)
    return price + discount_amount
