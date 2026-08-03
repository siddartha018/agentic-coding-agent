def process_twice(items):
    """Process items twice and return the sum of both passes."""
    filtered = (x for x in items if x > 0)
    first_pass = sum(filtered)
    second_pass = sum(filtered)
    return first_pass + second_pass
