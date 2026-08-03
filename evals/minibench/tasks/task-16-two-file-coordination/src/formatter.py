from src.helper import build_full_name


def format_user(user):
    """Format a user dictionary into a display string."""
    name = build_full_name(user['first'], user['last'])
    return f"User: {name}"
