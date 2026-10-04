from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.query import QueryResult

Metric = Literal["new_customers", "received_revenue", "cancelled_orders"]
Dimension = Literal["total", "region", "month"]
Region = Literal["South", "Southeast", "Northeast", "North", "Central-West"]  # sample REGIONS


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _plain_text(value: str) -> str:
    value = value.strip()
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ValueError("Texto com caracteres de controle.")
    return value


class ConversationTurn(StrictModel):
    """An earlier exchange of the same conversation, sent back by the client as context.

    Untrusted like the question itself; answers are dropped server-side for sources whose
    result rows may not be shown to the model.
    """

    question: str = Field(min_length=1, max_length=2000)
    answer: str | None = Field(default=None, max_length=1500)

    @field_validator("question", "answer")
    @classmethod
    def plain(cls, value: str | None) -> str | None:
        return None if value is None else _plain_text(value)


class AskRequest(StrictModel):
    question: str = Field(min_length=1, max_length=2000)
    reference_date: date | None = None
    source_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    model: str | None = Field(
        default=None, max_length=140, pattern=r"^(ollama|demo):[A-Za-z0-9._:/-]{1,120}$"
    )
    history: list[ConversationTurn] = Field(default_factory=list, max_length=8)
    # Language the model writes in; the interface translates its own fixed texts.
    language: Literal["pt", "en"] = "en"

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(character) < 32 and character not in "\n\t" for character in value):
            raise ValueError("Informe uma pergunta válida.")
        return value

    @field_validator("model")
    @classmethod
    def plain_model_name(cls, value: str | None) -> str | None:
        if value is not None and (".." in value or value.endswith(("/", ":"))):
            raise ValueError("Nome de modelo inválido.")
        return value


class IntentDecision(StrictModel):
    action: Literal["analyze", "explore", "chat", "clarification", "denied", "unsupported"]
    metric: Metric | None
    dimension: Dimension
    start_date: str | None
    end_date: str | None
    region: Region | None
    clarification_question: str | None = Field(max_length=300)


class QueryParameter(StrictModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z_0-9]{0,62}$")
    value: str | int | float | bool | None


class SQLDraft(StrictModel):
    sql: str = Field(min_length=1, max_length=16000)
    parameters: list[QueryParameter] = Field(max_length=16)

    @model_validator(mode="after")
    def unique_parameters(self):
        if len({parameter.name for parameter in self.parameters}) != len(self.parameters):
            raise ValueError("Nomes de parâmetros devem ser únicos.")
        return self

    def parameter_dict(self) -> dict:
        return {parameter.name: parameter.value for parameter in self.parameters}


OutputName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z_0-9]{0,62}$")]


class ChartSpec(StrictModel):
    """A chart the model may request: a type and two output columns of its own SELECT.

    Checked against the returned rows before drawing (backend.agents.charts)."""

    type: Literal["bar", "line", "scatter", "pie"]
    x: OutputName
    y: OutputName


class ExploratoryDraft(SQLDraft):
    """Free-form SELECT for questions outside the versioned metrics; still fully validated."""

    title: str = Field(min_length=1, max_length=120)
    assumptions: list[Annotated[str, Field(min_length=1, max_length=240)]] = Field(max_length=5)
    chart: ChartSpec | None = None


Sentence = Annotated[str, Field(min_length=1, max_length=240)]


class NarrativeDraft(StrictModel):
    """Natural-language answer written by the model from the returned rows only."""

    answer: str = Field(min_length=1, max_length=1500)
    highlights: list[Sentence] = Field(max_length=4)
    caveats: list[Sentence] = Field(max_length=3)
    follow_ups: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(max_length=3)


class ChatReply(StrictModel):
    """Conversational answer for messages that do not need the database."""

    answer: str = Field(min_length=1, max_length=2500)
    follow_ups: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(max_length=3)


class NarrativeEvidence(StrictModel):
    answer: str
    highlights: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    rows_shared: int
    numbers_checked: int
    unverified_numbers: list[str] = Field(default_factory=list)


class Period(StrictModel):
    start: date
    end_exclusive: date
    timezone: str = "America/Sao_Paulo"


class MetricEvidence(StrictModel):
    name: Metric
    version: int
    description: str
    unit: str


class UsageEvidence(StrictModel):
    llm_calls: int = 0
    provider_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    complete: bool = True


class AskResponse(StrictModel):
    request_id: str
    status: Literal["success", "clarification", "denied", "error"]
    code: str
    answer: str
    provider: str
    model: str | None
    demo_mode: bool
    source_id: str | None = None
    source_name: str | None = None
    reference_date: date
    period: Period | None = None
    metric: MetricEvidence | None = None
    analysis_mode: Literal["metric", "exploration", "chat"] | None = None
    title: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    interpretation: IntentDecision | None = None
    catalog_fields: list[str] = Field(default_factory=list)
    narrative: NarrativeEvidence | None = None
    narrative_note: str | None = None
    chart: ChartSpec | None = None
    follow_ups: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    operational_plan: list[str] = Field(default_factory=list)
    sources: tuple[str, ...] = ()
    queries_executed: int = 0
    sql_attempts: int = 0
    query: QueryResult | None = None
    limitations: list[str] = Field(default_factory=list)
    usage: UsageEvidence = Field(default_factory=UsageEvidence)
    duration_ms: float
