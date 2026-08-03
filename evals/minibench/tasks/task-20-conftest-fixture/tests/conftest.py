import pytest
from src.database import MockConnection


@pytest.fixture
def db_connection():
    """Provide a database connection for tests."""
    # Bug: missing autocommit=True parameter
    conn = MockConnection()
    yield conn
