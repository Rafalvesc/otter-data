"""Models the user may pick: installed Ollama models and configured Ollama cloud models.

Only models listed here can be requested; arbitrary names from the client are refused.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

import httpx2

from backend.config import Settings

CACHE_SECONDS = 20


@dataclass(frozen=True)
class ModelOption:
    id: str
    provider: str
    model: str
    location: str  # "local", "cloud", "api" or "demo"
    size: str | None = None
    parameters: str | None = None

    def public(self) -> dict:
        return asdict(self)


def is_cloud_model(name: str) -> bool:
    return name.endswith("-cloud") or name.endswith(":cloud")


def human_size(size: int | None) -> str | None:
    if not size:
        return None
    gigabytes = size / 1024**3
    return f"{gigabytes:.1f} GB".replace(".", ",") if gigabytes >= 1 else f"{size / 1024**2:.0f} MB"


def split_names(value: str) -> list[str]:
    return [name.strip() for name in value.split(",") if name.strip()]


def fetch_ollama_tags(base_url: str) -> list[dict]:
    response = httpx2.get(f"{base_url.rstrip('/')}/api/tags", timeout=2, follow_redirects=False)
    response.raise_for_status()
    return response.json().get("models", [])


class ModelCatalog:
    def __init__(self, settings: Settings, fetch_tags: Callable[[str], list[dict]] | None = None):
        self._settings = settings
        self._fetch_tags = fetch_tags or fetch_ollama_tags
        self._cache: tuple[float, list[ModelOption]] | None = None
        self._lock = threading.Lock()

    @property
    def default_id(self) -> str:
        provider = self._settings.llm_provider
        return f"{provider}:{self._settings.llm_model or 'scripted'}"

    def options(self) -> list[ModelOption]:
        with self._lock:
            if self._cache and time.monotonic() - self._cache[0] < CACHE_SECONDS:
                return self._cache[1]
            options = self._discover()
            self._cache = (time.monotonic(), options)
            return options

    def resolve(self, model_id: str) -> ModelOption | None:
        return next((option for option in self.options() if option.id == model_id), None)

    def _discover(self) -> list[ModelOption]:
        settings = self._settings
        options: dict[str, ModelOption] = {}
        if settings.llm_provider == "demo":
            options["demo:scripted"] = ModelOption("demo:scripted", "demo", "scripted", "demo")
        try:
            tags = self._fetch_tags(settings.ollama_base_url)
        except (httpx2.HTTPError, ValueError):
            tags = []
        for tag in tags:
            name = str(tag.get("name") or tag.get("model") or "")
            details = tag.get("details") or {}
            families = " ".join(details.get("families") or [details.get("family") or ""])
            if not name or "embed" in name or "bert" in families:
                continue  # embedding models cannot chat
            cloud = is_cloud_model(name) or bool(tag.get("remote_host"))
            options[f"ollama:{name}"] = ModelOption(
                id=f"ollama:{name}",
                provider="ollama",
                model=name,
                location="cloud" if cloud else "local",
                size=None if cloud else human_size(tag.get("size")),
                parameters=details.get("parameter_size") or None,
            )
        # Cloud models work without `ollama pull`; offer the configured ones even if not listed.
        for name in [settings.ollama_model, *split_names(settings.ollama_models)]:
            options.setdefault(
                f"ollama:{name}",
                ModelOption(
                    f"ollama:{name}", "ollama", name, "cloud" if is_cloud_model(name) else "local"
                ),
            )
        order = {"cloud": 0, "local": 1, "demo": 2}
        return sorted(options.values(), key=lambda option: (order[option.location], option.model))
