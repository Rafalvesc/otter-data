import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import partial
from time import perf_counter
from typing import Any, TypedDict
from uuid import uuid4
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from pydantic import ValidationError

from backend.agents.answer import InvalidResult, render_answer, render_exploration_answer
from backend.agents.charts import check_chart
from backend.agents.narrative import check_numbers, shared_rows
from backend.config import Settings
from backend.llm.base import LLMProvider, ProviderError
from backend.llm.catalog import ModelCatalog, ModelOption
from backend.llm.demo import normalize_question
from backend.llm.factory import build_provider
from backend.llm.prompts import (
    CHAT_INSTRUCTIONS,
    EXPLORE_SQL_INSTRUCTIONS,
    INTENT_INSTRUCTIONS,
    NARRATIVE_INSTRUCTIONS,
    SQL_INSTRUCTIONS,
)
from backend.models.analysis import (
    AskRequest,
    AskResponse,
    ChartSpec,
    ChatReply,
    ExploratoryDraft,
    IntentDecision,
    NarrativeDraft,
    NarrativeEvidence,
    SQLDraft,
    UsageEvidence,
)
from backend.models.query import QueryResult, ValidationResult
from backend.sample.embedded import SAMPLE_NAME, embedded_sample_runtime
from backend.sources.registry import SAMPLE_ID, RegistryError, SourceRegistry, SourceRuntime
from backend.tools.context import ContextError, SemanticContext
from backend.tools.sql_executor import SQLExecutor
from backend.tools.sql_validator import SQLValidator

logger = logging.getLogger(__name__)
WRITE_REQUEST = re.compile(
    r"\b(delete|apague|exclua|remova|atualize|insira|drop|truncate|insert|update|alter)\b"
)
SENSITIVE_REQUEST = re.compile(r"\b(cpfs?|emails?|e-mails?|telefones?|phones?|tax_id)\b")


@dataclass
class Audit:
    request_id: str
    started: float
    usage: UsageEvidence = field(default_factory=UsageEvidence)
    sql_attempts: int = 0
    query: QueryResult | None = None


LANGUAGE_RULE = {
    "en-US": "Write every text field of the JSON in English.",
    "pt-BR": "Escreva todos os campos de texto do JSON em português do Brasil.",
}


