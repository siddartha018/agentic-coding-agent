from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient, models
from fastembed import SparseTextEmbedding

from ..config import get_settings
from .tree_sitter_chunk import Chunk


DENSE_NAME = "dense"
SPARSE_NAME = "sparse"
DENSE_DIM = 768

_BM25_MODEL = "Qdrant/bm25"


@lru_cache
def _bm25() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name=_BM25_MODEL)


@lru_cache
def get_client() -> QdrantClient:
    s = get_settings()
    if s.qdrant_url == ":memory:":
        return QdrantClient(":memory:")
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key)


def collection_name(task_id: str) -> str:
    return "repo_" + task_id.replace("-", "")[:24]


def create_task_collection(task_id: str, *, client: QdrantClient | None = None) -> str:
    c = client or get_client()
    name = collection_name(task_id)
    if not c.collection_exists(name):
        c.create_collection(
            collection_name=name,
            vectors_config={
                DENSE_NAME: models.VectorParams(
                    size=DENSE_DIM, distance=models.Distance.COSINE
                ),
            },
            sparse_vectors_config={
                SPARSE_NAME: models.SparseVectorParams(),
            },
        )
    return name


def delete_task_collection(task_id: str, *, client: QdrantClient | None = None) -> None:
    c = client or get_client()
    name = collection_name(task_id)
    if c.collection_exists(name):
        c.delete_collection(name)


def upsert_chunks(
    task_id: str,
    chunks: list[Chunk],
    dense_vectors: list[list[float]],
    *,
    client: QdrantClient | None = None,
) -> None:
    if not chunks:
        return
    assert len(chunks) == len(dense_vectors), "dense vector count mismatch"
    c = client or get_client()
    name = collection_name(task_id)
    sparse = list(_bm25().embed([ch.text for ch in chunks]))
    points = []
    for i, (ch, dv, sv) in enumerate(zip(chunks, dense_vectors, sparse)):
        points.append(
            models.PointStruct(
                id=hash((ch.path, ch.symbol, ch.start_line)) & 0x7fffffff,  # Convert to positive integer
                vector={
                    DENSE_NAME: dv,
                    SPARSE_NAME: models.SparseVector(
                        indices=sv.indices.tolist(),
                        values=sv.values.tolist(),
                    ),
                },
                payload={
                    "path": ch.path,
                    "symbol": ch.symbol,
                    "start_line": ch.start_line,
                    "end_line": ch.end_line,
                    "text": ch.text,
                },
            )
        )
    c.upsert(collection_name=name, points=points)
