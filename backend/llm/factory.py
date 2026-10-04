from backend.config import Settings
from backend.llm.base import LLMProvider
from backend.llm.catalog import ModelOption
from backend.llm.demo import DemoProvider
from backend.llm.ollama_provider import OllamaProvider


def build_provider(settings: Settings, option: ModelOption | None = None) -> LLMProvider:
    provider = option.provider if option else settings.llm_provider
    model = option.model if option else None
    if provider == "demo":
        return DemoProvider()
    return OllamaProvider(settings, model)
