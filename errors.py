"""Client-safe exception taxonomy for the mapping assistant."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientSafeError(Exception):
    """Base class for errors that may be serialized at MCP boundaries."""

    message: str
    error_type: str = "client_safe_error"

    def __str__(self) -> str:
        return self.message

    def to_payload(self) -> dict[str, str]:
        return {"status": "error", "error_type": self.error_type, "message": self.message}


class RetrievalUnavailableError(ClientSafeError):
    """Raised when vector retrieval or query encoding is unavailable."""

    def __init__(self, message: str = "Retrieval service is unavailable") -> None:
        super().__init__(message=message, error_type="retrieval_unavailable")


class LLMUnavailableError(ClientSafeError):
    """Raised when the configured LLM provider remains unavailable."""

    def __init__(self, message: str = "LLM service is unavailable") -> None:
        super().__init__(message=message, error_type="llm_unavailable")


class AssistantValidationError(ClientSafeError):
    """Raised for invalid user or tool payload input."""

    def __init__(self, message: str = "Input validation failed") -> None:
        super().__init__(message=message, error_type="validation")


class GuardrailRejection(ClientSafeError):
    """Raised when a prompt-injection or policy guardrail blocks a request."""

    def __init__(self, message: str = "Prompt-injection attempt detected") -> None:
        super().__init__(message=message, error_type="guardrail_rejection")
