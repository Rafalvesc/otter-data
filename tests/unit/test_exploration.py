import json
from datetime import date

import pytest

from backend.agents.answer import render_exploration_answer
from backend.models.analysis import AskRequest, ExploratoryDraft, QueryParameter
from tests.helpers import intent, result, run, service


def explore_intent():
    return intent(action="explore", metric=None, start_date=None, end_date=None)


def exploratory(sql, title="Pedidos por status", assumptions=(), **parameters):
    return ExploratoryDraft(
        sql=sql,
        title=title,
        assumptions=list(assumptions),
        parameters=[QueryParameter(name=name, value=value) for name, value in parameters.items()],
    )


STATUS_ROWS = result(
    sources=("analytics.orders",),
    columns=["status", "order_count"],
    rows=[
        {"status": "paid", "order_count": 8217},
        {"status": "cancelled", "order_count": 1196},
        {"status": "pending", "order_count": 587},
    ],
    row_count=3,
)


def test_exploration_runs_one_validated_select_and_reports_its_nature():
    sql = (
        "SELECT status, COUNT(id) AS order_count FROM analytics.orders "
        "GROUP BY status ORDER BY order_count DESC"
    )
    analyst, provider, executor = service(
        explore_intent(),
        exploratory(sql, assumptions=["Todos os pedidos, sem filtro de período."]),
        query_result=STATUS_ROWS,
    )
    response = run(
        analyst.ask(AskRequest(question="Pedidos por status?", reference_date=date(2026, 9, 30)))
    )
    assert response.status == "success" and response.analysis_mode == "exploration"
    assert response.title == "Pedidos por status" and response.metric is None
    assert response.assumptions == ["Todos os pedidos, sem filtro de período."]
    assert response.answer == "Pedidos por status: 3 linha(s) retornada(s); veja a tabela."
    assert any("não é uma métrica versionada" in item for item in response.limitations)
    assert response.queries_executed == 1 and response.usage.llm_calls == 2
    executor.execute_async.assert_awaited_once()
    assert provider.payloads[0]["context"]["exploration_enabled"] is True
    context = provider.payloads[1]["context"]
    assert set(context["schema"]) == {
        "regions",
        "customers",
        "products",
        "orders",
        "order_items",
        "payments",
    }
    text = json.dumps(provider.payloads)
    assert "core.customers" not in text and '"email"' not in text
    assert "offline-db-secret" not in text and "offline-api-secret" not in text


def test_exploratory_parameters_are_passed_to_the_executor():
    sql = (
        "SELECT COUNT(id) AS orders FROM analytics.orders "
        "WHERE ordered_at >= :start_date AND ordered_at < :end_date"
    )
    parameters = {
        "start_date": "2026-01-01T00:00:00-03:00",
        "end_date": "2027-01-01T00:00:00-03:00",
    }
    analyst, _, executor = service(
        explore_intent(),
        exploratory(sql, title="Pedidos em 2026", **parameters),
        query_result=result(columns=["orders"], rows=[{"orders": 10000}]),
    )
    response = run(analyst.ask(AskRequest(question="Quantos pedidos em 2026?")))
    assert response.status == "success" and response.answer == "Pedidos em 2026: orders = 10.000."
    assert executor.execute_async.call_args.args[1] == parameters


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("SELECT email FROM analytics.customers", "column_not_allowed"),
        ("DELETE FROM analytics.orders", "read_only_required"),
        ("SELECT id FROM analytics.orders; SELECT 1", "multiple_statements"),
    ],
)
def test_terminal_rejections_end_the_request_without_a_rewrite(sql, code):
    analyst, provider, executor = service(explore_intent(), exploratory(sql))
    response = run(analyst.ask(AskRequest(question="Pergunta exploratória")))
    assert response.status == "denied" and response.code == code
    assert response.analysis_mode == "exploration" and response.queries_executed == 0
    executor.execute_async.assert_not_awaited()
    assert len(provider.payloads) == 2 and response.sql_attempts == 1


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("SELECT id FROM core.customers", "relation_not_allowed"),
        ("SELECT * FROM analytics.orders", "wildcard_not_allowed"),
        ("SELECT pg_sleep(5) AS pause FROM analytics.orders", "function_not_allowed"),
        (
            "SELECT o.id FROM analytics.orders AS o JOIN analytics.products AS p ON o.id = p.id",
            "join_not_allowed",
        ),
    ],
)
def test_fixable_rejections_get_one_rewrite_and_are_still_blocked(sql, code):
    analyst, provider, executor = service(explore_intent(), exploratory(sql), exploratory(sql))
    response = run(analyst.ask(AskRequest(question="Pergunta exploratória")))
    assert response.status == "denied" and response.code == code
    assert response.queries_executed == 0 and response.sql_attempts == 2
    executor.execute_async.assert_not_awaited()
    assert len(provider.payloads) == 3
    retry = provider.payloads[2]
    assert retry["previous_sql"] == sql and retry["repair_feedback"]


