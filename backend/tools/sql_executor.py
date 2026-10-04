"""The only entry point for executing model/user queries; always validates anew."""

import asyncio
import json
import logging
from collections.abc import Callable
from functools import partial
from time import perf_counter
from typing import Any
from uuid import uuid4

import psycopg

from backend.config import Settings
from backend.models.query import QueryCode, QueryResult
from backend.models.serialization import serialize_value
from backend.runtime import create_loop
from backend.sources.executor import STARTED_MESSAGE, finish_query
from backend.tools.execution_hints import postgres_hint
from backend.tools.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


class SQLExecutor:
    def __init__(self, settings: Settings):
        self._settings = Settings.model_validate(settings.model_dump())
        self._validator = SQLValidator()

    def execute(self, sql: str, parameters: dict[str, Any] | None = None) -> QueryResult:
        with asyncio.Runner(loop_factory=create_loop) as runner:
            return runner.run(self.execute_async(sql, parameters))

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
            finish_query, started, logger, "analytics_query_finished", request_id=request_id
        )
        prepared = self._validator.prepare(sql, parameters)
        validation = prepared.validation
        if not validation.allowed:
            return finish(status="denied", code=validation.code, message=validation.message)
        # The wrapper is trusted executor code, not model SQL. One extra row detects truncation.
        executed_sql = (
            f'SELECT * FROM ({validation.normalized_sql}) AS "_datapilot_result" '
            f"LIMIT {self._settings.max_rows + 1}"
        )
        scope = dict(sources=validation.sources, parameter_names=validation.parameter_names)
        common = dict(scope, sql=executed_sql, query_attempted=True)
        attempted = False
        hint = None
        try:
            url = self._settings.analytics_url
            async with await psycopg.AsyncConnection.connect(
                host=url.host,
                port=url.port,
                dbname=url.database,
                user=url.username,
                password=url.password,
                connect_timeout=5,
                autocommit=True,
            ) as connection:
                async with connection.transaction():
                    await connection.execute("SET TRANSACTION READ ONLY")
                    # Fixed control statements are not user SQL. Settings are bounded by Pydantic.
                    timeout_ms = self._settings.query_timeout_seconds * 1000
                    await connection.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
                    await connection.execute("SET LOCAL lock_timeout = '2s'")
                    await connection.execute("SET LOCAL search_path = pg_catalog")
                    await connection.execute("SET LOCAL timezone = 'America/Sao_Paulo'")
                    deadline = perf_counter() + self._settings.query_timeout_seconds
                    async with psycopg.AsyncRawServerCursor(
                        connection, "datapilot_result"
                    ) as cursor:
                        attempted = True
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
                        await cursor.execute(executed_sql, prepared.parameter_values or None)
                        columns = [column.name for column in cursor.description]
                        rows, size, reason = await self._read_result(cursor, columns, deadline)
            return finish(
                status="success",
                code=QueryCode.OK,
                message="Consulta executada.",
                columns=columns,
                rows=rows,
                row_count=len(rows),
                result_bytes=size,
                truncated=reason is not None,
                truncation_reason=reason,
                **common,
            )
        except asyncio.CancelledError:
            if attempted and on_attempt:
                on_attempt(
                    finish(
                        status="error",
                        code=QueryCode.TIMEOUT,
                        message="Execução cancelada pelo prazo ou cancelamento da solicitação.",
                        **common,
                    )
                )
            raise
        except (psycopg.errors.QueryCanceled, TimeoutError):
            code, message = QueryCode.TIMEOUT, "A consulta excedeu o tempo permitido."
        except psycopg.OperationalError:
            code, message = (
                QueryCode.CONNECTION_ERROR,
                "Não foi possível acessar o banco analítico.",
            )
        except (psycopg.Error, ValueError, OverflowError) as error:
            code, message = (
                QueryCode.EXECUTION_ERROR,
                "A consulta aprovada falhou durante a execução.",
            )
            hint = postgres_hint(error)
        return finish(
            status="error",
            code=code,
            message=message,
            retry_hint=hint,
            **(common if attempted else scope),
        )

    async def _read_result(self, cursor, columns, deadline):
        rows = []
        size = 2  # UTF-8 JSON array delimiters; this budget covers rows, not the entire envelope.
        while True:
            remaining_ms = int((deadline - perf_counter()) * 1000)
            if remaining_ms < 1:
                raise TimeoutError("Query time budget exhausted")
            await cursor.connection.execute(f"SET LOCAL statement_timeout = {remaining_ms}")
            batch = await cursor.fetchmany(32)
            if not batch:
                break
            for values in batch:
                if len(rows) >= self._settings.max_rows:
                    return rows, size, "row_limit"
                row = serialize_value(dict(zip(columns, values, strict=True)))
                encoded = json.dumps(
                    row, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                )
                addition = len(encoded.encode("utf-8")) + (1 if rows else 0)
                if size + addition > self._settings.max_result_bytes:
                    return rows, size, "byte_limit"
                rows.append(row)
                size += addition
        return rows, size, None
