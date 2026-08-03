from src.list_utils import append_item


def test_append_to_new_list():
    result1 = append_item('a')
    assert result1 == ['a']


def test_append_creates_separate_lists():
    result1 = append_item('x')
    result2 = append_item('y')
    # Each call should create a new list, not share state
    assert result1 != result2
    assert 'y' not in result1