def within_one_month(intent: IntentDecision) -> bool:
    try:
        start = date.fromisoformat(intent.start_date or "")
        end = date.fromisoformat(intent.end_date or "")
    except ValueError:
        return False
    next_month = date(start.year + start.month // 12, start.month % 12 + 1, 1)
    return start < end <= next_month


class AnalysisState(TypedDict, total=False):
    request: AskRequest
    reference_date: str
    audit: Audit
    status: str
    code: str
    answer: str
    intent: IntentDecision
    context: dict
    plan: dict
    draft: SQLDraft
    validation: ValidationResult
    narrative: NarrativeEvidence
    narrative_note: str
    follow_ups: list
    chart: ChartSpec | None
    chart_note: str | None
    source: SourceRuntime
    provider: Any
    budget: float


# Called with a finished graph node name ("interpret", "validate"...); never with data.
StageCallback = Callable[[str], Awaitable[None]]


class AnalystService:
    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        executor: SQLExecutor | None = None,
        sources: SourceRegistry | None = None,
        models: ModelCatalog | None = None,
        provider_factory: Callable[[ModelOption], LLMProvider] | None = None,
    ):
        self.settings = Settings.model_validate(settings.model_dump())
        self.provider = provider
        self.models = models
        self._provider_factory = provider_factory or partial(build_provider, self.settings)
        self._providers: dict[str, LLMProvider] = {}
        self.sources = sources
        if executor is None and self.settings.embedded_sample:
            self.sample = embedded_sample_runtime(self.settings)
        else:
            self.sample = SourceRuntime(
                id=SAMPLE_ID,
                name=SAMPLE_NAME,
                kind="sample",
                context=SemanticContext(),
                validator=SQLValidator(),
                executor=executor or SQLExecutor(self.settings),
                allow_rows_to_llm=True,
                metrics_enabled=True,
            )
        self._slots = asyncio.Semaphore(self.settings.max_concurrent_requests)
        builder = StateGraph(AnalysisState)
        for name in (
            "guard",
            "interpret",
            "converse",
            "retrieve",
            "plan",
            "generate",
            "validate",
            "execute",
            "answer",
            "narrate",
        ):
            builder.add_node(name, getattr(self, f"_{name}"))
        builder.add_edge(START, "guard")
        builder.add_conditional_edges(
            "guard",
            lambda state: "interpret" if "status" not in state else END,
            {"interpret": "interpret", END: END},
        )
        builder.add_conditional_edges(
            "interpret",
            self._after_interpret,
            {"retrieve": "retrieve", "converse": "converse", END: END},
        )
        builder.add_edge("converse", END)
        builder.add_edge("retrieve", "plan")
        builder.add_conditional_edges(
            "plan",
            lambda state: "generate" if "status" not in state else END,
            {"generate": "generate", END: END},
        )
        builder.add_edge("generate", "validate")
        builder.add_conditional_edges(
            "validate",
            self._after_validation,
            {"execute": "execute", "generate": "generate", END: END},
        )
        builder.add_conditional_edges(
            "execute",
            self._after_execute,
            {"answer": "answer", "generate": "generate", END: END},
        )
        builder.add_edge("answer", "narrate")
        builder.add_edge("narrate", END)
        self.graph = builder.compile()

    async def ask(self, request: AskRequest, on_stage: StageCallback | None = None) -> AskResponse:
        """Run the analysis. `on_stage(node)` is awaited after each graph node finishes; it
        receives only the node name, never data, so callers can show real progress."""
        reference = request.reference_date or datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        audit = Audit(str(uuid4()), perf_counter())
        state: AnalysisState = {
            "request": request,
            "reference_date": reference.isoformat(),
            "audit": audit,
        }
        try:
            state["source"] = self._source(request.source_id)
        except RegistryError as error:
            state.update(status="error", code="source_unavailable", answer=error.message)
        provider = self._model(request.model)
        if provider is None:
            state.update(
                status="error",
                code="model_unavailable",
                answer="Esse modelo não está disponível agora; escolha outro na lista de modelos.",
            )
            provider = self.provider
        state["provider"] = provider
        state["budget"] = (
            self.settings.local_request_timeout_seconds
            if getattr(provider, "local", False)
            else self.settings.request_timeout_seconds
        )
        try:
            if "status" not in state:
                state = await self._run(state, on_stage)
        except TimeoutError:
            audit.usage.complete = False
            state.update(
                status="error",
                code="request_timeout",
                answer="A análise excedeu o tempo permitido.",
            )
        except ProviderError as error:
            state.update(status="error", code=error.code, answer=error.message)
        except (ValidationError, InvalidResult, ValueError, KeyError, TypeError):
            state.update(
                status="error",
                code="invalid_model_output",
                answer="A análise não produziu uma resposta verificável.",
            )
        plan = state.get("plan", {})
        draft = state.get("draft")
        exploratory = isinstance(draft, ExploratoryDraft)
        query = audit.query
        source = state.get("source")
        first = (
            "Base local sintética; não representa uma empresa real."
            if source is None or source.kind == "sample"
            else f"Base conectada pelo usuário: {source.name}."
        )
        limitations = [first] + plan.get("limitations", [])
        if query and query.truncated:
            limitations.append(
                "Resultado truncado; não trate uma lista parcial como cobertura completa."
            )
        if state.get("chart_note"):
            limitations.append(state["chart_note"])
        if not audit.usage.complete:
            limitations.append("Tokens informados cobrem apenas respostas com uso conhecido.")
        result = AskResponse(
            request_id=audit.request_id,
            status=state.get("status", "error"),
            code=state.get("code", "workflow_error"),
            answer=state.get("answer", "A análise não foi concluída."),
            provider=provider.name,
            model=provider.model,
            demo_mode=provider.is_demo,
            source_id=source.id if source else request.source_id,
            source_name=source.name if source else None,
            reference_date=reference,
            period=plan.get("period"),
            metric=plan.get("metric_evidence"),
            analysis_mode=self._mode(state, plan),
            title=draft.title if exploratory else None,
            assumptions=list(draft.assumptions) if exploratory else [],
            narrative=state.get("narrative"),
            narrative_note=state.get("narrative_note"),
            follow_ups=state.get("follow_ups", []),
            chart=state.get("chart"),
            filters={"region": plan["region"]} if plan.get("region") else {},
            operational_plan=plan.get("operational_plan", []),
            interpretation=state.get("intent"),
            catalog_fields=list(state["validation"].fields) if state.get("validation") else [],
            sources=query.sources if query else (),
            queries_executed=int(query.query_attempted) if query else 0,
            sql_attempts=audit.sql_attempts,
            query=query,
            limitations=limitations,
            usage=audit.usage,
            duration_ms=round((perf_counter() - audit.started) * 1000, 3),
        )
        logger.info(
            "analysis_finished",
            extra={
                "request_id": result.request_id,
                "analysis_status": result.status,
                "analysis_code": result.code,
                "llm_calls": result.usage.llm_calls,
                "queries_executed": result.queries_executed,
                "duration_ms": result.duration_ms,
            },
        )
        return result

    def _guard(self, state):
        question = normalize_question(state["request"].question)
        if WRITE_REQUEST.search(question) or SENSITIVE_REQUEST.search(question):
            return {
                "status": "denied",
                "code": "request_denied",
                "answer": "Este assistente permite apenas análise de leitura sem campos pessoais.",
            }
        return {}

    async def _call(self, state, schema, instructions, payload):
        if "language" in payload:
            # The instructions are written in Portuguese; small models tend to follow the language
            # of the prompt over a field, so the target language is also stated last, in itself.
            instructions = f"{instructions.rstrip()}\n{LANGUAGE_RULE[payload['language']]}"
        audit = state["audit"]
        if audit.usage.provider_calls >= self.settings.max_llm_calls:
            raise ProviderError(
                "call_budget_exceeded", "A análise atingiu o limite de chamadas ao modelo."
            )
        audit.usage.provider_calls += 1
        provider = state["provider"]
        if not provider.is_demo:
            audit.usage.llm_calls += 1
        try:
            timeout = getattr(provider, "timeout_seconds", self.settings.llm_timeout_seconds)
            async with asyncio.timeout(timeout):
                reply = await provider.complete(schema, instructions, payload)
            value = schema.model_validate(reply.value.model_dump())
        except TimeoutError:
            audit.usage.complete = False
            raise ProviderError(
                "provider_timeout", "O provedor excedeu o tempo permitido."
            ) from None
        except BaseException:
            audit.usage.complete = False
            raise
        audit.usage.input_tokens += reply.input_tokens
        audit.usage.output_tokens += reply.output_tokens
        audit.usage.complete = audit.usage.complete and reply.usage_known
        return value

    def _model(self, model_id: str | None) -> LLMProvider | None:
        """The default provider, or the picked model if the catalog offers it."""
        if not model_id or self.models is None or model_id == self.models.default_id:
            return self.provider
        option = self.models.resolve(model_id)
        if option is None:
            return None
        if option.id not in self._providers:
            self._providers[option.id] = self._provider_factory(option)
        return self._providers[option.id]

    def _source(self, source_id: str | None) -> SourceRuntime:
        if not source_id or source_id == SAMPLE_ID:
            return self.sample
        if self.sources is None:
            raise RegistryError("Bases conectadas não estão disponíveis neste servidor.", 404)
        return self.sources.runtime(source_id)

    async def _run(self, state, on_stage: StageCallback | None = None):
        async with asyncio.timeout(state["budget"]):
            if self._slots.locked():
                raise ProviderError("busy", "O serviço está ocupado; tente novamente em instantes.")
            async with self._slots:
                # Prevent inherited LangSmith tracing from exporting prompts, SQL or results.
                with tracing_context(enabled=False):
                    final = state
                    async for mode, chunk in self.graph.astream(
                        state,
                        config={"recursion_limit": 20, "callbacks": []},
                        stream_mode=["updates", "values"],
                    ):
                        if mode == "values":
                            final = chunk
                        elif on_stage is not None:
                            for node in chunk:
                                await on_stage(node)
                    return final

    def _conversation(self, state) -> list[dict]:
        """Recent turns as model context. Answers can carry values from the base, so they are
        only included when the source lets the model read result rows."""
        limit = self.settings.history_turns
        turns = state["request"].history[-limit:] if limit else []
        with_answers = state["source"].allow_rows_to_llm
        return [
            {"question": turn.question, "answer": turn.answer if with_answers else None}
            for turn in turns
        ]

    @staticmethod
    def _locale(state) -> str:
        """Language and number format of everything the model writes for the user."""
        return "en-US" if state["request"].language == "en" else "pt-BR"

    def _about(self) -> dict:
        return {
            "product": "Otter Data",
            "description": "Analista de dados com IA que conversa, consulta bases somente leitura "
            "com SQL validado e mostra as evidências de cada número.",
            "author": self.settings.otter_author or None,
        }

    async def _interpret(self, state):
        intent = await self._call(
            state,
            IntentDecision,
            INTENT_INSTRUCTIONS,
            {
                "question": state["request"].question,
                "conversation": self._conversation(state),
                "language": self._locale(state),
                "reference_date": state["reference_date"],
                "context": state["source"].context.intent_context(
                    self.settings.exploration_enabled
                ),
            },
        )
        if intent.action == "analyze" and intent.dimension == "month" and within_one_month(intent):
            # A month-by-month breakdown of a single month is its total.
            intent = intent.model_copy(update={"dimension": "total"})
        source = state["source"]
        exploration = self.settings.exploration_enabled or not source.metrics_enabled
        if intent.action == "analyze" and not source.metrics_enabled:
            # Connected sources have no versioned metrics: data questions are explorations.
            intent = intent.model_copy(update={"action": "explore", "metric": None})
        if intent.action == "chat":
            return {"intent": intent}
        if intent.action == "analyze" or (intent.action == "explore" and exploration):
            return {"intent": intent}
        if intent.action == "denied":
            return {
                "intent": intent,
                "status": "denied",
                "code": "request_denied",
                "answer": "Não posso atender esse pedido: trabalho somente com leitura de "
                "dados e não compartilho instruções internas, credenciais ou dados pessoais.",
            }
        if intent.action == "explore":
            return {
                "intent": intent,
                "status": "clarification",
                "code": "unsupported",
                "answer": "Perguntas exploratórias estão desativadas; use uma métrica documentada.",
            }
        return {
            "intent": intent,
            "status": "clarification",
            "code": intent.action,
            "answer": intent.clarification_question
            or (
                "Essa pergunta exige dados ou análises fora do escopo (causas, previsões, custos). "
                "Tente uma pergunta descritiva sobre pedidos, produtos, pagamentos ou regiões."
                if intent.action == "unsupported"
                else "Informe a métrica e o período da análise."
            ),
        }

    @staticmethod
    def _after_interpret(state):
        if "status" in state:
            return END
        return "converse" if state["intent"].action == "chat" else "retrieve"

    @staticmethod
    def _mode(state, plan):
        if plan:
            return "exploration" if plan.get("mode") == "exploration" else "metric"
        intent = state.get("intent")
        return "chat" if intent is not None and intent.action == "chat" else None

    async def _converse(self, state):
        """General conversation: no SQL, no database, no result rows."""
        reply = await self._call(
            state,
            ChatReply,
            CHAT_INSTRUCTIONS,
            {
                "message": state["request"].question,
                "conversation": self._conversation(state),
                "language": self._locale(state),
                "reference_date": state["reference_date"],
                "about": self._about(),
                "capabilities": state["source"].context.capabilities(),
            },
        )
        return {
            "status": "success",
            "code": "chat",
            "answer": reply.answer,
            "follow_ups": reply.follow_ups,
        }

    def _retrieve(self, state):
        if state["intent"].action == "explore":
            return {"context": state["source"].context.explore_context()}
        try:
            return {"context": state["source"].context.retrieve(state["intent"])}
        except (KeyError, TypeError):
            return {"context": {}}

    def _plan(self, state):
        if state["intent"].action == "explore":
            return {"plan": state["source"].context.explore_plan()}
        try:
            return {"plan": state["source"].context.plan(state["intent"])}
        except ContextError as error:
            return {"status": "clarification", "code": "clarification", "answer": str(error)}

    async def _generate(self, state):
        state["audit"].sql_attempts += 1
        plan = state["plan"]
        if plan.get("mode") == "exploration":
            payload = {
                "question": state["request"].question,
                "conversation": self._conversation(state),
                "language": self._locale(state),
                "reference_date": state["reference_date"],
                "context": state["context"],
            }
            if "validation" in state:
                payload["previous_sql"] = state["draft"].sql
                payload["repair_feedback"] = state["validation"].message
            draft = await self._call(state, ExploratoryDraft, EXPLORE_SQL_INSTRUCTIONS, payload)
            return {"draft": draft}
        payload = {
            "question": state["request"].question,
            "context": state["context"],
            "plan": {
                key: plan[key]
                for key in ("metric", "dimension", "parameters", "output_columns", "region")
            },
        }
        if "validation" in state:
            payload["previous_sql"] = state["draft"].sql
            payload["repair_feedback"] = state["validation"].message
        return {"draft": await self._call(state, SQLDraft, SQL_INSTRUCTIONS, payload)}

    @staticmethod
    def _parameters(state) -> dict:
        """Values bound to the query. Versioned metrics always run with the plan's values, whatever
        the model sent, so it cannot change period or filters; the SQL must use every one of
        them (the validator rejects missing or unused names). Exploratory drafts bring their own
        values, which the validator still checks."""
        if state["plan"].get("mode") == "exploration":
            return state["draft"].parameter_dict()
        return state["plan"]["parameters"]

    def _validate(self, state):
        validation = state["source"].validator.validate(state["draft"].sql, self._parameters(state))
        if validation.allowed:
            return {"validation": validation}
        # One rewrite for fixable rejections (syntax, unknown function or column...). The new SQL
        # goes through the same validator; writes, extra statements and sensitive fields end here.
        if validation.repairable and state["audit"].sql_attempts < 2:
            return {"validation": validation}
        return {
            "validation": validation,
            "status": "denied",
            "code": validation.code.value,
            "answer": validation.message,
        }

    @staticmethod
    def _after_validation(state):
        if "status" in state:
            return END
        return "execute" if state["validation"].allowed else "generate"

    async def _execute(self, state):
        draft = state["draft"]

        def record_attempt(query):
            state["audit"].query = query

        query = await state["source"].executor.execute_async(
            draft.sql,
            self._parameters(state),
            request_id=state["audit"].request_id,
            on_attempt=record_attempt,
        )
        state["audit"].query = query
        if query.status != "success":
            if query.retry_hint and state["audit"].sql_attempts < 2:
                # The database refused a valid-looking query: one rewrite, guided only by a fixed
                # hint for the error class (never the driver message, which may quote data).
                feedback = f"O banco recusou a consulta na execução. {query.retry_hint}"
                return {
                    "validation": ValidationResult(
                        allowed=False, code=query.code, message=feedback, repairable=True
                    )
                }
            return {"status": query.status, "code": query.code.value, "answer": query.message}
        return {}

    @staticmethod
    def _after_execute(state):
        if "status" in state:
            return END
        return "answer" if state["validation"].allowed else "generate"

    def _answer(self, state):
        if state["plan"].get("mode") == "exploration":
            chart, chart_note = check_chart(state["draft"].chart, state["audit"].query)
            return {
                "status": "success",
                "code": "ok",
                "answer": render_exploration_answer(state["draft"].title, state["audit"].query),
                "chart": chart,
                "chart_note": chart_note,
            }
        return {
            "status": "success",
            "code": "ok",
            "answer": render_answer(state["plan"], state["audit"].query, state["provider"].is_demo),
        }

    async def _narrate(self, state):
        """Best effort: any failure keeps the deterministic answer already in the state."""
        if not self.settings.narrative_enabled:
            return {"narrative_note": "Resposta em linguagem natural desativada."}
        if not state["source"].allow_rows_to_llm:
            return {
                "narrative_note": "Esta base não permite que a IA leia os resultados; a resposta "
                "mostra apenas os valores calculados. Mude isso nas configurações da base."
            }
        if state["provider"].is_demo:
            return {"narrative_note": "Modo demonstração: sem resposta em linguagem natural."}
        audit, plan, draft = state["audit"], state["plan"], state["draft"]
        query = audit.query
        remaining = state["budget"] - (perf_counter() - audit.started) - 2
        if remaining < 3:
            return {"narrative_note": "Sem tempo restante para a resposta em linguagem natural."}
        rows = shared_rows(query, self.settings.narrative_max_rows)
        period = plan.get("period")
        metric = plan.get("metric_evidence")
        exploratory = isinstance(draft, ExploratoryDraft)
        analysis = {
            "mode": "exploration" if exploratory else "metric",
            "title": draft.title if exploratory else metric.description,
            "assumptions": list(draft.assumptions) if exploratory else [],
            "limitations": plan.get("limitations", []),
        }
        if metric:
            analysis["metric"] = {"name": metric.name, "unit": metric.unit}
        if period:
            analysis["period"] = {
                "start": period.start.isoformat(),
                "end_exclusive": period.end_exclusive.isoformat(),
            }
        if plan.get("region"):
            analysis["filters"] = {"region": plan["region"]}
        if state.get("chart"):
            # The app draws it from every returned row; the model only sees a sample of them.
            analysis["chart"] = {**state["chart"].model_dump(), "drawn_by_app": True}
        payload = {
            "question": state["request"].question,
            "conversation": self._conversation(state),
            "language": self._locale(state),
            "reference_date": state["reference_date"],
            "analysis": analysis,
            "result": {
                "columns": query.columns,
                "rows": rows,
                "row_count": query.row_count,
                "rows_shared": len(rows),
                "partial": query.truncated or len(rows) < query.row_count,
            },
            "conventions": {"currency": "BRL"} if state["source"].kind == "sample" else {},
        }
        try:
            async with asyncio.timeout(remaining):
                reply = await self._call(state, NarrativeDraft, NARRATIVE_INSTRUCTIONS, payload)
        except ProviderError as error:
            return {"narrative_note": f"Resposta em linguagem natural indisponível ({error.code})."}
        except (TimeoutError, ValidationError, ValueError, TypeError):
            return {"narrative_note": "Resposta em linguagem natural indisponível."}
        # The question, the date and the size of the result are context, not claims to verify.
        ignore = [state["request"].question, state["reference_date"]]
        checked, unverified = check_numbers(
            [reply.answer, *reply.highlights, *reply.caveats],
            rows,
            query.columns,
            ignore,
            known_values=(query.row_count,),
            locale=self._locale(state),
        )
        return {
            "narrative": NarrativeEvidence(
                answer=reply.answer,
                highlights=reply.highlights,
                caveats=reply.caveats,
                follow_ups=reply.follow_ups,
                rows_shared=len(rows),
                numbers_checked=checked,
                unverified_numbers=unverified,
            )
        }
