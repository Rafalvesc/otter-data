import json
from pathlib import Path

from backend.sample.data import (
    DATASET_VERSION,
    REFERENCE_DATE,
    SEED,
    fingerprint,
    generate_dataset,
    normalize,
    reference_answers,
)
from scripts.golden_questions import QUESTIONS


def build_golden() -> dict:
    data = generate_dataset()
    expected = reference_answers(data)
    return {
        "dataset_version": DATASET_VERSION,
        "seed": SEED,
        "fingerprint": fingerprint(data),
        "reference_date": REFERENCE_DATE.isoformat(),
        "timezone": "America/Sao_Paulo",
        "currency": "BRL",
        "counts": {table: len(rows) for table, rows in data.items()},
        "questions": [
            normalize({**question, "expected": expected[question["id"]]}) for question in QUESTIONS
        ],
    }


def main() -> None:
    path = Path("evaluation/datasets/golden_questions.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_golden(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Referências determinísticas gravadas em {path}.")


if __name__ == "__main__":
    main()
