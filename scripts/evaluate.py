"""Ask the reference questions to a real model and compare the numbers with the golden answers.

Calls the configured Ollama model (local or hosted); it is not part of the offline test suite.

    python -m scripts.evaluate --model qwen2.5:3b --mode embedded
    python -m scripts.evaluate --mode postgres --language pt
"""

import argparse
import asyncio
import json
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from backend.agents.analyst import AnalystService
from backend.config import Settings
from backend.llm.ollama_provider import OllamaProvider
from backend.models.analysis import AskRequest
from backend.runtime import create_loop

GOLDEN = Path("evaluation/datasets/golden_questions.json")
ENGLISH = {
    "new_customers": "How many customers signed up in September 2026?",
    "received_revenue": "What was the received revenue in September 2026?",
    "revenue_by_region": "Which regions had the highest received revenue in September 2026?",
    "monthly_revenue": "How did received revenue evolve from January to September 2026?",
    "cancelled_orders": "How many orders were cancelled in September 2026?",
}


def numbers(rows: list[dict]) -> list[tuple]:
    """Each row as its sorted numeric values, so column names and labels may differ."""
    result = []
    for row in rows:
        values = []
        for value in row.values():
            try:
                values.append(round(Decimal(str(value)), 2))
            except (InvalidOperation, ValueError):
                continue
        result.append(tuple(sorted(values)))
    return sorted(result)


def matches(expected: list[dict], rows: list[dict]) -> bool:
    got = numbers(rows)
    return len(got) == len(expected) and all(
        any(set(want) <= set(row) for row in got) for want in numbers(expected)
    )


async def evaluate(settings: Settings, model: str, language: str) -> list[dict]:
    analyst = AnalystService(settings, OllamaProvider(settings, model))
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    report = []
    for item in golden["questions"]:
        question = ENGLISH[item["id"]] if language == "en" else item["question"]
        response = await analyst.ask(
            AskRequest(question=question, reference_date=date(2026, 9, 30), language=language)
        )
        rows = response.query.rows if response.query and response.status == "success" else []
        narrative = response.narrative
        report.append(
            {
                "id": item["id"],
                "correct": response.status == "success" and matches(item["expected"], rows),
                "status": response.status,
                "code": response.code,
                "mode": response.analysis_mode,
                "sql_attempts": response.sql_attempts,
                "unverified": narrative.unverified_numbers if narrative else None,
                "seconds": round(response.duration_ms / 1000, 1),
            }
        )
        print(json.dumps(report[-1], ensure_ascii=False), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", help="Ollama model; defaults to OLLAMA_MODEL")
    parser.add_argument("--mode", choices=["embedded", "postgres"], default="embedded")
    parser.add_argument("--language", choices=["en", "pt"], default="en")
    args = parser.parse_args()
    if args.mode == "embedded":
        # The installed app's setup: no PostgreSQL credentials, sample data in a local DuckDB.
        data_dir = Path(tempfile.gettempdir()) / "otterdata-evaluation"
        settings = Settings(_env_file=None, analytics_password=None, data_dir=str(data_dir))
    else:
        settings = Settings()
    model = args.model or settings.ollama_model
    with asyncio.Runner(loop_factory=create_loop) as runner:
        report = runner.run(evaluate(settings, model, args.language))
    correct = sum(item["correct"] for item in report)
    print(f"{model} · {args.mode} · {args.language}: {correct}/{len(report)} correct")


if __name__ == "__main__":
    main()
