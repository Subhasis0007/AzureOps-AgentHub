from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Protocol

from jinja2 import Environment, StrictUndefined
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field

from core.state.schema import ACRGEState, GovernanceDecision, GovernanceOutcome, MessageTrace


class StructuredLLM(Protocol):
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        model: str,
    ) -> dict[str, Any]:
        ...


class SupervisorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    source: str
    service_name: str
    environment: str
    title: str
    description: str
    existing_log_summary: str = ""


class SupervisorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_to: Literal[
        "diagnostic_agent",
        "log_analysis_agent",
        "code_generation_agent",
        "governance_agent",
        "cost_optimization_agent",
        "human_escalation",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=8, max_length=4000)
    incident_class: Literal["pipeline", "integration", "data", "platform", "other"] = "other"


SUPERVISOR_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["route_to", "confidence", "rationale", "incident_class"],
    "properties": {
        "route_to": {
            "type": "string",
            "enum": [
                "diagnostic_agent",
                "log_analysis_agent",
                "code_generation_agent",
                "governance_agent",
                "cost_optimization_agent",
                "human_escalation",
            ],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "rationale": {"type": "string", "minLength": 8},
        "incident_class": {
            "type": "string",
            "enum": ["pipeline", "integration", "data", "platform", "other"],
        },
    },
    "additionalProperties": False,
}


class SupervisorAgent:
    def __init__(self, llm_client: StructuredLLM | None = None, *, confidence_gate: float = 0.65) -> None:
        self._llm = llm_client
        self._confidence_gate = confidence_gate

    def run(self, state: ACRGEState) -> ACRGEState:
        agent_input = SupervisorInput(
            incident_id=state.incident.incident_id,
            source=str(state.incident.source),
            service_name=state.incident.service_name,
            environment=state.incident.environment,
            title=state.incident.title,
            description=state.incident.description,
            existing_log_summary=state.log_summary,
        )

        output = self._classify(agent_input)
        route_target = output.route_to

        if output.confidence < self._confidence_gate or state.incident.requires_human:
            route_target = "human_escalation"

        next_state = state.update_from_node(
            {
                "reasoning_trace": [
                    *state.reasoning_trace,
                    f"supervisor.route={route_target} confidence={output.confidence:.2f}",
                ],
                "messages": [
                    *state.messages,
                    MessageTrace(
                        role="assistant",
                        content=(
                            f"Supervisor routed incident to {route_target} "
                            f"(class={output.incident_class}, confidence={output.confidence:.2f})."
                        ),
                        metadata={"agent": "supervisor"},
                    ),
                ],
            }
        )

        if route_target == "human_escalation":
            decision = GovernanceDecision(
                incident_id=state.incident.incident_id,
                decision=GovernanceOutcome.NEEDS_HUMAN_REVIEW,
                requires_human_approval=True,
                reasons=[
                    "Supervisor confidence below threshold or incident requires human handling.",
                ],
            )
            next_state = next_state.update_from_node({"governance_decision": decision})

        return next_state

    def _classify(self, agent_input: SupervisorInput) -> SupervisorOutput:
        if self._llm is None:
            return self._heuristic_classify(agent_input)

        payload = self._llm.complete_json(
            system_prompt=self._render_system_prompt(),
            user_prompt=json.dumps(agent_input.model_dump(mode="json"), ensure_ascii=True),
            output_schema=SUPERVISOR_OUTPUT_SCHEMA,
            model="gpt-4o-mini",
        )
        Draft202012Validator(SUPERVISOR_OUTPUT_SCHEMA).validate(payload)
        return SupervisorOutput.model_validate(payload)

    def _heuristic_classify(self, agent_input: SupervisorInput) -> SupervisorOutput:
        text = f"{agent_input.title} {agent_input.description}".lower()
        if "deadletter" in text or "logic app" in text or "service bus" in text:
            return SupervisorOutput(
                route_to="diagnostic_agent",
                confidence=0.86,
                rationale="Integration-failure signals detected in incident context.",
                incident_class="integration",
            )
        if "adf" in text or "databricks" in text or "schema" in text:
            return SupervisorOutput(
                route_to="log_analysis_agent",
                confidence=0.82,
                rationale="Data-pipeline related terms indicate log-first analysis.",
                incident_class="data",
            )
        if "pipeline" in text or "build" in text or "release" in text:
            return SupervisorOutput(
                route_to="diagnostic_agent",
                confidence=0.80,
                rationale="CI/CD failure terms point to diagnostic analysis.",
                incident_class="pipeline",
            )
        return SupervisorOutput(
            route_to="human_escalation",
            confidence=0.55,
            rationale="Insufficient deterministic signal for safe autonomous routing.",
            incident_class="other",
        )

    def _render_system_prompt(self) -> str:
        template_path = Path(__file__).parent / "prompts" / "supervisor_system.j2"
        template = Environment(undefined=StrictUndefined, autoescape=False).from_string(
            template_path.read_text(encoding="utf-8")
        )
        return template.render(confidence_gate=self._confidence_gate)
