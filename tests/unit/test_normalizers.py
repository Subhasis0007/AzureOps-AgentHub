from __future__ import annotations

from core.state.schema import IncidentSource
from services.ingest.normalizers import normalize_event


def test_devops_normalizer_maps_to_incident_event() -> None:
    payload = {
        "eventType": "ms.vss-pipelines.job-state-changed-event",
        "resource": {
            "status": "failed",
            "definition": {"name": "release-api"},
        },
    }
    incident = normalize_event("devops", payload, environment="dev")
    assert incident.source == IncidentSource.AZURE_DEVOPS
    assert "pipeline" in incident.title.lower()


def test_service_bus_normalizer_maps_dlq_payload() -> None:
    payload = {
        "entityPath": "orders-deadletter",
        "deadLetterReason": "MaxDeliveryCountExceeded",
        "messageId": "m-1",
    }
    incident = normalize_event("service_bus", payload, environment="stage")
    assert incident.source == IncidentSource.SERVICE_BUS
    assert incident.environment == "stage"


def test_logic_app_normalizer_maps_payload() -> None:
    payload = {"workflowName": "sync-orders", "actionName": "PostERP", "status": "Failed"}
    incident = normalize_event("logic_app", payload, environment="prod")
    assert incident.source == IncidentSource.LOGIC_APP
    assert incident.environment == "prod"


def test_adf_normalizer_flags_human_for_schema_keywords() -> None:
    payload = {
        "pipelineName": "copy-orders",
        "runId": "run-22",
        "failureType": "schema mismatch",
    }
    incident = normalize_event("adf", payload, environment="test")
    assert incident.source == IncidentSource.ADF
    assert incident.requires_human is True


def test_databricks_normalizer_maps_payload() -> None:
    payload = {"job_name": "bronze-to-silver", "run_id": "db-44", "error": "permission denied"}
    incident = normalize_event("databricks", payload, environment="dev")
    assert incident.source == IncidentSource.DATABRICKS
    assert incident.requires_human is True
