from __future__ import annotations

from agents.governance.agent import GovernanceAgent
from agents.governance.tools.policy_rules import GovernanceRuleEngine
from core.config.policy_loader import GovernancePolicy
from core.state.schema import ACRGEState, DiagnosticReport, PullRequestSpec


def test_rule_engine_requires_human_for_prod_and_main() -> None:
    policy = GovernancePolicy()
    engine = GovernanceRuleEngine()
    result = engine.evaluate(
        policy=policy,
        environment="prod",
        target_branch="main",
        risk_level="high",
        confidence=0.5,
        touches_data_mutation=True,
    )
    assert result.requires_human is True
    assert len(result.reasons) >= 3


def test_governance_agent_sets_decision_and_audit(base_state: ACRGEState) -> None:
    state = base_state.update_from_node(
        {
            "diagnostic_report": DiagnosticReport(
                incident_id=base_state.incident.incident_id,
                summary="Config drift suspected",
                confidence=0.9,
                taxonomy="config",
                root_cause_hypotheses=["Variable mismatch"],
            ),
            "pr_spec": PullRequestSpec(
                incident_id=base_state.incident.incident_id,
                repository="acrge-lite",
                source_branch="acrge/fix/test",
                target_branch="feature/ops-fix",
                title="Fix config issue",
                body="Valid remediation notes that satisfy minimum length.",
                risk_level="low",
            ),
        }
    )

    policy = GovernancePolicy(auto_approve_max_risk="medium", confidence_threshold=0.65)
    agent = GovernanceAgent(policy=policy)
    out = agent.run(state)

    assert out.governance_decision is not None
    assert len(out.audit_trail) == 1
