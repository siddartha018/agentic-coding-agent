from src.counter import Counter


def test_counter_increments():
    c = Counter()
    c.increment()
    c.increment()
    assert c.get_count() == 2


def test_counter_resets():
    c = Counter()
    c.increment()
    c.increment()
    c.reset()
    assert c.get_count() == 0
