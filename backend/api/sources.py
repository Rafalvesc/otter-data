"""Data source management. Passwords are accepted only on creation and never returned."""

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import Path as PathParam
from starlette.concurrency import run_in_threadpool

from backend.config import get_settings
from backend.sample.embedded import SAMPLE_NAME
from backend.sources.models import DatabaseSourceInput, SourceDetail, SourceSummary, SourceUpdate
from backend.sources.registry import SAMPLE_ID, RegistryError, SourceRegistry

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])
SOURCE_ID = r"^[a-z0-9][a-z0-9-]{0,63}$"
FILENAME = r"^[^\\/:*?\"<>|\x00-\x1f]{1,200}$"


@lru_cache
def get_source_registry() -> SourceRegistry:
    return SourceRegistry(get_settings())


Registry = Annotated[SourceRegistry, Depends(get_source_registry)]
SourceId = Annotated[str, PathParam(pattern=SOURCE_ID)]


def sample_summary() -> SourceSummary:
    embedded = get_settings().embedded_sample
    return SourceSummary(
        id=SAMPLE_ID,
        name=SAMPLE_NAME,
        kind="sample",
        location=(
            "Arquivo local (DuckDB) gerado no primeiro uso, somente leitura"
            if embedded
            else "PostgreSQL local (Docker), conta somente leitura"
        ),
        schema_name="main" if embedded else "analytics",
        allow_rows_to_llm=get_settings().narrative_enabled,
        metrics=not embedded,
        tables=6,
        columns=24 if embedded else 25,
        hidden_columns=0,
        built_in=True,
    )


def fail(error: RegistryError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=error.message)


async def receive_csv(request: Request) -> Path:
    """Stream the raw request body to a temporary file, enforcing the configured size limit."""
    limit = get_settings().csv_max_mb * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(413, f"O arquivo passa de {get_settings().csv_max_mb} MB.")
    handle = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)  # noqa: SIM115
    size = 0
    try:
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise HTTPException(413, f"O arquivo passa de {get_settings().csv_max_mb} MB.")
            handle.write(chunk)
    except BaseException:
        handle.close()
        Path(handle.name).unlink(missing_ok=True)
        raise
    handle.close()
    if size == 0:
        Path(handle.name).unlink(missing_ok=True)
        raise HTTPException(400, "O arquivo está vazio.")
    return Path(handle.name)


@router.get("")
def list_sources(registry: Registry) -> dict:
    return {"default": SAMPLE_ID, "sources": [sample_summary(), *registry.summaries()]}


@router.get("/{source_id}", response_model=SourceDetail)
def source_detail(source_id: SourceId, registry: Registry):
    try:
        return registry.detail(source_id)
    except RegistryError as error:
        raise fail(error) from None


@router.post("/database", response_model=SourceSummary, status_code=201)
async def add_database(data: DatabaseSourceInput, registry: Registry):
    try:
        return await run_in_threadpool(registry.add_database, data)
    except RegistryError as error:
        raise fail(error) from None


@router.post("/csv", response_model=SourceSummary, status_code=201)
async def add_csv(
    request: Request,
    registry: Registry,
    name: Annotated[str, Query(min_length=1, max_length=80)],
    filename: Annotated[str, Query(pattern=FILENAME)],
    allow_rows_to_llm: bool = False,
):
    path = await receive_csv(request)
    try:
        return await run_in_threadpool(registry.add_csv, name, filename, path, allow_rows_to_llm)
    except RegistryError as error:
        raise fail(error) from None
    finally:
        path.unlink(missing_ok=True)


@router.post("/{source_id}/csv", response_model=SourceSummary)
async def add_csv_table(
    source_id: SourceId,
    request: Request,
    registry: Registry,
    filename: Annotated[str, Query(pattern=FILENAME)],
):
    path = await receive_csv(request)
    try:
        return await run_in_threadpool(registry.add_csv_table, source_id, filename, path)
    except RegistryError as error:
        raise fail(error) from None
    finally:
        path.unlink(missing_ok=True)


@router.post("/{source_id}/refresh", response_model=SourceSummary)
async def refresh(source_id: SourceId, registry: Registry):
    try:
        return await run_in_threadpool(registry.refresh, source_id)
    except RegistryError as error:
        raise fail(error) from None


@router.patch("/{source_id}", response_model=SourceSummary)
def update(source_id: SourceId, data: SourceUpdate, registry: Registry):
    try:
        return registry.update(source_id, data)
    except RegistryError as error:
        raise fail(error) from None


@router.delete("/{source_id}", status_code=204)
def delete(source_id: SourceId, registry: Registry) -> None:
    try:
        registry.delete(source_id)
    except RegistryError as error:
        raise fail(error) from None
