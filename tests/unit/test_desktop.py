import json
import urllib.request

import pytest

pytest.importorskip("webview")

from desktop.app import Backend, SplashApi, free_port, port_open, splash_html  # noqa: E402


def test_splash_is_self_contained_and_scriptable():
    html = splash_html()
    assert "__OTTER__" not in html and "data:image/webp;base64," in html
    assert "function setStatus" in html and "pywebview.api.retry" in html


def test_splash_exposes_only_the_retry_action():
    public = [name for name in dir(SplashApi(object())) if not name.startswith("_")]
    assert public == ["retry"]


def test_embedded_api_starts_on_a_private_loopback_port_and_stops():
    backend = Backend()
    assert backend.url.startswith("http://127.0.0.1:")
    try:
        assert backend.start(timeout=20)
        with urllib.request.urlopen(f"{backend.url}health", timeout=5) as response:
            assert json.load(response)["status"] == "ok"
        with urllib.request.urlopen(backend.url, timeout=5) as response:
            assert "Content-Security-Policy" in response.headers
    finally:
        backend.stop()
    assert not backend.thread.is_alive()
    assert not port_open("127.0.0.1", backend.port, timeout=0.5)


def test_free_port_returns_an_unused_port():
    port = free_port()
    assert 1024 < port < 65536 and not port_open("127.0.0.1", port, timeout=0.5)
