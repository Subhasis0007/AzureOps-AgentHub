from __future__ import annotations

from typing import Any

from core.state.schema import IncidentSource


class _FakePublisher:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def publish(self, envelope: Any) -> None:
        self.sent.append((envelope.correlation_id, envelope.incident.source))


def test_ingest_payload_logic_app_flow(monkeypatch: Any) -> None:
    import services.ingest.function_app as ingest_app

    fake = _FakePublisher()
    monkeypatch.setattr(ingest_app, "publisher", fake)

    payload = {
        "workflowName": "erp-sync",
        "actionName": "post-order",
        "status": "Failed",
    }
    incident = ingest_app._ingest_payload("logic_app", payload, "corr-test-1")

    assert incident.source == IncidentSource.LOGIC_APP
    assert fake.sent[0][0] == "corr-test-1"


def test_ingest_payload_service_bus_flow(monkeypatch: Any) -> None:
    import services.ingest.function_app as ingest_app

    fake = _FakePublisher()
    monkeypatch.setattr(ingest_app, "publisher", fake)

    payload = {
        "entityPath": "orders-deadletter",
        "deadLetterReason": "MaxDeliveryCountExceeded",
        "messageId": "msg-77",
    }
    incident = ingest_app._ingest_payload("service_bus", payload, "corr-test-2")

    assert incident.source == IncidentSource.SERVICE_BUS
    assert fake.sent[0][0] == "corr-test-2"
