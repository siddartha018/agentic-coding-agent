from src.database import get_value


def test_get_value_with_connection(db_connection):
    result = get_value(db_connection, 'test_key')
    assert result == 'test_key'
