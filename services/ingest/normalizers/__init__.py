from __future__ import annotations

from typing import Any, Protocol

from core.state.schema import IncidentEvent
from services.ingest.normalizers.adf import ADFNormalizer
from services.ingest.normalizers.databricks import DatabricksNormalizer
from services.ingest.normalizers.devops import AzureDevOpsNormalizer
from services.ingest.normalizers.logic_app import LogicAppNormalizer
from services.ingest.normalizers.service_bus import ServiceBusNormalizer


class IncidentNormalizer(Protocol):
    def normalize(self, payload: dict[str, Any], *, environment: str = "dev") -> IncidentEvent:
        ...


NORMALIZER_REGISTRY: dict[str, IncidentNormalizer] = {
    "devops": AzureDevOpsNormalizer(),
    "azure_devops": AzureDevOpsNormalizer(),
    "service_bus": ServiceBusNormalizer(),
    "logic_app": LogicAppNormalizer(),
    "adf": ADFNormalizer(),
    "databricks": DatabricksNormalizer(),
}


def normalize_event(event_type: str, payload: dict[str, Any], *, environment: str = "dev") -> IncidentEvent:
    key = event_type.strip().lower()
    if key not in NORMALIZER_REGISTRY:
        raise ValueError(f"Unsupported event_type='{event_type}'.")
    return NORMALIZER_REGISTRY[key].normalize(payload, environment=environment)


__all__ = [
    "ADFNormalizer",
    "AzureDevOpsNormalizer",
    "DatabricksNormalizer",
    "IncidentNormalizer",
    "LogicAppNormalizer",
    "ServiceBusNormalizer",
    "normalize_event",
]
