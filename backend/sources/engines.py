"""Read-only connections to connected sources.

Every session is forced read-only and gets a server-side statement timeout before any SQL runs.
These are defense in depth: the validator already allows only a single approved SELECT, and users
are told to connect with an account that has read permission only.
"""

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import psycopg
import pymysql
import pymysql.cursors

from backend.models.query import QueryCode
from backend.models.serialization import serialize_value
from backend.sources.catalog import (
    DUCKDB_COLUMNS,
    MYSQL_COLUMNS,
    MYSQL_FOREIGN_KEYS,
    POSTGRES_COLUMNS,
    POSTGRES_FOREIGN_KEYS,
    build_catalog,
)
from backend.sources.models import Catalog
from backend.tools.execution_hints import duckdb_hint, mysql_hint, postgres_hint

MYSQL_TIMEOUT_ERROR = 3024  # ER_QUERY_TIMEOUT: max_execution_time exceeded


class SourceError(Exception):
    def __init__(self, code: QueryCode, message: str, hint: str | None = None):
        self.code = code
        self.message = message
        self.hint = hint  # fixed text from backend.tools.execution_hints, never the driver message
        super().__init__(message)


def timed_out() -> SourceError:
    return SourceError(QueryCode.TIMEOUT, "A consulta excedeu o tempo permitido.")


def failed(hint: str | None) -> SourceError:
    return SourceError(
        QueryCode.EXECUTION_ERROR, "A consulta aprovada falhou durante a execução.", hint
    )


@dataclass(frozen=True)
class Connection:
    kind: str
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None
    path: Path | None = None


@dataclass
class Result:
    columns: list[str]
    rows: list[dict[str, Any]]
    size: int
    truncation: str | None


def read_rows(fetchmany, columns: list[str], max_rows: int, max_bytes: int) -> Result:
    rows: list[dict[str, Any]] = []
    size = 2
    while True:
        batch = fetchmany(64)
        if not batch:
            return Result(columns, rows, size, None)
        for values in batch:
            if len(rows) >= max_rows:
                return Result(columns, rows, size, "row_limit")
            row = serialize_value(dict(zip(columns, values, strict=True)))
            encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            addition = len(encoded.encode("utf-8")) + (1 if rows else 0)
            if size + addition > max_bytes:
                return Result(columns, rows, size, "byte_limit")
            rows.append(row)
            size += addition


# ---------------------------------------------------------------- PostgreSQL


@contextmanager
def _postgres(connection: Connection, timeout_seconds: int):
    try:
        conn = psycopg.connect(
            host=connection.host,
            port=connection.port,
            dbname=connection.database,
            user=connection.user,
            password=connection.password,
            connect_timeout=5,
            options="-c default_transaction_read_only=on",
        )
    except psycopg.OperationalError:
        raise SourceError(
            QueryCode.CONNECTION_ERROR,
            "Não foi possível conectar ao PostgreSQL; confira host, porta, usuário e senha.",
        ) from None
    try:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            # Fixed control statements; the value is an int bounded by settings.
            conn.execute(f"SET LOCAL statement_timeout = {int(timeout_seconds * 1000)}")
            conn.execute("SET LOCAL lock_timeout = '2s'")
            yield conn
    finally:
        conn.close()


def _postgres_query(connection, sql, values, timeout, max_rows, max_bytes) -> Result:
    try:
        with _postgres(connection, timeout) as conn:
            conn.execute("SET LOCAL search_path = pg_catalog")
            with psycopg.RawServerCursor(conn, "otter_result") as cursor:
                cursor.execute(sql, list(values) or None)
                columns = [column.name for column in cursor.description]
                return read_rows(cursor.fetchmany, columns, max_rows, max_bytes)
    except psycopg.errors.QueryCanceled:
        raise timed_out() from None
    except psycopg.Error as error:
        raise failed(postgres_hint(error)) from None


def _postgres_catalog(connection, schema, timeout) -> Catalog:
    with _postgres(connection, timeout) as conn:
        columns = conn.execute(POSTGRES_COLUMNS, (schema,)).fetchall()
        keys = conn.execute(POSTGRES_FOREIGN_KEYS, (schema,)).fetchall()
    return build_catalog(columns, keys)


