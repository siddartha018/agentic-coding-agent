def sum_first_n(n):
    """Return the sum of first n positive integers."""
    total = 0
    for i in range(1, n):
        total += i
    return total
