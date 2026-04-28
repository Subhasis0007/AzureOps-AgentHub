from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievedIncident:
    incident_id: str
    score: float
    summary: str


class IncidentRAGAdapter:
    """Adapter for Azure AI Search hybrid retrieval over prior incidents."""

    def retrieve(self, *, query: str, top_k: int = 5) -> list[RetrievedIncident]:
        if not query.strip():
            return []
        return [
            RetrievedIncident(
                incident_id="inc_reference_001",
                score=0.79,
                summary="Prior deployment failure resolved by pipeline variable correction.",
            )
        ][:top_k]
