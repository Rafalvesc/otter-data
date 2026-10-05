"""MongoDB as a read-only, local snapshot.

Questions are answered with validated SQL, so a MongoDB database is copied into a DuckDB file
(one table per collection) and every query runs on that copy. Only `list_collection_names` and
`find` are used against MongoDB, with a time limit and a document limit per collection; the
copy is refreshed on demand.

Documents are flattened like MongoDB's own BI connector: embedded documents become columns
(`address.city` -> `address_city`), arrays of documents become child tables linked by the
parent's id (`orders.items` -> `orders_items.orders_id`), and other arrays are kept as JSON
text. Identifiers become plain snake_case names, and personal-looking columns are hidden later
by the catalog like in any other source.
"""

import base64
import datetime as dt
import json
import re
import tempfile
import unicodedata
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from backend.models.query import QueryCode
from backend.sources.catalog import MAX_TABLES
from backend.sources.engines import Connection, SourceError

MAX_DOCUMENTS = 100_000  # per collection
MAX_DEPTH = 3  # embedded documents deeper than this are kept as JSON text
BATCH_SIZE = 1_000


def slug(text: str, fallback: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")[:60]
    if cleaned and cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned or fallback


def scalar(value: Any) -> Any:
    """A JSON-ready value; BSON types become their natural text or number."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dt.datetime):
        # PyMongo returns naive UTC datetimes; the copy keeps them as UTC timestamps.
        return value.replace(tzinfo=None).isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "to_decimal"):  # bson.Decimal128
        return float(value.to_decimal())
    if isinstance(value, bytes):
        return base64.b64encode(value).decode()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)  # ObjectId, Timestamp, Regex, MinKey...


def as_json(value: Any) -> str:
    def default(item: Any) -> Any:
        return scalar(item)

    return json.dumps(value, ensure_ascii=False, default=default)


def flatten(
    document: dict, prefix: str = "", depth: int = 0
) -> tuple[dict[str, Any], dict[str, list]]:
    """(columns, child arrays) of one document. Child arrays only come from the top level."""
    row: dict[str, Any] = {}
    children: dict[str, list] = {}
    for key, value in document.items():
        name = f"{prefix}_{slug(key, 'field')}" if prefix else slug(key, "field")
        if isinstance(value, dict):
            if depth + 1 < MAX_DEPTH:
                nested, _ = flatten(value, name, depth + 1)
                row.update(nested)
            else:
                row[name] = as_json(value)
        elif isinstance(value, list):
            if depth == 0 and value and all(isinstance(item, dict) for item in value):
                children[name] = value
            else:
                row[name] = as_json(value)
        else:
            row[name] = scalar(value)
    return row, children


class Snapshot:
    """Accumulates flattened rows per table as newline-delimited JSON files."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.files: dict[str, Path] = {}
        self.handles: dict[str, Any] = {}

    def write(self, table: str, row: dict[str, Any]) -> None:
        if table not in self.handles:
            path = self.folder / f"{table}.jsonl"
            self.files[table] = path
            self.handles[table] = path.open("w", encoding="utf-8")
        self.handles[table].write(json.dumps(row, ensure_ascii=False) + "\n")

    def close(self) -> None:
        for handle in self.handles.values():
            handle.close()


def snapshot_database(database, db_path: Path, timeout_seconds: int) -> list[str]:
    """Copy every collection of `database` into `db_path`; returns notes for the catalog."""
    notes: list[str] = []
    names = sorted(
        name for name in database.list_collection_names() if not name.startswith("system.")
    )
    if len(names) > MAX_TABLES:
        notes.extend(
            f"coleção {name} (limite de {MAX_TABLES} coleções)" for name in names[MAX_TABLES:]
        )
        names = names[:MAX_TABLES]
    with tempfile.TemporaryDirectory(prefix="otter-mongo-") as folder:
        snapshot = Snapshot(Path(folder))
        tables: dict[str, str] = {}
        try:
            for name in names:
                table = slug(name, "colecao")
                while table in tables.values():
                    table = f"{table}_2"
                tables[name] = table
                cursor = (
                    database[name]
                    .find({}, batch_size=BATCH_SIZE, max_time_ms=timeout_seconds * 1000)
                    .limit(MAX_DOCUMENTS + 1)
                )
                count = 0
                for document in cursor:
                    if count == MAX_DOCUMENTS:
                        notes.append(
                            f"coleção {name}: importados os primeiros {MAX_DOCUMENTS} documentos"
                        )
                        break
                    count += 1
                    row, children = flatten(document)
                    parent_id = row.get("id")
                    snapshot.write(table, row)
                    for field, items in children.items():
                        child_table = f"{table}_{field}"[:60]
                        for position, item in enumerate(items):
                            child, _ = flatten(item, depth=1)
                            snapshot.write(
                                child_table,
                                {f"{table}_id": parent_id, "position": position, **child},
                            )
        finally:
            snapshot.close()
        write_duckdb(db_path, snapshot.files)
    return notes


def write_duckdb(db_path: Path, files: dict[str, Path]) -> None:
    """Build the DuckDB copy in a temporary file and swap it in, so a failed refresh keeps the
    previous copy."""
    temporary = db_path.with_suffix(".importing.duckdb")
    temporary.unlink(missing_ok=True)
    conn = duckdb.connect(str(temporary))
    try:
        for table, path in files.items():
            conn.execute(
                f'CREATE TABLE main."{table}" AS SELECT * FROM read_json_auto(?, '
                "format = 'newline_delimited', sample_size = -1, union_by_name = true)",
                [str(path)],
            )
    finally:
        conn.close()
    temporary.replace(db_path)


def connect(connection: Connection, auth_source: str, timeout_seconds: int):
    """A MongoClient for `connection`; Atlas hosts (*.mongodb.net) use the SRV scheme."""
    from pymongo import MongoClient

    options = dict(
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=(timeout_seconds + 5) * 1000,
        readPreference="secondaryPreferred",
        appname="OtterData",
    )
    if connection.user:
        options.update(username=connection.user, password=connection.password or "")
        options.update(authSource=auth_source)
    host = connection.host or "localhost"
    if host.endswith(".mongodb.net"):
        return MongoClient(f"mongodb+srv://{host}/", **options)
    return MongoClient(host=host, port=connection.port or 27017, **options)


def import_mongodb(
    connection: Connection, auth_source: str, db_path: Path, *, timeout: int
) -> list[str]:
    """Snapshot `connection.database` into `db_path`. Errors carry fixed messages only."""
    from pymongo import errors

    client = connect(connection, auth_source, timeout)
    try:
        client.admin.command("ping")
        return snapshot_database(client[connection.database], db_path, timeout)
    except errors.ExecutionTimeout:
        raise SourceError(
            QueryCode.TIMEOUT, "O MongoDB excedeu o tempo permitido ao ler as coleções."
        ) from None
    except errors.OperationFailure:
        raise SourceError(
            QueryCode.CONNECTION_ERROR,
            "O MongoDB recusou o acesso; confira usuário, senha, banco de autenticação e "
            "se o usuário pode ler esse banco.",
        ) from None
    except errors.PyMongoError:
        raise SourceError(
            QueryCode.CONNECTION_ERROR,
            "Não foi possível conectar ao MongoDB; confira servidor, porta, usuário e senha.",
        ) from None
    except duckdb.Error:
        raise SourceError(
            QueryCode.EXECUTION_ERROR, "Não foi possível montar a cópia local do MongoDB."
        ) from None
    finally:
        client.close()
