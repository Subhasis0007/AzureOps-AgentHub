from __future__ import annotations

from core.state.schema import ACRGEState
from services.executor.function_app import execute_route_pipeline, run_incident_pipeline


def test_execute_route_pipeline_diagnostic_branch(base_state: ACRGEState) -> None:
    out = execute_route_pipeline(base_state, "diagnostic_agent")

    assert out.diagnostic_report is not None
    assert out.log_summary
    assert out.pr_spec is not None
    assert out.governance_decision is not None


def test_execute_route_pipeline_human_escalation_branch(base_state: ACRGEState) -> None:
    out = execute_route_pipeline(base_state, "human_escalation")

    assert out.governance_decision is not None


def test_run_incident_pipeline_uses_supervisor_route(base_state: ACRGEState) -> None:
    out = run_incident_pipeline(base_state)

    assert any(step.startswith("supervisor.route=") for step in out.reasoning_trace)
    assert out.governance_decision is not None
