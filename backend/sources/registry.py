"""Registry of connected sources.

Configs and discovered catalogs live in the app data folder; passwords live in the OS credential
vault (Windows Credential Manager through keyring) and are never written to disk, returned by the
API or sent to the model.
"""

import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import duckdb

from backend.config import Settings
from backend.sources.context import DIALECT, CatalogContext
from backend.sources.engines import Connection, SourceError, discover
from backend.sources.executor import SourceExecutor
from backend.sources.models import (
    Catalog,
    DatabaseSourceInput,
    SourceConfig,
    SourceDetail,
    SourceSummary,
    SourceUpdate,
)
from backend.tools.sql_validator import SQLValidator

KEYRING_SERVICE = "OtterData"
SAMPLE_ID = "sample"


class RegistryError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status
        super().__init__(message)


class SecretStore(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


class KeyringSecrets:
    """Windows Credential Manager through keyring (installed with the desktop extra)."""

    @staticmethod
    def _keyring():
        try:
            import keyring
        except ImportError:
            raise RegistryError(
                "O cofre de credenciais não está disponível aqui; conecte bancos pelo app desktop."
            ) from None
        return keyring

    def get(self, key: str) -> str | None:
        try:
            return self._keyring().get_password(KEYRING_SERVICE, key)
        except RegistryError:
            return None

    def set(self, key: str, value: str) -> None:
        keyring = self._keyring()
        from keyring.errors import KeyringError

        try:
            keyring.set_password(KEYRING_SERVICE, key, value)
        except KeyringError:
            raise RegistryError(
                "O cofre de credenciais do sistema não está disponível; use o app no Windows."
            ) from None

    def delete(self, key: str) -> None:
        try:
            keyring = self._keyring()
        except RegistryError:
            return
        from keyring.errors import PasswordDeleteError

        try:
            keyring.delete_password(KEYRING_SERVICE, key)
        except PasswordDeleteError:
            pass


@dataclass
class SourceRuntime:
    id: str
    name: str
    kind: str
    context: Any
    validator: SQLValidator
    executor: Any
    allow_rows_to_llm: bool
    metrics_enabled: bool


def default_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "OtterData" if base else Path.home() / ".otterdata"


def slug(text: str, fallback: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")[:60]
    if cleaned and cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned or fallback


def unique(name: str, taken: set[str]) -> str:
    candidate, index = name, 2
    while candidate in taken:
        candidate = f"{name}_{index}"
        index += 1
    return candidate


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def import_csv(db_path: Path, csv_path: Path, filename: str) -> tuple[str, int]:
    """Load one CSV into a new DuckDB table with plain snake_case names."""
    conn = duckdb.connect(str(db_path))
    try:
        existing = {
            row[0]
            for row in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
        }
        table = unique(slug(Path(filename).stem, "dados"), existing)
        try:
            conn.execute(
                f"CREATE TABLE main.{quote(table)} AS "
                "SELECT * FROM read_csv_auto(?, header = true, sample_size = 20000)",
                [str(csv_path)],
            )
        except duckdb.Error:
            raise RegistryError(
                "Não foi possível ler o CSV; confira se a primeira linha tem os nomes das colunas."
            ) from None
        used: set[str] = set()
        for (column,) in conn.execute(
            f"SELECT column_name FROM (DESCRIBE main.{quote(table)})"
        ).fetchall():
            clean = unique(slug(column, "coluna"), used)
            used.add(clean)
            if clean != column:
                conn.execute(
                    f"ALTER TABLE main.{quote(table)} "
                    f"RENAME COLUMN {quote(column)} TO {quote(clean)}"
                )
        # Blank lines come back as rows of NULLs; count only rows with some value.
        filled = " OR ".join(f"{quote(column)} IS NOT NULL" for column in sorted(used))
        rows = conn.execute(f"SELECT COUNT(*) FROM main.{quote(table)} WHERE {filled}").fetchone()[
            0
        ]
        if not rows:
            conn.execute(f"DROP TABLE main.{quote(table)}")
            raise RegistryError("O CSV não tem linhas de dados abaixo do cabeçalho.")
        return table, int(rows)
    finally:
        conn.close()


class SourceRegistry:
    def __init__(
        self,
        settings: Settings,
        *,
        secrets: SecretStore | None = None,
        data_dir: Path | None = None,
    ):
        self._settings = settings
        self._secrets = secrets or KeyringSecrets()
        self.root = Path(data_dir or settings.data_dir or default_data_dir())
        self._folder = self.root / "sources"
        self._index = self.root / "sources.json"
        self._lock = threading.RLock()
        self._runtimes: dict[str, SourceRuntime] = {}

    # ------------------------------------------------------------ storage

    def _read_index(self) -> list[SourceConfig]:
        try:
            raw = json.loads(self._index.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        return [SourceConfig.model_validate(item) for item in raw]

    def _write(self, path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, path)

    def _write_index(self, configs: list[SourceConfig]) -> None:
        self._write(
            self._index, json.dumps([c.model_dump() for c in configs], ensure_ascii=False, indent=2)
        )

    def _catalog_path(self, source_id: str) -> Path:
        return self._folder / f"{source_id}.catalog.json"

    def _duckdb_path(self, source_id: str) -> Path:
        return self._folder / f"{source_id}.duckdb"

    def _save_catalog(self, source_id: str, catalog: Catalog) -> None:
        self._write(self._catalog_path(source_id), catalog.model_dump_json(indent=2))

    def _load_catalog(self, source_id: str) -> Catalog:
        try:
            return Catalog.model_validate_json(
                self._catalog_path(source_id).read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            raise RegistryError("Estrutura da base não encontrada; atualize a base.", 404) from None

    # ------------------------------------------------------------ queries

    def configs(self) -> list[SourceConfig]:
        with self._lock:
            return self._read_index()

    def config(self, source_id: str) -> SourceConfig:
        for item in self.configs():
            if item.id == source_id:
                return item
        raise RegistryError("Base de dados não encontrada.", 404)

    def _connection(self, config: SourceConfig) -> Connection:
        if config.kind == "csv":
            return Connection(kind="csv", path=self._duckdb_path(config.id))
        password = self._secrets.get(config.id)
        if password is None:
            raise RegistryError("A senha desta base não está no cofre; remova e conecte de novo.")
        return Connection(
            kind=config.kind,
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.user,
            password=password,
        )

    def summary(self, config: SourceConfig, catalog: Catalog | None = None) -> SourceSummary:
        catalog = catalog or self._load_catalog(config.id)
        location = (
            "arquivo CSV importado"
            if config.kind == "csv"
            else f"{config.user}@{config.host}:{config.port}/{config.database}"
        )
        return SourceSummary(
            id=config.id,
            name=config.name,
            kind=config.kind,
            location=location,
            schema_name=config.schema_name,
            allow_rows_to_llm=config.allow_rows_to_llm,
            metrics=False,
            tables=len(catalog.tables),
            columns=sum(len(t.columns) for t in catalog.tables.values()),
            hidden_columns=sum(len(t.hidden_columns) for t in catalog.tables.values()),
            built_in=False,
        )

    def detail(self, source_id: str) -> SourceDetail:
        config = self.config(source_id)
        catalog = self._load_catalog(source_id)
        return SourceDetail(
            **self.summary(config, catalog).model_dump(),
            catalog=catalog.tables,
            skipped=catalog.skipped,
        )

    def summaries(self) -> list[SourceSummary]:
        result = []
        for config in self.configs():
            try:
                result.append(self.summary(config))
            except RegistryError:
                continue
        return result

    # ------------------------------------------------------------ changes

    def add_database(self, data: DatabaseSourceInput) -> SourceSummary:
        schema = data.schema_name or ("public" if data.kind == "postgres" else data.database)
        connection = Connection(
            kind=data.kind,
            host=data.host,
            port=data.port,
            database=data.database,
            user=data.user,
            password=data.password.get_secret_value(),
        )
        catalog = self._discover(connection, schema)
        config = SourceConfig(
            id=f"{data.kind}-{uuid4().hex[:10]}",
            name=data.name,
            kind=data.kind,
            host=data.host,
            port=data.port,
            database=data.database,
            user=data.user,
            schema_name=schema,
            allow_rows_to_llm=data.allow_rows_to_llm,
        )
        with self._lock:
            self._secrets.set(config.id, data.password.get_secret_value())
            self._save_catalog(config.id, catalog)
            self._write_index([*self._read_index(), config])
        return self.summary(config, catalog)

    def add_csv(
        self, name: str, filename: str, csv_path: Path, allow_rows_to_llm: bool
    ) -> SourceSummary:
        config = SourceConfig(
            id=f"csv-{uuid4().hex[:10]}",
            name=name,
            kind="csv",
            schema_name="main",
            allow_rows_to_llm=allow_rows_to_llm,
        )
        db_path = self._duckdb_path(config.id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import_csv(db_path, csv_path, filename)
            catalog = self._discover(self._connection(config), "main")
        except Exception:
            db_path.unlink(missing_ok=True)
            raise
        with self._lock:
            self._save_catalog(config.id, catalog)
            self._write_index([*self._read_index(), config])
        return self.summary(config, catalog)

    def add_csv_table(self, source_id: str, filename: str, csv_path: Path) -> SourceSummary:
        config = self.config(source_id)
        if config.kind != "csv":
            raise RegistryError("Só é possível adicionar CSV a uma base de CSV.")
        with self._lock:
            import_csv(self._duckdb_path(source_id), csv_path, filename)
        return self.refresh(source_id)

    def refresh(self, source_id: str) -> SourceSummary:
        config = self.config(source_id)
        catalog = self._discover(self._connection(config), config.schema_name)
        with self._lock:
            self._save_catalog(source_id, catalog)
            self._runtimes.pop(source_id, None)
        return self.summary(config, catalog)

    def update(self, source_id: str, data: SourceUpdate) -> SourceSummary:
        with self._lock:
            configs = self._read_index()
            for index, item in enumerate(configs):
                if item.id == source_id:
                    configs[index] = item.model_copy(update=data.model_dump(exclude_none=True))
                    self._write_index(configs)
                    self._runtimes.pop(source_id, None)
                    return self.summary(configs[index])
        raise RegistryError("Base de dados não encontrada.", 404)

    def delete(self, source_id: str) -> None:
        with self._lock:
            configs = self._read_index()
            remaining = [item for item in configs if item.id != source_id]
            if len(remaining) == len(configs):
                raise RegistryError("Base de dados não encontrada.", 404)
            self._write_index(remaining)
            self._runtimes.pop(source_id, None)
            self._secrets.delete(source_id)
            self._catalog_path(source_id).unlink(missing_ok=True)
            self._duckdb_path(source_id).unlink(missing_ok=True)

    def _discover(self, connection: Connection, schema: str) -> Catalog:
        try:
            catalog = discover(connection, schema, timeout=self._settings.query_timeout_seconds)
        except SourceError as error:
            raise RegistryError(error.message) from None
        if not catalog.tables:
            raise RegistryError(
                f"Conectou, mas não há tabelas legíveis em “{schema}” com esse usuário."
            )
        return catalog

    # ------------------------------------------------------------ runtime

    def runtime(self, source_id: str) -> SourceRuntime:
        with self._lock:
            if source_id in self._runtimes:
                return self._runtimes[source_id]
            config = self.config(source_id)
            catalog = self._load_catalog(source_id)
            dialect = DIALECT[config.kind]
            validator = SQLValidator(
                {name: spec.model_dump() for name, spec in catalog.tables.items()},
                schema=config.schema_name,
                dialect=dialect,
            )
            runtime = SourceRuntime(
                id=config.id,
                name=config.name,
                kind=config.kind,
                context=CatalogContext(config, catalog),
                validator=validator,
                executor=SourceExecutor(self._settings, validator, self._connection(config)),
                allow_rows_to_llm=config.allow_rows_to_llm,
                metrics_enabled=False,
            )
            self._runtimes[source_id] = runtime
            return runtime
