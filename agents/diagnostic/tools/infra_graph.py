from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InfraSignal:
    node: str
    relation: str
    detail: str


class InfraGraphAdapter:
    """Adapter for infrastructure topology/knowledge graph correlation."""

    def correlate(self, *, service_name: str) -> list[InfraSignal]:
        return [
            InfraSignal(
                node=service_name,
                relation="depends_on",
                detail="shared integration network gateway",
            )
        ]