# ---------------------------------------------------------------- MySQL


@contextmanager
def _mysql(connection: Connection, timeout_seconds: int, *, streaming: bool = False):
    try:
        conn = pymysql.connect(
            host=connection.host,
            port=connection.port,
            user=connection.user,
            password=connection.password or "",
            database=connection.database,
            connect_timeout=5,
            read_timeout=timeout_seconds + 5,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.SSCursor if streaming else pymysql.cursors.Cursor,
            autocommit=False,
        )
    except pymysql.err.OperationalError:
        raise SourceError(
            QueryCode.CONNECTION_ERROR,
            "Não foi possível conectar ao MySQL; confira host, porta, usuário e senha.",
        ) from None
    try:
        with conn.cursor() as control:
            control.execute("SET SESSION TRANSACTION READ ONLY")
            control.execute("SET SESSION max_execution_time = %s", (int(timeout_seconds * 1000),))
            control.execute("START TRANSACTION READ ONLY")
        yield conn
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def _mysql_query(connection, sql, values, timeout, max_rows, max_bytes) -> Result:
    try:
        with _mysql(connection, timeout, streaming=True) as conn, conn.cursor() as cursor:
            cursor.execute(sql, tuple(values))
            columns = [column[0] for column in cursor.description]
            return read_rows(cursor.fetchmany, columns, max_rows, max_bytes)
    except pymysql.err.MySQLError as error:
        if error.args and error.args[0] == MYSQL_TIMEOUT_ERROR:
            raise timed_out() from None
        raise failed(mysql_hint(error)) from None


def _mysql_catalog(connection, schema, timeout) -> Catalog:
    with _mysql(connection, timeout) as conn, conn.cursor() as cursor:
        cursor.execute(MYSQL_COLUMNS, (schema,))
        columns = cursor.fetchall()
        cursor.execute(MYSQL_FOREIGN_KEYS, (schema,))
        keys = cursor.fetchall()
    return build_catalog(columns, keys)


# ---------------------------------------------------------------- DuckDB (imported CSV)


def _duckdb_query(connection, sql, values, timeout, max_rows, max_bytes) -> Result:
    try:
        conn = duckdb.connect(str(connection.path), read_only=True)
    except duckdb.Error:
        raise SourceError(
            QueryCode.CONNECTION_ERROR, "Não foi possível abrir a base importada."
        ) from None
    # DuckDB has no statement timeout; interrupt the connection when the budget runs out.
    timer = threading.Timer(timeout, conn.interrupt)
    timer.start()
    try:
        cursor = conn.execute(sql, list(values))
        columns = [column[0] for column in cursor.description]
        return read_rows(cursor.fetchmany, columns, max_rows, max_bytes)
    except duckdb.InterruptException:
        raise timed_out() from None
    except duckdb.Error as error:
        raise failed(duckdb_hint(error)) from None
    finally:
        timer.cancel()
        conn.close()


def _duckdb_catalog(connection, schema, timeout) -> Catalog:
    conn = duckdb.connect(str(connection.path), read_only=True)
    try:
        return build_catalog(conn.execute(DUCKDB_COLUMNS).fetchall())
    finally:
        conn.close()


QUERY = {"postgres": _postgres_query, "mysql": _mysql_query, "csv": _duckdb_query}
CATALOG = {"postgres": _postgres_catalog, "mysql": _mysql_catalog, "csv": _duckdb_catalog}


def run_query(
    connection: Connection, sql: str, values, *, timeout: int, max_rows: int, max_bytes: int
) -> Result:
    return QUERY[connection.kind](connection, sql, values, timeout, max_rows, max_bytes)


def discover(connection: Connection, schema: str, *, timeout: int = 10) -> Catalog:
    try:
        return CATALOG[connection.kind](connection, schema, timeout)
    except SourceError:
        raise
    except (psycopg.Error, pymysql.err.MySQLError, duckdb.Error):
        raise SourceError(
            QueryCode.EXECUTION_ERROR,
            "Conectou, mas não foi possível ler a estrutura do banco com esse usuário.",
        ) from None
