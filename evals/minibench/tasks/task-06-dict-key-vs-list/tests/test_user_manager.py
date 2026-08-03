from src.user_manager import get_user_name


def test_get_existing_user():
    users = [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]
    assert get_user_name(users, 1) == 'Alice'
    assert get_user_name(users, 2) == 'Bob'


def test_get_nonexistent_user():
    users = [{'id': 1, 'name': 'Alice'}]
    assert get_user_name(users, 99) is None
