class MockConnection:
    """Mock database connection."""

    def __init__(self, autocommit=False):
        self.autocommit = autocommit
        self.data = {}

    def execute(self, query, value):
        """Execute a mock query."""
        if not self.autocommit:
            raise RuntimeError("autocommit must be True for this operation")
        self.data['last_query'] = query
        self.data['last_value'] = value
        return True


def get_value(connection, key):
    """Get a value using the connection."""
    connection.execute("SELECT", key)
    return connection.data.get('last_value')
