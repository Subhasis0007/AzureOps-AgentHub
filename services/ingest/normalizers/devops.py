from __future__ import annotations

from typing import Any

from core.state.schema import IncidentEvent, IncidentSource
from services.ingest.normalizers.common import build_incident


class AzureDevOpsNormalizer:
    source = IncidentSource.AZURE_DEVOPS

    def normalize(self, payload: dict[str, Any], *, environment: str = "dev") -> IncidentEvent:
        resource = payload.get("resource", {}) if isinstance(payload.get("resource"), dict) else {}
        definition = resource.get("definition", {}) if isinstance(resource.get("definition"), dict) else {}

        pipeline_name = str(definition.get("name") or payload.get("eventType") or "azure-devops-pipeline")
        status = str(resource.get("status") or resource.get("result") or "failed")
        project = ""
        if isinstance(resource.get("project"), dict):
            project = str(resource["project"].get("name") or "")

        title = f"Azure DevOps pipeline failure: {pipeline_name}"
        description = (
            f"Pipeline execution reported status '{status}'. "
            f"Project='{project or 'unknown'}'."
        )

        evidence = []
        if isinstance(resource.get("_links"), dict):
            web = resource["_links"].get("web", {})
            if isinstance(web, dict) and isinstance(web.get("href"), str):
                evidence.append(web["href"])

        return build_incident(
            source=self.source,
            payload=payload,
            title=title,
            description=description,
            service_name=pipeline_name,
            environment=environment,
            severity_hint=str(payload.get("severity") or "high"),
            evidence_uris=evidence,
        )