def test_rejected_function_is_named_and_the_rewrite_runs():
    bad = (
        "SELECT status, STDDEV_SAMP(id) AS spread, PG_SLEEP(1) AS pause "
        "FROM analytics.orders GROUP BY status"
    )
    good = "SELECT status, COUNT(id) AS order_count FROM analytics.orders GROUP BY status"
    analyst, provider, executor = service(
        explore_intent(), exploratory(bad), exploratory(good), query_result=STATUS_ROWS
    )
    response = run(analyst.ask(AskRequest(question="Pedidos por status?")))
    assert response.status == "success" and response.sql_attempts == 2
    assert "PG_SLEEP" in provider.payloads[2]["repair_feedback"]
    executor.execute_async.assert_awaited_once()
    assert executor.execute_async.call_args.args[0] == good


def test_exploration_can_be_disabled_without_generating_sql():
    analyst, provider, executor = service(explore_intent(), exploration_enabled=False)
    response = run(analyst.ask(AskRequest(question="Pedidos por status?")))
    assert response.status == "clarification" and response.code == "unsupported"
    assert provider.payloads[0]["context"]["exploration_enabled"] is False
    assert "schema" not in provider.payloads[0]["context"]
    assert len(provider.payloads) == 1 and response.sql_attempts == 0
    executor.execute_async.assert_not_awaited()


def test_exploration_answer_uses_only_returned_values():
    single = result(columns=["average_price"], rows=[{"average_price": "437.35"}])
    assert (
        render_exploration_answer("Preço médio", single) == "Preço médio: average_price = 437,35."
    )
    empty = result(columns=["n"], rows=[], row_count=0)
    assert (
        render_exploration_answer("Falhas", empty) == "Falhas: a consulta não retornou registros."
    )
    truncated = result(rows=[{"new_customers": 1}] * 2, row_count=2, truncated=True)
    assert "truncada" in render_exploration_answer("Lista", truncated)


def test_response_exposes_interpretation_and_catalog_fields_read():
    sql = (
        "SELECT status, COUNT(id) AS order_count FROM analytics.orders "
        "GROUP BY status ORDER BY order_count DESC"
    )
    analyst, _, _ = service(explore_intent(), exploratory(sql), query_result=STATUS_ROWS)
    response = run(analyst.ask(AskRequest(question="Pedidos por status?")))
    assert response.interpretation.action == "explore"
    assert response.catalog_fields == ["analytics.orders.id", "analytics.orders.status"]


def test_database_error_with_a_known_class_gets_one_guided_rewrite():
    failed = result(
        status="error",
        code="execution_error",
        message="A consulta aprovada falhou durante a execução.",
        rows=[],
        row_count=0,
        retry_hint="Divisão por zero: proteja o divisor com NULLIF(divisor, 0).",
    )
    bad = "SELECT 1 / (COUNT(id) - COUNT(id)) AS ratio FROM analytics.orders"
    good = "SELECT 1 / NULLIF(COUNT(id) - COUNT(id), 0) AS ratio FROM analytics.orders"
    analyst, provider, executor = service(explore_intent(), exploratory(bad), exploratory(good))
    executor.execute_async.side_effect = [failed, STATUS_ROWS]
    response = run(analyst.ask(AskRequest(question="Razão?")))
    assert response.status == "success" and response.sql_attempts == 2
    feedback = provider.payloads[2]["repair_feedback"]
    assert "NULLIF" in feedback and "falhou" not in feedback  # fixed hint only, no driver text
    assert executor.execute_async.await_count == 2


def test_database_error_without_a_known_class_ends_the_request():
    failed = result(
        status="error", code="execution_error", message="A consulta aprovada falhou.", rows=[]
    )
    sql = "SELECT status, COUNT(id) AS n FROM analytics.orders GROUP BY status"
    analyst, provider, executor = service(explore_intent(), exploratory(sql), query_result=failed)
    response = run(analyst.ask(AskRequest(question="Pedidos?")))
    assert response.status == "error" and response.code == "execution_error"
    assert len(provider.payloads) == 2 and response.sql_attempts == 1
