from __future__ import annotations

import pytest

from mcp_server.consent import ConsentRequiredError, require_consent


def test_consent_required_decorator_blocks_until_approved() -> None:
    @require_consent()
    def destructive_action() -> str:
        return "done"

    with pytest.raises(ConsentRequiredError):
        destructive_action()

    @require_consent(approved=True)
    def approved_action() -> str:
        return "done"

    assert approved_action() == "done"
