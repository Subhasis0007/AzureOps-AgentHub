from __future__ import annotations

import json

from services.executor.function_app import ServiceBusConsumer
from services.ingest.function_app import ServiceBusEnvelope, ServiceBusPublisher


class FakeSender:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def send_messages(self, message) -> None:
        self.messages.append(message)


class FakeClient:
    last_sender: FakeSender | None = None

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self._sender = FakeSender()
        FakeClient.last_sender = self._sender

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_topic_sender(self, topic_name: str) -> FakeSender:
        return self._sender

    @classmethod
    def from_connection_string(cls, conn_str: str):
        return cls(conn_str=conn_str)


class FakeMessage:
    def __init__(self, body: str, content_type: str, application_properties: dict):
        self.body = body
        self.content_type = content_type
        self.application_properties = application_properties


def test_service_bus_consumer_deserializes_envelope(base_incident) -> None:
    payload = json.dumps(
        {
            "correlation_id": "corr-1",
            "incident": base_incident.model_dump(mode="json"),
        }
    )
    envelope = ServiceBusConsumer().deserialize(payload)
    assert envelope.correlation_id == "corr-1"
    assert envelope.incident.incident_id == base_incident.incident_id


def test_service_bus_publisher_uses_fake_azure_client(monkeypatch, base_incident) -> None:
    import services.ingest.function_app as ingest_app

    monkeypatch.setattr(ingest_app, "ServiceBusClient", FakeClient)
    monkeypatch.setattr(ingest_app, "ServiceBusMessage", FakeMessage)
    monkeypatch.setattr(ingest_app.settings.service_bus, "connection_string", None)
    monkeypatch.setattr(ingest_app.settings.service_bus, "namespace", "fake.servicebus.windows.net")
    monkeypatch.setattr(ingest_app.settings.service_bus, "inbound_topic", "acrge.events.inbound")

    ingest_app.ServiceBusPublisher().publish(
        ServiceBusEnvelope(incident=base_incident, correlation_id="corr-xyz")
    )

    assert FakeClient.last_sender is not None
    assert len(FakeClient.last_sender.messages) == 1
