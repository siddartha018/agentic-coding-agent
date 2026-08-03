from __future__ import annotations

from ..indexing.tree_sitter_chunk import chunk_repo, Chunk
from ..indexing.qdrant import create_task_collection, upsert_chunks
from ..llm import get_llm
from ..obs import observed
from ..state import AgentState


@observed(name="node.index", as_type="agent", capture_input=False)
def run_index(
    state: AgentState,
    *,
    chunk_fn=None,
    embed_fn=None,
    upsert_fn=None,
    create_fn=None,
) -> dict:
    """Index the repository by chunking, embedding, and storing in Qdrant.

    Args:
        state: AgentState with task_id and workdir
        chunk_fn: Function to chunk repo (default: chunk_repo)
        embed_fn: Function to embed texts (default: llm.embed)
        upsert_fn: Function to upsert chunks (default: upsert_chunks)
        create_fn: Function to create collection (default: create_task_collection)

    Returns:
        Empty dict (no state changes)
    """
    chunk_fn = chunk_fn or chunk_repo
    embed_fn = embed_fn or (lambda texts: get_llm().embed(texts))
    upsert_fn = upsert_fn or upsert_chunks
    create_fn = create_fn or create_task_collection

    workdir = state["workdir"]
    task_id = state["task_id"]

    # Chunk the repository
    chunks = chunk_fn(workdir)

    # Ensure collection exists (even if empty chunks)
    create_fn(task_id)

    # If chunks are empty, return early
    if not chunks:
        return {}

    # Extract text and embed
    texts = [ch.text for ch in chunks]
    vectors = embed_fn(texts)

    # Upsert chunks into collection
    upsert_fn(task_id, chunks, vectors)

    return {}
