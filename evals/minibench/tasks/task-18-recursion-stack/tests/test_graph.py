import pytest
from src.graph import traverse_graph


def test_traverse_acyclic_graph():
    graph = {'A': ['B', 'C'], 'B': ['D'], 'C': [], 'D': []}
    result = traverse_graph('A', graph)
    assert set(result) == {'A', 'B', 'C', 'D'}


def test_traverse_cyclic_graph():
    # Cyclic graph: A -> B -> C -> A
    graph = {'A': ['B'], 'B': ['C'], 'C': ['A']}
    # Should not crash with RecursionError
    result = traverse_graph('A', graph)
    assert set(result) == {'A', 'B', 'C'}
