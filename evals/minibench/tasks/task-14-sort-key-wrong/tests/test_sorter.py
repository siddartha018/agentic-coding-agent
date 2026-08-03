from src.sorter import sort_by_age


def test_sort_by_age():
    people = [
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob', 'age': 25},
        {'name': 'Charlie', 'age': 35}
    ]
    result = sort_by_age(people)
    assert result[0]['name'] == 'Bob'
    assert result[1]['name'] == 'Alice'
    assert result[2]['name'] == 'Charlie'
