from qdrant_client import QdrantClient
from coding_agent.indexing.qdrant import (
    create_task_collection, delete_task_collection, upsert_chunks,
    collection_name, DENSE_DIM,
)
from coding_agent.indexing.tree_sitter_chunk import Chunk


def test_lifecycle(monkeypatch):
    client = QdrantClient(":memory:")
    monkeypatch.setattr("coding_agent.indexing.qdrant.get_client", lambda: client)
    name = create_task_collection("t1")
    assert client.collection_exists(name)
    chunks = [Chunk(path="calc.py", symbol="add", start_line=1, end_line=2, text="def add(): pass")]
    upsert_chunks("t1", chunks, [[0.1] * DENSE_DIM])
    hits, _ = client.scroll(collection_name=name, limit=10, with_payload=True)
    assert len(hits) == 1
    delete_task_collection("t1")
    assert not client.collection_exists(collection_name("t1"))
