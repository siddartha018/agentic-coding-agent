def get_user_name(users, user_id):
    """Get username for a given user_id from a list of users."""
    # users is a list like: [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]
    for user in users:
        if user[user_id] == user_id:
            return user['name']
    return None
