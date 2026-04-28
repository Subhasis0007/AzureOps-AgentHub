from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_to: str
    reason: str


def to_langgraph_node(decision: RouteDecision) -> str:
    """Map a supervisor route to a graph node name."""
    mapping = {
        "diagnostic_agent": "diagnostic",
        "log_analysis_agent": "log_analysis",
        "code_generation_agent": "code_generation",
        "governance_agent": "governance",
        "cost_optimization_agent": "cost_optimization",
        "human_escalation": "governance",
    }
    return mapping.get(decision.route_to, "governance")
