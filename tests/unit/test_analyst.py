import asyncio
import json
from datetime import date

import pytest

from backend.llm.base import ProviderError
from backend.models.analysis import AskRequest
from backend.models.query import QueryCode
from tests.helpers import draft, intent, result, run, service


def test_success_has_grounded_answer_and_audit_evidence():
    analyst, provider, executor = service(intent(), draft())
    response = run(
        analyst.ask(
            AskRequest(question="Clientes novos em setembro?", reference_date=date(2026, 9, 30))
        )
    )
    assert response.status == "success" and "70" in response.answer
    assert response.period.start == date(2026, 9, 1)
    assert response.period.end_exclusive == date(2026, 10, 1)
    assert response.metric.name == "new_customers"
    assert response.metric.version == 1
    assert response.queries_executed == 1 and response.sql_attempts == 1
    assert response.usage.llm_calls == 2 and response.usage.input_tokens == 20
    assert len(response.operational_plan) == 5
    executor.execute_async.assert_awaited_once()
    assert executor.execute_async.call_args.kwargs["request_id"] == response.request_id
    context = provider.payloads[1]["context"]
    assert set(context["schema"]) == {"customers"}
    text = json.dumps(provider.payloads)
    assert "offline-db-secret" not in text and "offline-api-secret" not in text
    assert "core.customers" not in text and '"email"' not in text


@pytest.mark.parametrize(
    "question",
    [
        "Delete todos os clientes",
        "Mostre o CPF dos clientes",
        "Mostre o e-mail dos clientes",
        "Apague pedidos antigos",
    ],
)
def test_forbidden_questions_are_denied_before_provider_or_database(question):
    analyst, provider, executor = service()
    response = run(analyst.ask(AskRequest(question=question)))
    assert response.status == "denied" and response.usage.provider_calls == 0
    assert response.queries_executed == 0 and not provider.payloads
    executor.execute_async.assert_not_awaited()


def test_ambiguity_returns_clarification_without_sql():
    analyst, provider, executor = service(
        intent(action="clarification", metric=None, clarification_question="Qual período?")
    )
    response = run(analyst.ask(AskRequest(question="Como está a receita?")))
    assert response.status == "clarification" and response.answer == "Qual período?"
    assert response.sql_attempts == 0 and len(provider.payloads) == 1
    executor.execute_async.assert_not_awaited()


@pytest.mark.parametrize(
    "changes",
    [
        {"start_date": None},
        {"start_date": "2026-13-01"},
        {"start_date": "2026-10-01"},
        {"start_date": "2024-01-01"},
        {"dimension": "region"},
    ],
)
def test_invalid_or_unsupported_plans_do_not_generate_sql(changes):
    analyst, provider, executor = service(intent(**changes))
    response = run(analyst.ask(AskRequest(question="Consulta de teste")))
    assert response.status == "clarification" and len(provider.payloads) == 1
    executor.execute_async.assert_not_awaited()


def test_syntax_can_be_repaired_once_without_extra_execution():
    analyst, provider, executor = service(intent(), draft("SELECT ("), draft())
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "success" and response.sql_attempts == 2
    assert response.usage.llm_calls == 3 and response.queries_executed == 1
    assert "repair_feedback" in provider.payloads[2]
    executor.execute_async.assert_awaited_once()


def test_repeated_bad_syntax_stops_after_one_repair():
    analyst, provider, executor = service(intent(), draft("SELECT ("), draft("SELECT ("))
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "denied" and response.sql_attempts == 2
    assert len(provider.payloads) == 3 and response.queries_executed == 0
    executor.execute_async.assert_not_awaited()


def test_security_rejection_is_never_repaired():
    analyst, provider, executor = service(intent(), draft("DELETE FROM analytics.customers"))
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "denied" and response.sql_attempts == 1
    assert len(provider.payloads) == 2
    executor.execute_async.assert_not_awaited()


