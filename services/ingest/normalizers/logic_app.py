from __future__ import annotations

from typing import Any

from core.state.schema import IncidentEvent, IncidentSource
from services.ingest.normalizers.common import build_incident


class LogicAppNormalizer:
    source = IncidentSource.LOGIC_APP

    def normalize(self, payload: dict[str, Any], *, environment: str = "dev") -> IncidentEvent:
        workflow_name = str(payload.get("workflowName") or payload.get("resourceName") or "logic-app")
        action_name = str(payload.get("actionName") or payload.get("operationName") or "unknown-action")
        status = str(payload.get("status") or payload.get("state") or "failed")

        title = f"Logic App integration failure: {workflow_name}"
        description = (
            f"Logic App action '{action_name}' entered status '{status}'. "
            "Potential integration/runtime failure."
        )

        return build_incident(
            source=self.source,
            payload=payload,
            title=title,
            description=description,
            service_name=workflow_name,
            environment=environment,
            severity_hint=str(payload.get("severity") or "high"),
        )
