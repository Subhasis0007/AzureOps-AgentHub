from __future__ import annotations

from pathlib import Path

from agents.code_generation.agent import CodeGenerationAgent
from core.state.schema import ACRGEState, DiagnosticReport


def test_code_generation_produces_pr_spec(base_state: ACRGEState, tmp_path: Path) -> None:
    state = base_state.update_from_node(
        {
            "diagnostic_report": DiagnosticReport(
                incident_id=base_state.incident.incident_id,
                summary="Likely config issue in pipeline",
                confidence=0.78,
                taxonomy="config",
                root_cause_hypotheses=["Config variable drift"],
            )
        }
    )

    (tmp_path / "pipelines").mkdir(parents=True, exist_ok=True)
    (tmp_path / "pipelines" / "ci.yml").write_text("name: ci\n", encoding="utf-8")

    agent = CodeGenerationAgent(repo_root=tmp_path)
    out = agent.run(state)

    assert out.pr_spec is not None
    assert out.pr_spec.source_branch.startswith("acrge/fix/")
    assert out.pr_spec.diff_patch
    assert "pr_payload_preview" in out.messages[-1].metadata