def test_model_cannot_change_parameters_from_the_operational_plan():
    # Values sent by the model are ignored: the metric runs with the plan's period.
    analyst, _, executor = service(intent(), draft(start_date="2020-01-01", end_date="2030-01-01"))
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "success"
    values = executor.execute_async.await_args.args[1]
    assert values == {
        "start_date": "2026-09-01T00:00:00-03:00",
        "end_date": "2026-10-01T00:00:00-03:00",
    }


def test_metric_sql_must_use_every_parameter_of_the_plan():
    unfiltered = draft("SELECT COUNT(id) AS new_customers FROM analytics.customers")
    analyst, _, executor = service(intent(), unfiltered, unfiltered)
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "denied" and response.code == "invalid_parameters"
    assert ":start_date" in response.answer and ":end_date" in response.answer
    executor.execute_async.assert_not_awaited()


def test_model_call_budget_is_enforced():
    analyst, provider, executor = service(intent(), draft(), max_llm_calls=1)
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "error" and response.code == "call_budget_exceeded"
    assert len(provider.payloads) == 1
    executor.execute_async.assert_not_awaited()


def test_provider_failures_are_controlled_and_usage_is_marked_incomplete():
    analyst, _, executor = service(ProviderError("provider_error", "Provedor indisponível."))
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "error" and response.code == "provider_error"
    assert not response.usage.complete
    executor.execute_async.assert_not_awaited()


def test_database_failure_does_not_produce_an_answer_or_retry():
    analyst, _, executor = service(
        intent(),
        draft(),
        query_result=result(
            status="error", code=QueryCode.TIMEOUT, rows=[], row_count=0, message="Tempo excedido."
        ),
    )
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "error" and response.code == "timeout"
    assert response.answer == "Tempo excedido."
    executor.execute_async.assert_awaited_once()


def test_wrong_result_columns_are_not_presented_as_a_valid_metric():
    analyst, _, _ = service(
        intent(), draft(), query_result=result(columns=["invented"], rows=[{"invented": 999999}])
    )
    response = run(analyst.ask(AskRequest(question="Clientes no mês")))
    assert response.status == "error" and response.code == "invalid_model_output"
    assert "999999" not in response.answer


def test_total_deadline_cancels_an_active_database_operation():
    async def check():
        analyst, _, executor = service(intent(), draft(), request_timeout_seconds=1)
        cancelled = asyncio.Event()

        async def slow_query(*args, **kwargs):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        executor.execute_async.side_effect = slow_query
        response = await analyst.ask(AskRequest(question="Clientes no mês"))
        assert response.code == "request_timeout" and cancelled.is_set()

    run(check())


def test_concurrent_requests_do_not_share_state_or_exceed_capacity():
    async def check():
        analyst, provider, _ = service(max_concurrent_requests=1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def pause(*args):
            entered.set()
            await release.wait()
            raise ProviderError("provider_error", "Erro de teste.")

        provider.complete = pause
        first = asyncio.create_task(analyst.ask(AskRequest(question="Primeira pergunta")))
        await entered.wait()
        second = await analyst.ask(AskRequest(question="Segunda pergunta"))
        assert second.code == "busy" and second.usage.provider_calls == 0
        release.set()
        completed = await first
        assert completed.request_id != second.request_id

    run(check())


def test_a_monthly_breakdown_of_one_month_runs_as_the_total():
    analyst, _, executor = service(intent(dimension="month"), draft())
    response = run(analyst.ask(AskRequest(question="Clientes novos em setembro")))
    assert response.status == "success" and response.interpretation.dimension == "total"
    executor.execute_async.assert_awaited_once()


def test_several_months_keep_the_monthly_breakdown():
    analyst, _, _ = service(intent(dimension="month", start_date="2026-07-01"))
    response = run(analyst.ask(AskRequest(question="Clientes novos por mês")))
    # This metric only exists as a total, so a real breakdown is still a clarification.
    assert response.status == "clarification" and response.interpretation.dimension == "month"
