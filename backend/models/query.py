from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class QueryCode(StrEnum):
    OK = "ok"
    INVALID_SQL = "invalid_sql"
    MULTIPLE_STATEMENTS = "multiple_statements"
    READ_ONLY_REQUIRED = "read_only_required"
    UNSUPPORTED_SQL = "unsupported_sql"
    RELATION_NOT_ALLOWED = "relation_not_allowed"
    COLUMN_NOT_ALLOWED = "column_not_allowed"
    FUNCTION_NOT_ALLOWED = "function_not_allowed"
    WILDCARD_NOT_ALLOWED = "wildcard_not_allowed"
    JOIN_NOT_ALLOWED = "join_not_allowed"
    DUPLICATED_AGGREGATE = "duplicated_aggregate"
    COMPLEXITY_LIMIT = "complexity_limit"
    INVALID_PARAMETERS = "invalid_parameters"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    EXECUTION_ERROR = "execution_error"


class ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    code: QueryCode
    message: str
    normalized_sql: str | None = None
    sources: tuple[str, ...] = ()
    parameter_names: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    # Whether the model may rewrite a rejected query once (never for writes or sensitive fields).
    repairable: bool = False


class QueryResult(BaseModel):
    request_id: str
    status: Literal["success", "denied", "error"]
    code: QueryCode
    message: str
    sql: str | None = None
    sources: tuple[str, ...] = ()
    parameter_names: tuple[str, ...] = ()
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    result_bytes: int = 2
    truncated: bool = False
    truncation_reason: Literal["row_limit", "byte_limit"] | None = None
    duration_ms: float
    query_attempted: bool = False
    # Fixed, data-free advice for a rewrite after a database error (backend.tools.execution_hints).
    retry_hint: str | None = None
