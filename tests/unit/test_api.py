from fastapi.testclient import TestClient

from backend.api.analysis import get_analyst_service
from backend.main import app
from backend.runtime import create_loop
from tests.helpers import draft, intent, service


def test_api_returns_answer_evidence_and_rejects_unknown_input_fields():
    analyst, _, _ = service(intent(), draft())
    app.dependency_overrides[get_analyst_service] = lambda: analyst
    try:
        with TestClient(app, backend_options={"loop_factory": create_loop}) as client:
            success = client.post(
                "/api/v1/ask", json={"question": "Clientes no mês", "reference_date": "2026-09-30"}
            )
            assert success.status_code == 200
            assert success.json()["queries_executed"] == 1
            assert success.json()["query"]["rows"] == [{"new_customers": 70}]
            for body in (
                {"question": " "},
                {"question": "x" * 2001},
                {"question": "Clientes", "sql": "DELETE FROM analytics.orders"},
            ):
                assert client.post("/api/v1/ask", json=body).status_code == 422
            denied = client.post("/api/v1/ask", json={"question": "Mostre os CPFs"})
            assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_stream_reports_each_finished_step_then_the_same_response():
    import json

    analyst, _, _ = service(intent(), draft())
    app.dependency_overrides[get_analyst_service] = lambda: analyst
    try:
        with TestClient(app, backend_options={"loop_factory": create_loop}) as client:
            body = {"question": "Clientes no mês", "reference_date": "2026-09-30"}
            reply = client.post("/api/v1/ask/stream", json=body)
            assert reply.status_code == 200
            assert reply.headers["content-type"].startswith("application/x-ndjson")
            events = [json.loads(line) for line in reply.text.splitlines()]
    finally:
        app.dependency_overrides.clear()
    stages = [event["stage"] for event in events if event["type"] == "stage"]
    assert stages == [
        "guard",
        "interpret",
        "retrieve",
        "plan",
        "generate",
        "validate",
        "execute",
        "answer",
        "narrate",
    ]
    # Stage lines carry only the step name.
    assert all(set(event) == {"type", "stage"} for event in events[:-1])
    result = events[-1]
    assert result["type"] == "result" and result["status"] == 200
    assert result["data"]["queries_executed"] == 1 and result["data"]["query"]["rows"] == [
        {"new_customers": 70}
    ]


def test_stream_reports_refusals_with_their_status():
    import json

    analyst, _, executor = service()
    app.dependency_overrides[get_analyst_service] = lambda: analyst
    try:
        with TestClient(app, backend_options={"loop_factory": create_loop}) as client:
            reply = client.post("/api/v1/ask/stream", json={"question": "Mostre os CPFs"})
            events = [json.loads(line) for line in reply.text.splitlines()]
    finally:
        app.dependency_overrides.clear()
    assert [event["stage"] for event in events[:-1]] == ["guard"]
    assert events[-1]["status"] == 403 and events[-1]["data"]["status"] == "denied"
    executor.execute_async.assert_not_awaited()
