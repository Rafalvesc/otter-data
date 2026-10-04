import argparse
import asyncio
from datetime import date

from pydantic import ValidationError

from backend.agents.analyst import AnalystService
from backend.config import Settings
from backend.llm.factory import build_provider
from backend.models.analysis import AskRequest
from backend.runtime import create_loop


def main() -> None:
    parser = argparse.ArgumentParser(description="Pergunte ao Otter Data pela linha de comando.")
    parser.add_argument("question")
    parser.add_argument("--reference-date", type=date.fromisoformat)
    parser.add_argument(
        "--demo", action="store_true", help="Demonstração roteirizada, sem LLM ou custo de API."
    )
    args = parser.parse_args()
    try:
        settings = Settings(llm_provider="demo") if args.demo else Settings()
        provider = build_provider(settings)
        request = AskRequest(question=args.question, reference_date=args.reference_date)
        with asyncio.Runner(loop_factory=create_loop) as runner:
            result = runner.run(AnalystService(settings, provider).ask(request))
    except ValidationError:
        parser.exit(1, "Verifique a pergunta, a data e a configuração .env.\n")
    print(result.model_dump_json(indent=2))
    raise SystemExit({"success": 0, "clarification": 0, "error": 1, "denied": 2}[result.status])


if __name__ == "__main__":
    main()
