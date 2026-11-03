import pytest

from app.config import Settings


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("INVITATION_ORIGIN", "https://ejemplo.invalid")
    settings = Settings()
    assert settings.log_level == "DEBUG"
    assert settings.invitation_origin == "https://ejemplo.invalid"
