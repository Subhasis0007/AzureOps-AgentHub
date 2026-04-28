from __future__ import annotations

from typing import Any

from core.state.schema import IncidentEvent, IncidentSource
from services.ingest.normalizers.common import build_incident


class DatabricksNormalizer:
    source = IncidentSource.DATABRICKS

    def normalize(self, payload: dict[str, Any], *, environment: str = "dev") -> IncidentEvent:
        job_name = str(payload.get("job_name") or payload.get("jobName") or payload.get("task_key") or "databricks-job")
        run_id = str(payload.get("run_id") or payload.get("runId") or "unknown-run")
        error = str(payload.get("error") or payload.get("state_message") or "unknown-error")

        title = f"Databricks pipeline failure: {job_name}"
        description = f"Databricks run '{run_id}' failed. Error summary: {error}."

        requires_human = "schema" in error.lower() or "permission" in error.lower()
        return build_incident(
            source=self.source,
            payload=payload,
            title=title,
            description=description,
            service_name=job_name,
            environment=environment,
            severity_hint=str(payload.get("severity") or "high"),
            requires_human=requires_human,
        )
