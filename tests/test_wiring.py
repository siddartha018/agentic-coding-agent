"""End-to-end wiring smoke test. Validates graph + app instantiation without live network."""

from __future__ import annotations


def test_can_import_and_build_graph(monkeypatch):
    """Verify build_graph() instantiates without live network calls."""
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.setenv("QDRANT_API_KEY", "x")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")

    from coding_agent.config import get_settings
    get_settings.cache_clear()

    from coding_agent.graph import build_graph
    graph = build_graph()
    assert graph is not None


def test_can_build_app(monkeypatch):
    """Verify build_app() returns a FastAPI instance with expected title and real nodes wired."""
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.setenv("QDRANT_API_KEY", "x")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")

    from coding_agent.config import get_settings
    get_settings.cache_clear()

    from coding_agent.api import build_app
    from coding_agent.graph import build_graph

    app = build_app()
    assert app.title  # non-empty
    assert app.title == "coding-agent"

    # Verify the graph is properly wired with real nodes
    graph = build_graph()
    nodes = list(graph.get_graph().nodes.keys())
    assert {"index", "plan", "act", "observe", "repair"}.issubset(set(nodes))
