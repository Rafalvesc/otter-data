import json
import re

import httpx2
from pydantic import BaseModel, ValidationError

from backend.config import Settings
from backend.llm.base import ProviderError, ProviderReply
from backend.llm.catalog import is_cloud_model

JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
OUTPUT_CONTRACT = """
Responda somente com um objeto JSON válido que siga exatamente este JSON Schema.
Não use markdown, blocos de código, comentários nem texto fora do objeto.
Inclua todas as propriedades obrigatórias; use null quando o schema permitir.
JSON Schema:
"""


class OllamaProvider:
    """Adapter for the local Ollama daemon; `-cloud` models are relayed by it to ollama.com."""

    name = "ollama"
    is_demo = False

    def __init__(self, settings: Settings, model: str | None = None):
        self.model = model or settings.ollama_model
        self.local = not is_cloud_model(self.model)
        self.timeout_seconds = (
            settings.local_llm_timeout_seconds if self.local else settings.llm_timeout_seconds
        )
        # Hosted models have large windows; local ones get an explicit one (see config).
        self._options = {"temperature": 0} | (
            {"num_ctx": settings.local_context_tokens} if self.local else {}
        )
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._timeout = self.timeout_seconds

    async def complete(
        self, schema: type[BaseModel], instructions: str, payload: dict
    ) -> ProviderReply:
        json_schema = schema.model_json_schema()
        body = {
            "model": self.model,
            "stream": False,
            "think": False,
            # Cloud models may ignore `format`, so the contract is repeated in the prompt and
            # the reply is always validated by Pydantic below.
            "format": json_schema,
            "options": self._options,
            "messages": [
                {
                    "role": "system",
                    "content": instructions.strip()
                    + "\n"
                    + OUTPUT_CONTRACT
                    + json.dumps(json_schema, ensure_ascii=False),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        try:
            async with httpx2.AsyncClient(
                base_url=self._base_url, timeout=self._timeout, follow_redirects=False
            ) as client:
                response = await client.post("/api/chat", json=body)
        except httpx2.TimeoutException:
            raise ProviderError(
                "provider_timeout", "O provedor excedeu o tempo permitido."
            ) from None
        except httpx2.HTTPError:
            raise ProviderError(
                "provider_connection_error",
                "Não foi possível conectar ao Ollama; confira se ele está em execução "
                "e o valor de OLLAMA_BASE_URL.",
            ) from None
        if response.status_code != 200:
            code, message = classify_status(response.status_code)
            raise ProviderError(code, message)
        try:
            data = response.json()
            content = data["message"]["content"]
            parsed = schema.model_validate_json(extract_json(content))
        except (ValidationError, ValueError, KeyError, TypeError):
            raise ProviderError(
                "invalid_model_output", "O modelo retornou uma saída inválida."
            ) from None
        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
        return ProviderReply(
            value=parsed,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            usage_known=isinstance(input_tokens, int) and isinstance(output_tokens, int),
        )


def extract_json(content: str) -> str:
    text = content.strip()
    fenced = JSON_FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Resposta sem objeto JSON.")
    return text[start : end + 1]


def classify_status(status: int) -> tuple[str, str]:
    # Only fixed messages escape the adapter; never return provider bodies or headers.
    if status in (401, 403):
        return (
            "provider_authentication_error",
            "O Ollama recusou o acesso ao modelo cloud; execute `ollama signin`.",
        )
    if status == 404:
        return (
            "provider_model_unavailable",
            "O modelo configurado não está disponível no Ollama; confira OLLAMA_MODEL.",
        )
    if status == 429:
        return (
            "provider_rate_limited",
            "O Ollama limitou o uso do plano atual; aguarde e tente depois.",
        )
    if status in (400, 422):
        return (
            "provider_invalid_request",
            "O Ollama rejeitou o formato da solicitação; a integração precisa de revisão.",
        )
    return "provider_unavailable", "O Ollama está indisponível; tente novamente mais tarde."
