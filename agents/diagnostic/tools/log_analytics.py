from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LogEvidence:
    source: str
    excerpt: str


class LogAnalyticsAdapter:
    """Adapter placeholder for Azure Monitor / Log Analytics queries."""

    def fetch_evidence(self, *, incident_id: str, service_name: str) -> list[LogEvidence]:
        return [
            LogEvidence(
                source="log_analytics",
                excerpt=(
                    f"Incident {incident_id} on service {service_name}: "
                    "error burst detected around failure timestamp."
                ),
            )
        ]
