from src.messages import get_status_message


def test_success_message():
    assert get_status_message(200) == "Success"


def test_not_found_message():
    assert get_status_message(404) == "Not Found"
