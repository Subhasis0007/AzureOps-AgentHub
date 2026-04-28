from __future__ import annotations

from typing import Any

import pytest

from core.state.schema import ACRGEState, IncidentEvent, IncidentSource


class FakeStructuredLLM:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
    ) -> dict[str, Any]:
        return dict(self._payload)


@pytest.fixture
def base_incident() -> IncidentEvent:
    return IncidentEvent(
        source=IncidentSource.AZURE_DEVOPS,
        source_event_id="build-123",
        title="Pipeline failure in release stage",
        description="Deployment job failed after config variable expansion.",
        service_name="acrge-api",
        environment="dev",
    )


@pytest.fixture
def base_state(base_incident: IncidentEvent) -> ACRGEState:
    return ACRGEState(incident=base_incident)
