from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel


class ProviderError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ProviderReply:
    value: BaseModel
    input_tokens: int = 0
    output_tokens: int = 0
    usage_known: bool = True


class LLMProvider(Protocol):
    name: str
    model: str | None
    is_demo: bool

    async def complete(
        self, schema: type[BaseModel], instructions: str, payload: dict[str, Any]
    ) -> ProviderReply: ...
