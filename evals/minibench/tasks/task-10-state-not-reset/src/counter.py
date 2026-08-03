class Counter:
    """A simple counter that can be incremented and reset."""

    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1

    def reset(self):
        pass

    def get_count(self):
        return self.count
