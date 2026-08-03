from coding_agent.config import get_settings
from coding_agent.llm import LLM, get_llm


def test_settings_loads_from_env():
    s = get_settings()
    assert s.groq_api_key == "test-groq"
    assert s.gemini_api_key == "test-gemini"
    assert s.coding_agent_max_iterations == 4


def test_get_llm_returns_singleton():
    a = get_llm()
    b = get_llm()
    assert a is b
    assert isinstance(a, LLM)


def test_llm_model_alias_map():
    llm = get_llm()
    assert llm._resolve("primary") == ("groq", "llama-3.3-70b-versatile")
    assert llm._resolve("fast") == ("groq", "llama-3.1-8b-instant")
    assert llm._resolve("fallback") == ("gemini", "gemini-flash-latest")
