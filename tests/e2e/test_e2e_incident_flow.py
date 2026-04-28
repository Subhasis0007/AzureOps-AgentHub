from __future__ import annotations

from agents.code_generation.agent import CodeGenerationAgent
from agents.diagnostic.agent import DiagnosticAgent
from agents.governance.agent import GovernanceAgent
from agents.log_analysis.agent import LogAnalysisAgent
from agents.supervisor.agent import SupervisorAgent
from core.config.policy_loader import GovernancePolicy
from core.state.schema import ACRGEState
from services.ingest.normalizers import normalize_event


def test_e2e_devops_to_governance_flow(tmp_path) -> None:
    payload = {
        "eventType": "ms.vss-pipelines.job-state-changed-event",
        "resource": {
            "status": "failed",
            "result": "failed",
            "definition": {"name": "deploy-api"},
        },
    }

    incident = normalize_event("devops", payload, environment="dev")
    state = ACRGEState(incident=incident)

    (tmp_path / "pipelines").mkdir(parents=True, exist_ok=True)
    (tmp_path / "pipelines" / "ci.yml").write_text("name: ci\n", encoding="utf-8")

    state = SupervisorAgent().run(state)
    state = DiagnosticAgent().run(state)
    state = LogAnalysisAgent().run(state)
    state = CodeGenerationAgent(repo_root=tmp_path).run(state)
    state = GovernanceAgent(policy=GovernancePolicy()).run(state)

    assert state.incident.source == "azure_devops"
    assert state.diagnostic_report is not None
    assert state.pr_spec is not None
    assert state.governance_decision is not None
    assert len(state.audit_trail) >= 1
