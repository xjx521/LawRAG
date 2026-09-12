from ..app.config import get_settings


def test_a(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    assert get_settings().llm_provider == "deepseek"  # ✅ 过了


def test_b(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert get_settings().llm_provider == "ollama"  # ❓ 这里拿到什么？
