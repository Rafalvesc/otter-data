import json
from unittest.mock import patch

import httpx2
import pytest

from backend.api.analysis import analysis_status
from backend.config import Settings
from backend.llm.base import ProviderError
from backend.llm.factory import build_provider
from backend.llm.ollama_provider import OllamaProvider, extract_json
from backend.models.analysis import IntentDecision
from tests.helpers import intent, run

REAL_CLIENT = httpx2.AsyncClient


def settings(**values):
    return Settings(
        _env_file=None, analytics_password="offline-db-secret", llm_provider="ollama", **values
    )


def mocked(handle):
    def factory(**kwargs):
        return REAL_CLIENT(**kwargs, transport=httpx2.MockTransport(handle))

    return patch("backend.llm.ollama_provider.httpx2.AsyncClient", side_effect=factory)


def ollama_reply(content, **extra):
    return httpx2.Response(
        200,
        json={
            "model": "gemma4:31b",
            "message": {"role": "assistant", "content": content},
            "done": True,
            **extra,
        },
    )


def test_adapter_sends_schema_in_prompt_and_parses_structured_output():
    requests = []

    async def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        assert request.url == "http://127.0.0.1:11434/api/chat"
        assert body["model"] == "gemma4:31b-cloud" and body["stream"] is False
        assert body["format"]["title"] == "IntentDecision"
        assert '"clarification_question"' in body["messages"][0]["content"]
        assert "offline-db-secret" not in request.content.decode()
        return ollama_reply(intent().model_dump_json(), prompt_eval_count=10, eval_count=5)

    with mocked(handle):
        reply = run(
            OllamaProvider(settings()).complete(IntentDecision, "Instructions", {"q": "test"})
        )
    assert reply.value == intent()
    assert reply.input_tokens == 10 and reply.output_tokens == 5 and reply.usage_known
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("model", "options"),
    [
        ("qwen2.5:7b", {"temperature": 0, "num_ctx": 16384}),
        ("gemma4:31b-cloud", {"temperature": 0}),
    ],
)
def test_local_models_get_a_context_window_that_fits_the_instructions(model, options):
    sent = []

    async def handle(request):
        sent.append(json.loads(request.content)["options"])
        return ollama_reply(intent().model_dump_json())

    with mocked(handle):
        run(OllamaProvider(settings(), model).complete(IntentDecision, "Instructions", {}))
    assert sent == [options]


def test_markdown_fenced_json_is_accepted_and_missing_usage_is_flagged():
    async def handle(request):
        return ollama_reply("```json\n" + intent().model_dump_json(indent=2) + "\n```")

    with mocked(handle):
        reply = run(OllamaProvider(settings()).complete(IntentDecision, "Instructions", {}))
    assert reply.value == intent() and not reply.usage_known


@pytest.mark.parametrize(
    "content",
    ["A capital é Paris.", '{"action": "analyze"}', '{"action": "drop", "extra": 1}'],
)
def test_output_outside_contract_is_rejected(content):
    async def handle(request):
        return ollama_reply(content)

    with mocked(handle):
        with pytest.raises(ProviderError) as error:
            run(OllamaProvider(settings()).complete(IntentDecision, "Instructions", {}))
    assert error.value.code == "invalid_model_output"


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (401, "provider_authentication_error"),
        (404, "provider_model_unavailable"),
        (429, "provider_rate_limited"),
        (400, "provider_invalid_request"),
        (500, "provider_unavailable"),
    ],
)
def test_http_error_is_sanitized_and_never_retried(status, expected_code):
    calls = []

    async def handle(request):
        calls.append(request)
        return httpx2.Response(status, json={"error": "private-marker-do-not-log"})

    with mocked(handle):
        with pytest.raises(ProviderError) as error:
            run(OllamaProvider(settings()).complete(IntentDecision, "Instructions", {}))
    assert error.value.code == expected_code and "private-marker" not in str(error.value)
    assert len(calls) == 1


def test_daemon_offline_is_a_connection_error():
    async def handle(request):
        raise httpx2.ConnectError("refused", request=request)

    with mocked(handle):
        with pytest.raises(ProviderError) as error:
            run(OllamaProvider(settings()).complete(IntentDecision, "Instructions", {}))
    assert error.value.code == "provider_connection_error"


def test_extract_json_requires_an_object():
    assert extract_json('Resposta: {"a": 1} fim') == '{"a": 1}'
    with pytest.raises(ValueError):
        extract_json("sem json")


def test_factory_and_status_select_ollama_without_api_key(monkeypatch):
    config = settings()
    assert isinstance(build_provider(config), OllamaProvider)
    monkeypatch.setattr("backend.api.analysis.get_settings", lambda: config)
    status = analysis_status()
    assert status["provider"] == "ollama" and status["model"] == "gemma4:31b-cloud"
    assert status["configured"] and not status["demo_mode"]


def test_base_url_must_be_plain_http_origin():
    with pytest.raises(ValueError):
        settings(ollama_base_url="file:///etc/passwd")
