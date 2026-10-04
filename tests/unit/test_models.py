import asyncio

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.agents.analyst import AnalystService
from backend.api.analysis import get_model_catalog
from backend.config import Settings
from backend.llm.base import ProviderReply
from backend.llm.catalog import ModelCatalog
from backend.llm.factory import build_provider
from backend.llm.ollama_provider import OllamaProvider
from backend.main import app
from backend.models.analysis import AskRequest, ChatReply
from backend.runtime import create_loop
from tests.helpers import ScriptedProvider, intent, run

TAGS = [
    {
        "name": "qwen2.5:3b",
        "size": 1_929_912_432,
        "details": {"parameter_size": "3.1B", "family": "qwen2"},
    },
    {"name": "nomic-embed-text:latest", "size": 274_302_450, "details": {"family": "nomic-bert"}},
    {"name": "gpt-oss:120b-cloud", "remote_host": "https://ollama.com:443", "details": {}},
]


def settings(**values):
    return Settings(
        _env_file=None,
        analytics_password="offline-db-secret",
        llm_provider="ollama",
        **values,
    )


def catalog(tags=TAGS, **values):
    return ModelCatalog(settings(**values), fetch_tags=lambda base_url: tags)


def test_catalog_lists_cloud_and_local_models_and_skips_embeddings():
    options = catalog(ollama_models="qwen3-coder:480b-cloud").options()
    ids = [option.id for option in options]
    assert ids == [
        "ollama:gemma4:31b-cloud",
        "ollama:gpt-oss:120b-cloud",
        "ollama:qwen3-coder:480b-cloud",
        "ollama:qwen2.5:3b",
    ]
    local = options[-1]
    assert local.location == "local" and local.size == "1,8 GB" and local.parameters == "3.1B"
    assert all(option.location == "cloud" for option in options[:3])


def test_daemon_failures_keep_the_configured_cloud_models():
    def offline(base_url):
        raise httpx2.ConnectError("refused")

    options = ModelCatalog(settings(), fetch_tags=offline).options()
    assert [option.id for option in options] == ["ollama:gemma4:31b-cloud"]
    assert catalog().resolve("ollama:made-up:7b") is None


def test_local_models_get_their_own_timeouts():
    config = settings(local_llm_timeout_seconds=90, llm_timeout_seconds=20)
    local = build_provider(config, catalog().resolve("ollama:qwen2.5:3b"))
    cloud = build_provider(config, catalog().resolve("ollama:gemma4:31b-cloud"))
    assert isinstance(local, OllamaProvider) and local.local and local.timeout_seconds == 90
    assert not cloud.local and cloud.timeout_seconds == 20


def chat_intent():
    return intent(action="chat", metric=None, start_date=None, end_date=None)


def test_a_picked_model_answers_and_is_reported():
    picked = ScriptedProvider(chat_intent(), ChatReply(answer="Oi!", follow_ups=[]))
    picked.model, picked.local, picked.timeout_seconds = "qwen2.5:3b", True, 90
    default = ScriptedProvider()
    created = []

    def factory(option):
        created.append(option.id)
        return picked

    analyst = AnalystService(
        settings(local_request_timeout_seconds=300),
        default,
        models=catalog(),
        provider_factory=factory,
    )
    for _ in range(2):
        picked.values = [chat_intent(), ChatReply(answer="Oi!", follow_ups=[])]
        response = run(analyst.ask(AskRequest(question="oi", model="ollama:qwen2.5:3b")))
        assert response.status == "success" and response.model == "qwen2.5:3b"
    assert created == ["ollama:qwen2.5:3b"]  # providers are reused
    assert default.payloads == []


def test_unknown_model_is_refused_before_any_call():
    default = ScriptedProvider()
    analyst = AnalystService(settings(), default, models=catalog())
    response = run(analyst.ask(AskRequest(question="oi", model="ollama:not-installed:1b")))
    assert response.status == "error" and response.code == "model_unavailable"
    assert default.payloads == []


def test_each_provider_call_uses_that_provider_timeout():
    class Slow(ScriptedProvider):
        async def complete(self, schema, instructions, payload):
            await asyncio.sleep(0.5)
            return ProviderReply(value=chat_intent())

    slow = Slow()
    slow.model, slow.local, slow.timeout_seconds = "qwen2.5:3b", True, 0.1
    analyst = AnalystService(
        settings(), ScriptedProvider(), models=catalog(), provider_factory=lambda option: slow
    )
    response = run(analyst.ask(AskRequest(question="oi", model="ollama:qwen2.5:3b")))
    assert response.status == "error" and response.code == "provider_timeout"


@pytest.mark.parametrize(
    "model", ["ollama:../../etc", "ollama:x;rm -rf", "other:model", "qwen2.5:3b"]
)
def test_model_names_are_constrained(model):
    with pytest.raises(ValidationError):
        AskRequest(question="oi", model=model)


def test_models_endpoint():
    app.dependency_overrides[get_model_catalog] = lambda: catalog()
    try:
        with TestClient(app, backend_options={"loop_factory": create_loop}) as client:
            body = client.get("/api/v1/models").json()
    finally:
        app.dependency_overrides.clear()
    assert body["default"] == "ollama:gemma4:31b-cloud"
    assert {"id", "provider", "model", "location", "size", "parameters"} <= set(body["models"][0])
