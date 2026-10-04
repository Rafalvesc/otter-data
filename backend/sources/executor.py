"""Executes validated SELECTs against a connected source (never the sample analytics database)."""

import asyncio
import logging
from collections.abc import Callable
from functools import partial
from time import perf_counter
from typing import Any
from uuid import uuid4

from backend.config import Settings
from backend.models.query import QueryCode, QueryResult
from backend.sources.engines import Connection, SourceError, run_query
from backend.tools.sql_validator import SQLValidator

logger = logging.getLogger(__name__)

STARTED_MESSAGE = "Consulta iniciada; execução ainda não concluída."


def finish_query(started: float, log: logging.Logger | None, event: str, **fields) -> QueryResult:
    """The result with its duration. Logs carry metadata only: no SQL, values, rows,
    credentials or driver messages."""
    result = QueryResult(duration_ms=round((perf_counter() - started) * 1000, 3), **fields)
    if log:
        log.info(
            event,
            extra={
                "request_id": result.request_id,
                "query_status": result.status,
                "query_code": result.code.value,
                "duration_ms": result.duration_ms,
                "row_count": result.row_count,
                "truncated": result.truncated,
            },
        )
    return result


class SourceExecutor:
    def __init__(self, settings: Settings, validator: SQLValidator, connection: Connection):
        self._settings = settings
        self._validator = validator
        self._connection = connection

    async def execute_async(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
        *,
        request_id: str | None = None,
        on_attempt: Callable[[QueryResult], None] | None = None,
    ) -> QueryResult:
        started = perf_counter()
        request_id = request_id or str(uuid4())
        finish = partial(
            finish_query, started, logger, "source_query_finished", request_id=request_id
        )
        prepared = self._validator.prepare(sql, parameters)
        validation = prepared.validation
        if not validation.allowed:
            return finish(status="denied", code=validation.code, message=validation.message)
        # Trusted wrapper (no quoting, valid in every supported dialect); +1 row detects truncation.
        executed_sql = (
            f"SELECT * FROM ({validation.normalized_sql}) AS otter_result "
            f"LIMIT {self._settings.max_rows + 1}"
        )
        common = dict(
            sql=executed_sql,
            sources=validation.sources,
            parameter_names=validation.parameter_names,
            query_attempted=True,
        )
        if on_attempt:
            on_attempt(
                finish_query(
                    started,
                    None,
                    "",
                    request_id=request_id,
                    status="error",
                    code=QueryCode.TIMEOUT,
                    message=STARTED_MESSAGE,
                    **common,
                )
            )
        try:
            result = await asyncio.to_thread(
                run_query,
                self._connection,
                executed_sql,
                prepared.parameter_values,
                timeout=self._settings.query_timeout_seconds,
                max_rows=self._settings.max_rows,
                max_bytes=self._settings.max_result_bytes,
            )
        except SourceError as error:
            return finish(
                status="error",
                code=error.code,
                message=error.message,
                retry_hint=error.hint,
                **common,
            )
        return finish(
            status="success",
            code=QueryCode.OK,
            message="Consulta executada.",
            columns=result.columns,
            rows=result.rows,
            row_count=len(result.rows),
            result_bytes=result.size,
            truncated=result.truncation is not None,
            truncation_reason=result.truncation,
            **common,
        )
