from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostRecommendation:
    category: str
    recommendation: str
    estimated_monthly_savings_usd: float


class CostPatternAnalyzer:
    """Rule-based baseline analyzer. Replace with Cost Management APIs in later phases."""

    def recommend(self, *, tags: dict[str, str], service_name: str) -> list[CostRecommendation]:
        recs: list[CostRecommendation] = []

        if tags.get("environment", "").lower() in {"dev", "test"}:
            recs.append(
                CostRecommendation(
                    category="compute",
                    recommendation="Apply schedule-based shutdown outside business hours.",
                    estimated_monthly_savings_usd=120.0,
                )
            )

        recs.append(
            CostRecommendation(
                category="observability",
                recommendation=(
                    "Tune log retention and sampling for high-volume telemetry in "
                    f"{service_name}."
                ),
                estimated_monthly_savings_usd=45.0,
            )
        )
        return recs
