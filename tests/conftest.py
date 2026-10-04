import os

import psycopg
import pytest
from dotenv import load_dotenv


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Executa testes contra o PostgreSQL local; falha se o banco não estiver pronto.",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="Use --run-integration após subir e popular o PostgreSQL.")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def analytics_connection():
    load_dotenv()
    with psycopg.connect(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATABASE_PORT", "55432")),
        dbname=os.getenv("DATABASE_NAME", "datapilot"),
        user="analytics_agent",
        password=os.environ["ANALYTICS_PASSWORD"],
        connect_timeout=5,
        autocommit=True,
    ) as connection:
        yield connection
