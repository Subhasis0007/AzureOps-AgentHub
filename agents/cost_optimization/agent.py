from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, StrictUndefined
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field

from agents.cost_optimization.tools.cost_analyzer import CostPatternAnalyzer
from core.state.schema import ACRGEState, AuditEntry, MessageTrace


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


class CostOptimizationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    estimated_total_monthly_savings_usd: float = Field(ge=0.0)


COST_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["recommendations", "estimated_total_monthly_savings_usd"],
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["category", "recommendation", "estimated_monthly_savings_usd"],
                "properties": {
                    "category": {"type": "string"},
                    "recommendation": {"type": "string"},
                    "estimated_monthly_savings_usd": {"type": "number", "minimum": 0.0},
                },
                "additionalProperties": False,
            },
        },
        "estimated_total_monthly_savings_usd": {"type": "number", "minimum": 0.0},
    },
    "additionalProperties": False,
}


class CostOptimizationAgent:
    def __init__(self, llm_client: StructuredLLM | None = None, *, analyzer: CostPatternAnalyzer | None = None) -> None:
        self._llm = llm_client
        self._analyzer = analyzer or CostPatternAnalyzer()

    def run(self, state: ACRGEState) -> ACRGEState:
        if self._llm is None:
            recs = [rec.__dict__ for rec in self._analyzer.recommend(
                tags=state.incident.tags,
                service_name=state.incident.service_name,
            )]
            payload = {
                "recommendations": recs,
                "estimated_total_monthly_savings_usd": round(
                    sum(item["estimated_monthly_savings_usd"] for item in recs),
                    2,
                ),
            }
        else:
            payload = self._llm.complete_json(
                system_prompt=self._render_system_prompt(),
                user_prompt=json.dumps(
                    {
                        "service_name": state.incident.service_name,
                        "environment": state.incident.environment,
                        "tags": state.incident.tags,
                        "incident": {
                            "title": state.incident.title,
                            "description": state.incident.description,
                        },
                    },
                    ensure_ascii=True,
                ),
                output_schema=COST_OUTPUT_SCHEMA,
                model="gpt-4o-mini",
            )

        Draft202012Validator(COST_OUTPUT_SCHEMA).validate(payload)
        output = CostOptimizationOutput.model_validate(payload)

        audit = AuditEntry(
            incident_id=state.incident.incident_id,
            actor="cost_optimization_agent",
            action="cost_recommendations_generated",
            outcome="success",
            details=output.model_dump(mode="json"),
        )

        return state.update_from_node(
            {
                "audit_trail": [*state.audit_trail, audit],
                "messages": [
                    *state.messages,
                    MessageTrace(
                        role="assistant",
                        content=(
                            "Cost optimization recommendations generated with estimated monthly "
                            f"savings USD {output.estimated_total_monthly_savings_usd:.2f}."
                        ),
                        metadata={"agent": "cost_optimization", "recommendations": output.recommendations},
                    ),
                ],
                "reasoning_trace": [
                    *state.reasoning_trace,
                    (
                        "cost_optimization.estimated_savings_usd="
                        f"{output.estimated_total_monthly_savings_usd:.2f}"
                    ),
                ],
            }
        )

    def _render_system_prompt(self) -> str:
        template_path = Path(__file__).parent / "prompts" / "cost_optimization_system.j2"
        template = Environment(undefined=StrictUndefined, autoescape=False).from_string(
            template_path.read_text(encoding="utf-8")
        )
        return template.render()
