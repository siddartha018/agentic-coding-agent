from src.formatter import format_user


def test_format_user():
    user = {'first': 'John', 'middle': 'Q', 'last': 'Doe'}
    result = format_user(user)
    assert result == "User: John Q Doe"
