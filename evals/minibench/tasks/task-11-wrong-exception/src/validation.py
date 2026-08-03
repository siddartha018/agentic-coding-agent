def validate_positive(number):
    """Validate that a number is positive, raising ValueError if not."""
    if number <= 0:
        raise TypeError("Number must be positive")
    return number
