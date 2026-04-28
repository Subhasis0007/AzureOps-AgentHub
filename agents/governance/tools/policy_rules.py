from __future__ import annotations

from dataclasses import dataclass

from core.config.policy_loader import GovernancePolicy


@dataclass(frozen=True)
class RuleEvaluation:
    requires_human: bool
    reasons: list[str]


class GovernanceRuleEngine:
    def evaluate(
        self,
        *,
        policy: GovernancePolicy,
        environment: str,
        target_branch: str,
        risk_level: str,
        confidence: float,
        touches_data_mutation: bool,
    ) -> RuleEvaluation:
        reasons: list[str] = []
        requires_human = False

        if environment == "prod" and policy.require_human_for_production:
            requires_human = True
            reasons.append("Production change requires human approval.")

        if target_branch in set(policy.protected_branches):
            requires_human = True
            reasons.append(f"Protected branch '{target_branch}' requires human approval.")

        rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        if rank.get(risk_level, 4) > rank.get(policy.auto_approve_max_risk, 1):
            requires_human = True
            reasons.append("Risk level exceeds auto-approve threshold.")

        if confidence < policy.confidence_threshold:
            requires_human = True
            reasons.append("Diagnostic confidence below policy threshold.")

        if touches_data_mutation and policy.require_human_for_data_mutation:
            requires_human = True
            reasons.append("Data mutation changes require human approval.")

        return RuleEvaluation(requires_human=requires_human, reasons=reasons)
