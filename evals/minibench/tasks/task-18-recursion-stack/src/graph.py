def traverse_graph(node, graph, visited=None):
    """Traverse a graph and return all reachable nodes."""
    if visited is None:
        visited = set()

    visited.add(node)
    result = [node]

    for neighbor in graph.get(node, []):
        # Bug: missing early return if neighbor already visited
        result.extend(traverse_graph(neighbor, graph, visited))

    return result
