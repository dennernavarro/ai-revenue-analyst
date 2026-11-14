import pytest

from revenue_analyst.llm import OPENROUTER_BASE_URL, init_model


def test_openrouter_requires_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        init_model("openrouter:anthropic/claude-haiku-4.5")


def test_openrouter_builds_openai_client_with_custom_base_url(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    model = init_model("openrouter:anthropic/claude-haiku-4.5")
    assert model.model_name == "anthropic/claude-haiku-4.5"
    assert model.openai_api_base == OPENROUTER_BASE_URL
