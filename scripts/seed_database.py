"""Atomic insert-only bootstrap. Refuses partial or different pre-existing data."""

import os

import psycopg
from dotenv import load_dotenv
from psycopg import sql

from backend.sample.data import COLUMNS, fingerprint, generate_dataset


def connect_seed() -> psycopg.Connection:
    load_dotenv()
    return psycopg.connect(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATABASE_PORT", "55432")),
        dbname=os.getenv("DATABASE_NAME", "datapilot"),
        user="seed_writer",
        password=os.environ["SEED_PASSWORD"],
        connect_timeout=5,
    )


def seed_database(connection: psycopg.Connection) -> str:
    data = generate_dataset()
    with connection.transaction():
        # Serializes seed attempts; ordinary writers are not part of this local fixture.
        connection.execute("SELECT pg_advisory_xact_lock(20260930)")
        present = {}
        for table in COLUMNS:
            query = sql.SQL("SELECT {} FROM {} ORDER BY id").format(
                sql.SQL(", ").join(map(sql.Identifier, COLUMNS[table])),
                sql.Identifier("core", table),
            )
            present[table] = connection.execute(query).fetchall()
        if any(present.values()):
            # Compare real rows, not just counts, before claiming that the seed exists.
            for table, columns in COLUMNS.items():
                expected = [tuple(row[column] for column in columns) for row in data[table]]
                if present[table] != expected:
                    raise RuntimeError(
                        "Banco contém dados diferentes ou parciais; nenhum dado foi alterado."
                    )
            return "Dados já conferidos; nenhuma alteração realizada."
        with connection.cursor() as cursor:
            for table, columns in COLUMNS.items():
                statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier("core", table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                cursor.executemany(
                    statement, [tuple(row[column] for column in columns) for row in data[table]]
                )
    return "Carga concluída: " + ", ".join(f"{len(rows)} {table}" for table, rows in data.items())


def main() -> None:
    try:
        with connect_seed() as connection:
            print(seed_database(connection))
            print(f"Dataset SHA256: {fingerprint(generate_dataset())}")
    except (psycopg.Error, KeyError, RuntimeError):
        # No connection strings, credentials or raw database diagnostics in terminal logs.
        raise SystemExit(
            "Carga não concluída. Verifique .env, PostgreSQL e se o banco está vazio "
            "ou contém exatamente a seed prevista. Nenhum reset é automático."
        ) from None


if __name__ == "__main__":
    main()
