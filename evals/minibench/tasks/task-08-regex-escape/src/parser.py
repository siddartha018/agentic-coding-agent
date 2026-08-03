import re


def extract_price(text):
    """Extract a dollar price from text like 'Price: $50'."""
    match = re.search(r'$(\d+)', text)
    if match:
        return int(match.group(1))
    return None
