import base64
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
import webview

# Installed (PyInstaller) builds unpack the app files into sys._MEIPASS.
FROZEN = getattr(sys, "frozen", False)
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
ASSETS = ROOT / "frontend" / "assets"
ICON = ASSETS / "otter.ico"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OtterData"
LOG_FILE = DATA_DIR / "desktop.log"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

logger = logging.getLogger("otterdata.desktop")


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ollama_running(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/version", timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


class Backend:
    """Runs the FastAPI app in a background thread on a private loopback port."""

    def __init__(self):
        self.port = free_port()
        config = uvicorn.Config(
            "backend.main:app",
            host="127.0.0.1",
            port=self.port,
            loop="backend.runtime:create_loop",
            log_level="warning",
            log_config=None,  # keep uvicorn errors in desktop.log (no console when installed)
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="otterdata-api", daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self, timeout: float = 30) -> bool:
        self.thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and self.thread.is_alive():
            if self.server.started:
                return True
            time.sleep(0.1)
        return False

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


class SplashApi:
    """The only object exposed to the splash page's JavaScript: a retry button."""

    def __init__(self, launcher: "Launcher"):
        self._launcher = launcher

    def retry(self) -> None:
        threading.Thread(target=self._launcher.boot, daemon=True).start()


class Launcher:
    """Boot sequence reported on the splash screen."""

    def __init__(self):
        self.window = None
        self.backend: Backend | None = None
        self._lock = threading.Lock()

    def report(self, text: str, state: str = "working") -> None:
        logger.info("%s: %s", state, text)
        if self.window:
            self.window.evaluate_js(f"setStatus({json.dumps(text)}, {json.dumps(state)})")

    def boot(self) -> None:
        if not self._lock.acquire(blocking=False):
            return
        try:
            self._boot()
        except Exception:
            logger.exception("startup failed")
            self.report("Unexpected error while starting. Details in " + str(LOG_FILE), "error")
        finally:
            self._lock.release()

    def _boot(self) -> None:
        from backend.config import get_settings

        settings = get_settings()
        if settings.embedded_sample:
            # No PostgreSQL configured (installed app): the sample base is a local DuckDB file.
            from backend.sample.data import DATASET_VERSION
            from backend.sample.embedded import build_database

            data_dir = Path(settings.data_dir) if settings.data_dir else DATA_DIR
            self.report("Preparing the sample data…")
            build_database(data_dir / f"sample-{DATASET_VERSION}.duckdb")
        else:
            if not self._database_ready(settings):
                return
        if settings.llm_provider == "ollama" and not ollama_running(settings.ollama_base_url):
            self.report(
                "Ollama did not respond. Install it from ollama.com or open the Ollama app; "
                "without it the app cannot answer. Continuing…",
                "warn",
            )
            time.sleep(2.5)
        if self.backend is None:
            self.report("Starting the local API…")
            backend = Backend()
            if not backend.start():
                self.report("The local API did not start. Details in " + str(LOG_FILE), "error")
                return
            self.backend = backend
        self.report("Ready!", "ready")
        self.window.load_url(self.backend.url)

    def _database_ready(self, settings) -> bool:
        """Source checkout with Docker: make sure the PostgreSQL sample is up."""
        host, port = settings.database_host, settings.database_port
        self.report("Looking for the database…")
        if not port_open(host, port):
            if not shutil.which("docker"):
                self.report("Database unavailable and Docker not found.", "error")
                return False
            self.report("Starting the database in Docker… this can take a few seconds.")
            try:
                subprocess.run(
                    ["docker", "compose", "up", "-d", "--wait", "postgres"],
                    cwd=ROOT,
                    timeout=240,
                    capture_output=True,
                    creationflags=NO_WINDOW,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                pass
            if not port_open(host, port, timeout=3):
                self.report("Could not start the database. Open Docker Desktop.", "error")
                return False
        return True


def splash_html() -> str:
    otter = base64.b64encode((ASSETS / "otter-mascot.webp").read_bytes()).decode()
    # The splash is shown before the API exists, so the image is inlined.
    template = (Path(__file__).with_name("splash.html")).read_text(encoding="utf-8")
    return template.replace("__OTTER__", otter)


def configure_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    # pythonw has no console; keep stray writes from libraries out of the void.
    if sys.stdout is None or sys.stderr is None:
        stream = open(LOG_FILE, "a", encoding="utf-8")  # noqa: SIM115
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream


def main() -> None:
    configure_logging()
    # Settings reads .env from the working directory: the checkout when run from source, the
    # data folder (%LOCALAPPDATA%\OtterData, optional) when installed.
    os.chdir(DATA_DIR if FROZEN else ROOT)
    launcher = Launcher()
    launcher.window = webview.create_window(
        "Otter Data",
        html=splash_html(),
        js_api=SplashApi(launcher),
        width=1320,
        height=880,
        min_size=(900, 620),
        background_color="#06101B",
    )
    try:
        webview.start(
            launcher.boot,
            private_mode=False,  # keep history and theme between sessions
            storage_path=str(DATA_DIR / "webview"),
            icon=str(ICON),
        )
    finally:
        if launcher.backend:
            launcher.backend.stop()
