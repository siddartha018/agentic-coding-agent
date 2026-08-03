def find_max(numbers):
    """Return the maximum value from a list of numbers."""
    if not numbers:
        return None

    max_val = numbers[0]
    for num in numbers[1:]:
        if num > max_val:
            max_val = num
