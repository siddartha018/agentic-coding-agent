import os
import pytest

# Set up test env vars BEFORE any imports that might trigger Settings()
os.environ.setdefault("GROQ_API_KEY", "test-groq")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini")
os.environ.setdefault("QDRANT_URL", ":memory:")
os.environ.setdefault("QDRANT_API_KEY", "test-qdrant")
os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
os.environ.pop("LANGFUSE_SECRET_KEY", None)


@pytest.fixture(autouse=True)
def _test_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    monkeypatch.setenv("QDRANT_API_KEY", "test-qdrant")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    from coding_agent.config import get_settings
    get_settings.cache_clear()
    from coding_agent import obs
    obs._INITIALIZED = False
    obs._ENABLED = False
