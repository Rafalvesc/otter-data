import pytest
from pydantic import ValidationError

from backend.config import Settings


def test_runtime_credentials_are_always_analytics_only(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "datapilot_admin")
    settings = Settings(_env_file=None, analytics_password="test-only-password")
    assert settings.analytics_url.username == "analytics_agent"
    assert "test-only-password" not in repr(settings)
    assert "test-only-password" not in str(settings.analytics_url)


@pytest.mark.parametrize("field,value", [("max_rows", 10001), ("query_timeout_seconds", 0)])
def test_limits_cannot_exceed_configured_bounds(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, analytics_password="test-only-password", **{field: value})
