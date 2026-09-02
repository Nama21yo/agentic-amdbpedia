from __future__ import annotations

import pytest
from pydantic import ValidationError

from config import Settings


def clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GROQ_API_KEY",
        "GROQ_MODEL_FAST",
        "GROQ_MODEL_REASONING",
        "RETRIEVAL_CONFIDENCE_THRESHOLD",
    ):
        monkeypatch.delenv(name, raising=False)


def test_settings_load_valid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_placeholder")
    monkeypatch.setenv("RETRIEVAL_CONFIDENCE_THRESHOLD", "0.42")

    settings = Settings(_env_file=None)

    assert settings.groq_api_key == "gsk_test_placeholder"
    assert settings.retrieval_confidence_threshold == 0.42


def test_settings_missing_groq_key_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_settings_env(monkeypatch)

    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        Settings(_env_file=None)


def test_settings_malformed_threshold_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_placeholder")
    monkeypatch.setenv("RETRIEVAL_CONFIDENCE_THRESHOLD", "not-a-float")

    with pytest.raises(ValidationError, match="RETRIEVAL_CONFIDENCE_THRESHOLD"):
        Settings(_env_file=None)
