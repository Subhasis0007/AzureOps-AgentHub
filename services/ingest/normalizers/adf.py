from __future__ import annotations

from typing import Any

from core.state.schema import IncidentEvent, IncidentSource
from services.ingest.normalizers.common import build_incident


class ADFNormalizer:
    source = IncidentSource.ADF

    def normalize(self, payload: dict[str, Any], *, environment: str = "dev") -> IncidentEvent:
        pipeline_name = str(payload.get("pipelineName") or payload.get("pipeline") or "adf-pipeline")
        run_id = str(payload.get("runId") or payload.get("pipelineRunId") or "unknown-run")
        failure = str(payload.get("failureType") or payload.get("errorCode") or "unknown")

        title = f"ADF pipeline failure: {pipeline_name}"
        description = (
            f"ADF pipeline run '{run_id}' failed with failureType/error='{failure}'."
        )

        requires_human = "schema" in json_string(payload).lower() or "mapping" in json_string(payload).lower()
        return build_incident(
            source=self.source,
            payload=payload,
            title=title,
            description=description,
            service_name=pipeline_name,
            environment=environment,
            severity_hint=str(payload.get("severity") or "high"),
            requires_human=requires_human,
        )


def json_string(payload: dict[str, Any]) -> str:
    return str(payload)
