from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, ConfigDict

from agents.governance.tools.policy_rules import GovernanceRuleEngine
from core.config.policy_loader import GovernancePolicy, load_governance_policy
from core.state.schema import (
    ACRGEState,
    AuditEntry,
    GovernanceDecision,
    GovernanceOutcome,
    MessageTrace,
)
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


class GovernanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    environment: str
    target_branch: str
    risk_level: str
    diagnostic_confidence: float
    touches_data_mutation: bool


class GovernanceAgent:
    def __init__(
        self,
        llm_client: StructuredLLM | None = None,
        *,
        policy: GovernancePolicy | None = None,
        rule_engine: GovernanceRuleEngine | None = None,
    ) -> None:
        self._llm = llm_client
        self._policy = policy or load_governance_policy()
        self._rules = rule_engine or GovernanceRuleEngine()

    def run(self, state: ACRGEState) -> ACRGEState:
        pr_spec = state.pr_spec
        target_branch = pr_spec.target_branch if pr_spec else "main"
        risk_level = str(pr_spec.risk_level) if pr_spec else "high"
        confidence = state.diagnostic_report.confidence if state.diagnostic_report else 0.0
        touches_data_mutation = any(
            marker in state.log_summary.lower() for marker in ["schema", "migration", "delete", "truncate"]
        )

        agent_input = GovernanceInput(
            incident_id=state.incident.incident_id,
            environment=state.incident.environment,
            target_branch=target_branch,
            risk_level=risk_level,
            diagnostic_confidence=confidence,
            touches_data_mutation=touches_data_mutation,
        )

        deterministic = self._rules.evaluate(
            policy=self._policy,
            environment=agent_input.environment,
            target_branch=agent_input.target_branch,
            risk_level=agent_input.risk_level,
            confidence=agent_input.diagnostic_confidence,
            touches_data_mutation=agent_input.touches_data_mutation,
        )

        decision = self._produce_decision(agent_input, deterministic.reasons)

        if deterministic.requires_human:
            decision.decision = GovernanceOutcome.NEEDS_HUMAN_REVIEW
            decision.requires_human_approval = True
            decision.reasons = list(dict.fromkeys([*deterministic.reasons, *decision.reasons]))

        audit = AuditEntry(
            incident_id=state.incident.incident_id,
            actor="governance_agent",
            action="governance_evaluation",
            outcome="success",
            details=decision.model_dump(mode="json"),
        )

        return state.update_from_node(
            {
                "governance_decision": decision,
                "audit_trail": [*state.audit_trail, audit],
                "messages": [
                    *state.messages,
                    MessageTrace(
                        role="assistant",
                        content=(
                            f"Governance decision: {decision.decision}; "
                            f"requires_human_approval={decision.requires_human_approval}."
                        ),
                        metadata={"agent": "governance", "policy_version": decision.policy_version},
                    ),
                ],
            }
        )

    def _produce_decision(self, agent_input: GovernanceInput, deterministic_reasons: list[str]) -> GovernanceDecision:
        if self._llm is None:
            payload = {
                "incident_id": agent_input.incident_id,
                "decision": "approved" if not deterministic_reasons else "needs_human_review",
                "requires_human_approval": bool(deterministic_reasons),
                "reasons": deterministic_reasons or ["Meets low-risk auto-approval policy."],
                "policy_version": self._policy.policy_version,
                "approver": None,
                "expires_at": None,
            }
        else:
            payload = self._llm.complete_json(
                system_prompt=self._render_system_prompt(),
                user_prompt=json.dumps(
                    {
                        "input": agent_input.model_dump(mode="json"),
                        "policy": self._policy.model_dump(mode="json"),
                        "deterministic_reasons": deterministic_reasons,
                    },
                    ensure_ascii=True,
                ),
                output_schema={"$ref": "governance_decision"},
                model="gpt-4o-mini",
            )

        validate_payload("governance_decision", payload)
        payload.setdefault("incident_id", agent_input.incident_id)
        payload.setdefault("policy_version", self._policy.policy_version)
        return GovernanceDecision.model_validate(payload)

    def _render_system_prompt(self) -> str:
        template_path = Path(__file__).parent / "prompts" / "governance_system.j2"
        template = Environment(undefined=StrictUndefined, autoescape=False).from_string(
            template_path.read_text(encoding="utf-8")
        )
        return template.render()
