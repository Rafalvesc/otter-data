from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

SourceKind = Literal["sample", "postgres", "mysql", "csv"]
SOURCE_ID = r"^[a-z0-9][a-z0-9-]{0,63}$"
IDENTIFIER = r"^[A-Za-z_][A-Za-z0-9_$]{0,63}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceConfig(StrictModel):
    """Persisted connection settings. Never contains a password."""

    id: str = Field(pattern=SOURCE_ID)
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["postgres", "mysql", "csv"]
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str | None = Field(default=None, max_length=128)
    user: str | None = Field(default=None, max_length=128)
    schema_name: str = Field(pattern=IDENTIFIER)
    allow_rows_to_llm: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class DatabaseSourceInput(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["postgres", "mysql"]
    host: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9.\-_:\[\]]+$")
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1, max_length=128, pattern=IDENTIFIER)
    user: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(max_length=512)
    schema_name: str | None = Field(default=None, pattern=IDENTIFIER)
    allow_rows_to_llm: bool = False


class SourceUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    allow_rows_to_llm: bool | None = None


class CatalogTable(StrictModel):
    columns: dict[str, str]
    relationships: dict[str, str] = Field(default_factory=dict)
    hidden_columns: list[str] = Field(default_factory=list)


class Catalog(StrictModel):
    tables: dict[str, CatalogTable]
    skipped: list[str] = Field(default_factory=list)
    discovered_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class SourceSummary(StrictModel):
    id: str
    name: str
    kind: SourceKind
    location: str
    schema_name: str
    allow_rows_to_llm: bool
    metrics: bool
    tables: int
    columns: int
    hidden_columns: int
    built_in: bool


class SourceDetail(SourceSummary):
    catalog: dict[str, CatalogTable]
    skipped: list[str]
