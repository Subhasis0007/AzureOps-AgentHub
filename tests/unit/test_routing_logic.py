from __future__ import annotations

from typing import Any

from agents.supervisor.agent import SupervisorAgent
from agents.supervisor.router import RouteDecision, to_langgraph_node
from core.state.schema import ACRGEState


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


def test_supervisor_heuristic_routes_pipeline_to_diagnostic(base_state: ACRGEState) -> None:
    agent = SupervisorAgent()
    routed = agent.run(base_state)
    assert any("diagnostic_agent" in step for step in routed.reasoning_trace)


def test_supervisor_escalates_low_confidence_llm(base_state: ACRGEState) -> None:
    llm = FakeStructuredLLM(
        {
            "route_to": "diagnostic_agent",
            "confidence": 0.41,
            "rationale": "low confidence output from model",
            "incident_class": "pipeline",
        }
    )
    agent = SupervisorAgent(llm_client=llm, confidence_gate=0.65)
    routed = agent.run(base_state)
    assert routed.governance_decision is not None
    assert routed.governance_decision.requires_human_approval is True


def test_router_mapping_defaults_to_governance() -> None:
    decision = RouteDecision(route_to="unknown", reason="fallback")
    assert to_langgraph_node(decision) == "governance"
