from fastapi.testclient import TestClient

from backend.main import FRONTEND_DIR, app


def test_ui_is_served_with_strict_content_security_policy():
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/app.js")
        health = client.get("/health")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert "/static/app.js" in page.text
    policy = page.headers["content-security-policy"]
    assert "script-src 'self'" in policy and "font-src 'self'" in policy
    assert "unsafe-inline" not in policy
    assert script.status_code == 200 and script.headers["x-content-type-options"] == "nosniff"
    assert script.headers["cache-control"] == "no-cache"
    assert "content-security-policy" not in health.headers


def test_example_conversation_is_a_real_api_response():
    import json
    import re

    from backend.models.analysis import AskResponse

    for name in ("example.json", "example-en.json"):
        example = json.loads((FRONTEND_DIR / "assets" / name).read_text(encoding="utf-8"))
        response = AskResponse.model_validate(example["data"])
        assert response.status == "success" and response.query.status == "success"
        assert response.catalog_fields and response.interpretation is not None
        assert response.narrative is not None and not response.narrative.unverified_numbers
    # Every image the UI references must exist.
    for name in ("index.html", "app.js"):
        text = (FRONTEND_DIR / name).read_text(encoding="utf-8")
        for asset in re.findall(r"/static/assets/([\w.-]+\.(?:webp|png|json))", text):
            assert (FRONTEND_DIR / "assets" / asset).is_file(), asset


def test_ui_never_injects_response_text_as_html():
    for name in ("app.js", "i18n.js"):
        text = (FRONTEND_DIR / name).read_text(encoding="utf-8")
        assert "innerHTML" not in text and "insertAdjacentHTML" not in text
        assert "eval(" not in text


def test_every_interface_text_has_an_english_entry():
    """Each t("...") literal in app.js must exist in the English table of i18n.js."""
    import re

    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
    table = (FRONTEND_DIR / "i18n.js").read_text(encoding="utf-8")
    string = r'"((?:[^"\\]|\\.)*)"'
    keys = {unescape(key) for key in re.findall(r"^\s+" + string + ":", table, re.MULTILINE)}
    used = {unescape(text) for text in re.findall(r"\bt\(" + string, script)}
    # Conditional keys are written as t(cond ? "a" : "b"); both branches count.
    for pair in re.findall(r"\bt\([^()\"]*\? " + string + " : " + string + r"\)", script):
        used.update(unescape(text) for text in pair)
    assert len(used) > 150
    missing = sorted(used - keys)
    assert not missing, missing


def unescape(text: str) -> str:
    import json

    return json.loads(f'"{text}"')


def test_ui_uses_its_own_confirmation_dialog_instead_of_browser_popups():
    script = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
    page = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    for native in (
        "window.confirm",
        "window.alert",
        "window.prompt",
        "confirm(",
        "alert(",
        "prompt(",
    ):
        assert native not in script.replace("confirmAction(", ""), native
    assert 'id="confirm-dialog"' in page
