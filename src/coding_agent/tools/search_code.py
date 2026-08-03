from __future__ import annotations

from ..indexing.qdrant import collection_name, get_client, DENSE_NAME, SPARSE_NAME, _bm25
from ..llm import get_llm
from ..obs import observed


@observed(name="tool.search_code", as_type="retriever")
def search_code(task_id: str, query: str, k: int = 8) -> list[dict]:
    """Hybrid search using RRF (Reciprocal Rank Fusion) over dense + sparse vectors.

    Args:
        task_id: Task identifier for the Qdrant collection
        query: Search query string
        k: Number of top results to return (default 8)

    Returns:
        List of dicts with keys: path, symbol, start_line, end_line, text, score
    """
    client = get_client()
    name = collection_name(task_id)

    if not client.collection_exists(name):
        return []

    # Dense search: embed query via LLM
    try:
        llm = get_llm()
        dense_vec = llm.embed([query])[0]
    except Exception:
        dense_vec = [0.0] * 768  # Fallback: zero vector

    # Sparse search: BM25 (reuse cached model)
    try:
        bm25 = _bm25()
        sparse_vecs = list(bm25.embed([query]))
        sparse_vec = sparse_vecs[0] if sparse_vecs else None
    except Exception:
        sparse_vec = None

    # Query dense vectors
    dense_results = {}
    try:
        dense_hits = client.search(
            collection_name=name,
            query_vector=(DENSE_NAME, dense_vec),
            limit=k * 2,
            with_payload=True,
        )
        for rank, hit in enumerate(dense_hits):
            dense_results[hit.id] = (1.0 / (rank + 1), hit)
    except Exception:
        pass

    # Query sparse vectors
    sparse_results = {}
    if sparse_vec:
        try:
            sparse_hits = client.search(
                collection_name=name,
                query_vector=(SPARSE_NAME, sparse_vec),
                limit=k * 2,
                with_payload=True,
            )
            for rank, hit in enumerate(sparse_hits):
                sparse_results[hit.id] = (1.0 / (rank + 1), hit)
        except Exception:
            pass

    # RRF: combine dense and sparse scores
    combined: dict[int, tuple[float, any]] = {}
    for point_id, (score, hit) in dense_results.items():
        combined[point_id] = (score, hit)
    for point_id, (score, hit) in sparse_results.items():
        if point_id in combined:
            combined[point_id] = (combined[point_id][0] + score, combined[point_id][1])
        else:
            combined[point_id] = (score, hit)

    # Sort by RRF score and return top-k
    sorted_results = sorted(combined.items(), key=lambda x: x[1][0], reverse=True)[:k]

    output = []
    for point_id, (rrf_score, hit) in sorted_results:
        payload = hit.payload
        output.append({
            "path": payload.get("path", ""),
            "symbol": payload.get("symbol", ""),
            "start_line": payload.get("start_line", 0),
            "end_line": payload.get("end_line", 0),
            "text": payload.get("text", ""),
            "score": rrf_score,
        })

    return output
