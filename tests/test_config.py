import pytest


def test_settings_loads():
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    os.environ.setdefault("TAVILY_API_KEY", "tvly-test")
    os.environ.setdefault("SERPAPI_API_KEY", "serp-test")
    os.environ.setdefault("CODEBASE_PATH", "/tmp/fake-codebase")

    from config import settings
    assert settings.openai_model
    assert settings.codebase_path


def test_get_llm_returns_singleton():
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    os.environ.setdefault("TAVILY_API_KEY", "tvly-test")
    os.environ.setdefault("SERPAPI_API_KEY", "serp-test")
    os.environ.setdefault("CODEBASE_PATH", "/tmp/fake-codebase")

    from services.llm import get_llm
    llm1 = get_llm()
    llm2 = get_llm()
    assert llm1 is llm2
