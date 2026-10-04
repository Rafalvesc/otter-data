import asyncio
import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from backend.agents.analyst import AnalystService
from backend.api.sources import get_source_registry
from backend.config import get_settings
from backend.llm.catalog import ModelCatalog
from backend.llm.factory import build_provider
from backend.models.analysis import AskRequest, AskResponse

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@lru_cache
def get_model_catalog() -> ModelCatalog:
    return ModelCatalog(get_settings())


@lru_cache
def get_analyst_service() -> AnalystService:
    settings = get_settings()
    return AnalystService(
        settings,
        build_provider(settings),
        sources=get_source_registry(),
        models=get_model_catalog(),
    )


@router.get("/models")
def list_models(catalog: Annotated[ModelCatalog, Depends(get_model_catalog)]) -> dict:
    return {"default": catalog.default_id, "models": [m.public() for m in catalog.options()]}


@router.get("/status")
def analysis_status():
    settings = get_settings()
    return {
        "provider": settings.llm_provider,
        "configured": True,  # Ollama needs no key; availability shows up per request
        "model": settings.llm_model,
        "demo_mode": settings.llm_provider == "demo",
        "max_queries": 1,
        "max_llm_calls": settings.max_llm_calls,
        "request_timeout_seconds": settings.request_timeout_seconds,
    }


@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    response: Response,
    service: Annotated[AnalystService, Depends(get_analyst_service)],
) -> AskResponse:
    result = await service.ask(request)
    response.status_code = status_code_for(result)
    return result


@router.post("/ask/stream")
async def ask_stream(
    request: AskRequest,
    service: Annotated[AnalystService, Depends(get_analyst_service)],
) -> StreamingResponse:
    """Same analysis as /ask, as NDJSON: one {"type": "stage"} line per finished step (name
    only), then {"type": "result"} with the full response and its HTTP-equivalent status."""

    async def events() -> AsyncIterator[str]:
        stages: asyncio.Queue[str] = asyncio.Queue()
        task = asyncio.create_task(service.ask(request, on_stage=stages.put))
        try:
            while True:
                waiter = asyncio.ensure_future(stages.get())
                done, _ = await asyncio.wait({waiter, task}, return_when=asyncio.FIRST_COMPLETED)
                if waiter in done:
                    yield json.dumps({"type": "stage", "stage": waiter.result()}) + "\n"
                    continue
                waiter.cancel()
                while not stages.empty():
                    yield json.dumps({"type": "stage", "stage": stages.get_nowait()}) + "\n"
                break
            result = task.result()
            payload = {
                "type": "result",
                "status": status_code_for(result),
                "data": result.model_dump(mode="json"),
            }
            yield json.dumps(payload, ensure_ascii=False) + "\n"
        finally:
            if not task.done():
                task.cancel()  # the client went away: stop the analysis

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def status_code_for(result: AskResponse) -> int:
    if result.status == "denied":
        return 403
    if result.status == "error":
        if result.code in {"timeout", "request_timeout", "provider_timeout"}:
            return 504
        if result.code in {
            "provider_error",
            "provider_authentication_error",
            "provider_permission_error",
            "provider_model_unavailable",
            "provider_quota_exceeded",
            "provider_rate_limited",
            "provider_connection_error",
            "provider_unavailable",
            "source_unavailable",
            "model_unavailable",
            "connection_error",
            "busy",
        }:
            return 503
        return 502
    return 200
