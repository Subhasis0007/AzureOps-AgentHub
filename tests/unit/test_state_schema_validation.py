from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from core.state.schema import ACRGEState, DiagnosticReport, IncidentEvent, IncidentSource, PullRequestSpec


def test_incident_event_coerces_detected_at_to_utc() -> None:
    event = IncidentEvent(
        source=IncidentSource.ADF,
        source_event_id="run-1",
        title="ADF failure",
        description="Schema mapping broke",
        service_name="adf-pipeline-a",
        detected_at=datetime(2026, 4, 28, 12, 0, 0),
    )
    assert event.detected_at.tzinfo is not None


def test_diagnostic_report_requires_root_cause_hypothesis() -> None:
    with pytest.raises(ValidationError):
        DiagnosticReport(
            incident_id="inc_12345678",
            summary="Some summary text",
            confidence=0.8,
            root_cause_hypotheses=[],
        )


def test_pull_request_spec_enforces_branch_prefix() -> None:
    pr = PullRequestSpec(
        incident_id="inc_12345678",
        repository="acrge-lite",
        source_branch="feature/temp",
        target_branch="main",
        title="Fix incident inc_12345678",
        body="This is a remediation proposal with enough detail for validation.",
    )
    assert pr.source_branch.startswith("acrge/fix/")


def test_acrge_state_update_from_node_roundtrip(base_state: ACRGEState) -> None:
    updated = base_state.update_from_node({"log_summary": "found likely config drift"})
    assert updated.log_summary == "found likely config drift"
    assert updated.incident.incident_id == base_state.incident.incident_id
