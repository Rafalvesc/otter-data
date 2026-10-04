import asyncio
from unittest.mock import AsyncMock

from backend.agents.analyst import AnalystService
from backend.config import Settings
from backend.llm.base import ProviderReply
from backend.models.analysis import IntentDecision, QueryParameter, SQLDraft
from backend.models.query import QueryCode, QueryResult
from backend.runtime import create_loop


def run(coroutine):
    with asyncio.Runner(loop_factory=create_loop) as runner:
        return runner.run(coroutine)


def intent(**updates):
    values = dict(
        action="analyze",
        metric="new_customers",
        dimension="total",
        start_date="2026-09-01",
        end_date="2026-10-01",
        region=None,
        clarification_question=None,
    )
    return IntentDecision(**(values | updates))


def draft(sql=None, **parameters):
    parameters = parameters or {
        "start_date": "2026-09-01T00:00:00-03:00",
        "end_date": "2026-10-01T00:00:00-03:00",
    }
    return SQLDraft(
        sql=sql
        or "SELECT COUNT(id) AS new_customers FROM analytics.customers "
        "WHERE created_at >= :start_date AND created_at < :end_date",
        parameters=[QueryParameter(name=name, value=value) for name, value in parameters.items()],
    )


def result(**updates):
    values = dict(
        request_id="test-query",
        status="success",
        code=QueryCode.OK,
        message="Consulta executada.",
        sql="SELECT safe_sql",
        sources=("analytics.customers",),
        columns=["new_customers"],
        rows=[{"new_customers": 70}],
        row_count=1,
        duration_ms=1,
        query_attempted=True,
    )
    return QueryResult(**(values | updates))


class ScriptedProvider:
    name = "scripted-test"
    model = "offline-model"
    is_demo = False

    def __init__(self, *values):
        self.values = list(values)
        self.payloads = []
        self.instructions = []

    async def complete(self, schema, instructions, payload):
        self.payloads.append(payload)
        self.instructions.append(instructions)
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return ProviderReply(value=value, input_tokens=10, output_tokens=5)


def service(*values, query_result=None, **settings):
    provider = ScriptedProvider(*values)
    executor = AsyncMock()
    executor.execute_async.return_value = query_result or result()
    # Narration adds a model call; tests that cover it enable it explicitly.
    settings.setdefault("narrative_enabled", False)
    config = Settings(
        _env_file=None,
        analytics_password="offline-db-secret",
        llm_provider="ollama",
        **settings,
    )
    return AnalystService(config, provider, executor), provider, executor
