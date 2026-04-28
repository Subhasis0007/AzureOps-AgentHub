from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, ConfigDict

from agents.diagnostic.tools.infra_graph import InfraGraphAdapter
from agents.diagnostic.tools.log_analytics import LogAnalyticsAdapter
from agents.diagnostic.tools.rag_retrieval import IncidentRAGAdapter
from core.state.schema import ACRGEState, DiagnosticReport, IncidentStatus, MessageTrace
from core.utils.json_schemas import validate_payload


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


class DiagnosticInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    title: str
    description: str
    service_name: str
    environment: str
    prior_log_summary: str = ""


class DiagnosticAgent:
    def __init__(
        self,
        llm_client: StructuredLLM | None = None,
        *,
        log_analytics: LogAnalyticsAdapter | None = None,
        infra_graph: InfraGraphAdapter | None = None,
        rag: IncidentRAGAdapter | None = None,
    ) -> None:
        self._llm = llm_client
        self._log_analytics = log_analytics or LogAnalyticsAdapter()
        self._infra_graph = infra_graph or InfraGraphAdapter()
        self._rag = rag or IncidentRAGAdapter()

    def run(self, state: ACRGEState) -> ACRGEState:
        incident = state.incident
        agent_input = DiagnosticInput(
            incident_id=incident.incident_id,
            title=incident.title,
            description=incident.description,
            service_name=incident.service_name,
            environment=incident.environment,
            prior_log_summary=state.log_summary,
        )

        log_evidence = self._log_analytics.fetch_evidence(
            incident_id=incident.incident_id,
            service_name=incident.service_name,
        )
        infra_signals = self._infra_graph.correlate(service_name=incident.service_name)
        prior_cases = self._rag.retrieve(query=f"{incident.title} {incident.description}", top_k=5)

        report = self._produce_report(agent_input, log_evidence, infra_signals, prior_cases)

        merged_state = state.update_from_node(
            {
                "diagnostic_report": report,
                "messages": [
                    *state.messages,
                    MessageTrace(
                        role="assistant",
                        content=f"Diagnostic report generated with confidence {report.confidence:.2f}.",
                        metadata={"agent": "diagnostic"},
                    ),
                ],
                "reasoning_trace": [
                    *state.reasoning_trace,
                    f"diagnostic.taxonomy={report.taxonomy} confidence={report.confidence:.2f}",
                ],
            }
        )
        merged_state.incident.status = IncidentStatus.DIAGNOSING
        return merged_state

    def _produce_report(
        self,
        agent_input: DiagnosticInput,
        log_evidence: list[Any],
        infra_signals: list[Any],
        prior_cases: list[Any],
    ) -> DiagnosticReport:
        if self._llm is None:
            payload = {
                "incident_id": agent_input.incident_id,
                "summary": "Likely integration configuration regression during deployment.",
                "confidence": 0.74,
                "taxonomy": "config",
                "root_cause_hypotheses": [
                    "Pipeline variable mismatch caused target service configuration drift."
                ],
                "correlated_signals": [s.detail for s in infra_signals],
                "evidence_uris": [],
                "recommended_actions": [
                    "Validate release variables against previous successful run.",
                    "Re-run pipeline with locked configuration snapshot.",
                ],
            }
        else:
            llm_input = {
                "incident": agent_input.model_dump(mode="json"),
                "log_evidence": [e.__dict__ for e in log_evidence],
                "infra_signals": [s.__dict__ for s in infra_signals],
                "prior_cases": [c.__dict__ for c in prior_cases],
            }
            payload = self._llm.complete_json(
                system_prompt=self._render_system_prompt(),
                user_prompt=json.dumps(llm_input, ensure_ascii=True),
                output_schema={"$ref": "diagnostic_report"},
                model="gpt-4o",
            )

        validate_payload("diagnostic_report", payload)
        return DiagnosticReport.model_validate(payload)

    def _render_system_prompt(self) -> str:
        template_path = Path(__file__).parent / "prompts" / "diagnostic_system.j2"
        template = Environment(undefined=StrictUndefined, autoescape=False).from_string(
            template_path.read_text(encoding="utf-8")
        )
        return template.render()
