# Development

How to run Otter Data from source, configure it, test it and build the Windows installer.

## Requirements

Windows, Python 3.12 and [Ollama](https://ollama.com). Docker Desktop only for the full mode.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock -r requirements-desktop.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

## Light mode (no Docker)

Without a `.env`, the project runs like the installed app: the sample data is a DuckDB copy created in `%LOCALAPPDATA%\OtterData`.

```powershell
.\.venv\Scripts\python.exe -m desktop   # desktop app (its own window)
.\.venv\Scripts\python.exe -m backend   # web interface at http://127.0.0.1:8000
```

## Full mode, with PostgreSQL in Docker

Enables the versioned metrics and database accounts with separate privileges (administration, loading and read-only analysis).

```powershell
.\.venv\Scripts\python.exe -m scripts.init_env           # creates .env with random passwords
docker compose up -d --wait postgres
.\.venv\Scripts\python.exe -m scripts.seed_database      # deterministic, idempotent load
docker compose up -d --build --wait backend              # API and interface at http://localhost:8000
```

The backend container reaches the host's Ollama through `host.docker.internal`. Once `.env` exists, `python -m desktop` also uses PostgreSQL and starts the container by itself if Docker is running.

## Configuration

All variables are in [`.env.example`](../.env.example). The installed app reads a `.env` placed in `%LOCALAPPDATA%\OtterData`. The most common:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_MODEL` | `gemma4:31b-cloud` | Default model |
| `OLLAMA_MODELS` | empty | Extra cloud models in the picker (local models show up automatically) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama address |
| `LOCAL_CONTEXT_TOKENS` | `16384` | Context window for local models (Ollama's own default, 4096, silently cuts long instructions) |
| `HISTORY_TURNS` | `6` | Previous exchanges sent as context |
| `NARRATIVE_MAX_ROWS` | `50` | Maximum result rows read by the AI |
| `OTTER_AUTHOR` | empty | What the assistant says when asked who made it |
| `LLM_PROVIDER` | `ollama` | `demo` uses scripted answers, no model (tests) |

## Tests and lint

```powershell
.\.venv\Scripts\python.exe -m pytest                     # offline tests (unit and security)
.\.venv\Scripts\python.exe -m pytest --run-integration   # includes real PostgreSQL (full mode)
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check backend desktop scripts tests
```

CI ([ci.yml](../.github/workflows/ci.yml)) runs lint and the offline tests on every push to `main`.

The reference answers in [`evaluation/datasets/golden_questions.json`](../evaluation/datasets/golden_questions.json) are computed in Python from the data generator; regenerate them with `python -m scripts.export_golden` after changing the sample data.

## Evaluating a model

`scripts/evaluate.py` asks the five reference questions to a real model and compares the numbers with the golden answers. It calls Ollama, so it is not part of the test suite:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate --model qwen2.5:7b --mode embedded --language en
.\.venv\Scripts\python.exe -m scripts.evaluate --mode postgres --language pt   # default model, full mode
```

`embedded` uses the built-in DuckDB sample (the installed app's setup); `postgres` needs the full mode running.

## Building the installer

Pushing a `v*` tag triggers [release.yml](../.github/workflows/release.yml), which runs the tests, packages the app with PyInstaller and builds the `.exe` with Inno Setup on the Releases page:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

To build locally: `pip install pyinstaller==6.22.3`, then `pyinstaller packaging/otterdata.spec --noconfirm` (output in `dist/OtterData/`) and, with [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed, `iscc packaging\installer.iss`.

## Project layout

```
backend/
  agents/       analysis flow (LangGraph), answer writing, number check, charts
  api/          FastAPI routes: questions (with NDJSON progress), models and sources
  llm/          Ollama adapter, model catalog, prompts, demo mode
  sample/       deterministic synthetic data and the built-in sample database (DuckDB)
  semantic/     versioned metrics and schema documentation
  sources/      your own sources: catalog, connections, executor and registry
  tools/        SQL validator, PostgreSQL executor and error hints
  database/     PostgreSQL schema and roles (full mode)
desktop/        desktop app (pywebview) and splash screen
frontend/       interface (HTML, CSS and JavaScript, no build step; i18n.js holds English)
packaging/      PyInstaller and Inno Setup
scripts/        utilities: .env, database load, command-line questions, model evaluation, icons
tests/          unit, SQL security and PostgreSQL integration tests
evaluation/     reference questions and expected answers
docs/           security, verification history, project plan and images
```
