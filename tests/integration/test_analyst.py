import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agents.analyst import AnalystService
from backend.api.analysis import get_analyst_service
from backend.config import Settings
from backend.llm.demo import DEMO_QUESTIONS, DemoProvider
from backend.main import app
from backend.models.analysis import AskRequest
from backend.runtime import create_loop
from tests.helpers import run

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("question", list(DEMO_QUESTIONS))
def test_entire_graph_matches_golden_data_in_explicit_demo_mode(question):
    analyst = AnalystService(Settings(llm_provider="demo"), DemoProvider())
    response = run(analyst.ask(AskRequest(question=question, reference_date=date(2026, 9, 30))))
    golden = json.loads(Path("evaluation/datasets/golden_questions.json").read_text("utf-8"))
    expected = next(
        item["expected"] for item in golden["questions"] if item["question"] == question
    )
    assert response.status == "success", response
    assert response.query.rows == expected
    assert response.queries_executed == 1 and response.sql_attempts == 1
    assert response.demo_mode and response.usage.llm_calls == 0
    assert "Modo demonstração" in response.answer
    assert response.query.request_id == response.request_id


def test_http_api_uses_real_database_without_paid_model_calls():
    analyst = AnalystService(Settings(llm_provider="demo"), DemoProvider())
    app.dependency_overrides[get_analyst_service] = lambda: analyst
    try:
        with TestClient(app, backend_options={"loop_factory": create_loop}) as client:
            response = client.post(
                "/api/v1/ask",
                json={
                    "question": "Qual foi a receita recebida em setembro de 2026?",
                    "reference_date": "2026-09-30",
                },
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["query"]["rows"] == [{"received_revenue": "5179102.78"}]
            assert "R$ 5.179.102,78" in body["answer"]
            assert body["usage"]["llm_calls"] == 0
    finally:
        app.dependency_overrides.clear()


def test_total_request_deadline_cancels_real_database_query_and_records_attempt():
    import os

    import psycopg
    from dotenv import load_dotenv

    load_dotenv()
    settings = Settings(llm_provider="demo", request_timeout_seconds=1)
    analyst = AnalystService(settings, DemoProvider())
    with psycopg.connect(
        host=settings.database_host,
        port=settings.database_port,
        dbname=settings.database_name,
        user=os.getenv("POSTGRES_USER", "datapilot_admin"),
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as blocker:
        with blocker.transaction():
            blocker.execute("LOCK TABLE core.orders IN ACCESS EXCLUSIVE MODE")
            response = run(
                analyst.ask(
                    AskRequest(question="Quantos pedidos foram cancelados em setembro de 2026?")
                )
            )
            assert response.code == "request_timeout" and response.status == "error"
            assert response.queries_executed == 1 and response.query.query_attempted
            assert response.query.sql is not None and response.query.rows == []
    recovered = run(
        analyst.ask(AskRequest(question="Quantos pedidos foram cancelados em setembro de 2026?"))
    )
    assert recovered.status == "success"
