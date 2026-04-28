from __future__ import annotations

from typing import Any

from core.state.schema import IncidentEvent, IncidentSource
from services.ingest.normalizers.common import build_incident


class ServiceBusNormalizer:
    source = IncidentSource.SERVICE_BUS

    def normalize(self, payload: dict[str, Any], *, environment: str = "dev") -> IncidentEvent:
        entity = str(payload.get("entityPath") or payload.get("queue") or payload.get("topic") or "servicebus-entity")
        deadletter_reason = str(payload.get("deadLetterReason") or payload.get("reason") or "unknown")
        delivery_count = payload.get("deliveryCount")

        title = f"Service Bus dead-letter incident: {entity}"
        description = (
            f"Dead-letter message detected. reason='{deadletter_reason}', "
            f"deliveryCount='{delivery_count}'."
        )

        return build_incident(
            source=self.source,
            payload=payload,
            title=title,
            description=description,
            service_name=entity,
            environment=environment,
            severity_hint=str(payload.get("severity") or "medium"),
            requires_human=False,
        )
