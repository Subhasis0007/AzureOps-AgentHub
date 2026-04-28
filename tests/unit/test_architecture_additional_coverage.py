from __future__ import annotations

import pytest

from agents.governance.tools.policy_rules import GovernanceRuleEngine
from agents.supervisor.agent import SupervisorAgent
from core.config.policy_loader import GovernancePolicy
from core.state.schema import ACRGEState
from services.ingest.normalizers import normalize_event


def test_state_rejects_unknown_field(base_state: ACRGEState) -> None:
    with pytest.raises(ValueError):
        base_state.update_from_node({"unknown_field": "not-allowed"})


def test_supervisor_routes_data_incident_to_log_analysis(base_state: ACRGEState) -> None:
    state = base_state.update_from_node(
        {
            "incident": {
                **base_state.incident.model_dump(mode="python"),
                "title": "ADF schema drift failure",
                "description": "databricks schema mismatch in silver layer",
            }
        }
    )
    routed = SupervisorAgent().run(state)
    assert any("log_analysis_agent" in step for step in routed.reasoning_trace)


def test_governance_rule_engine_can_auto_approve_low_risk_non_prod() -> None:
    policy = GovernancePolicy(
        auto_approve_max_risk="medium",
        confidence_threshold=0.6,
        protected_branches=["main"],
        require_human_for_production=True,
        require_human_for_data_mutation=True,
    )
    result = GovernanceRuleEngine().evaluate(
        policy=policy,
        environment="dev",
        target_branch="feature/safe-change",
        risk_level="low",
        confidence=0.95,
        touches_data_mutation=False,
    )
    assert result.requires_human is False
    assert result.reasons == []


def test_normalizer_rejects_unsupported_event_type() -> None:
    with pytest.raises(ValueError):
        normalize_event("unsupported", {}, environment="dev")
