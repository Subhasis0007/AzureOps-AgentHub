from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage

from core.config.settings import get_settings
from core.state.schema import IncidentEvent
from core.utils.ids import deterministic_fingerprint, generate_id
from core.utils.logging import clear_log_context, configure_logging, get_logger, set_log_context
from services.ingest.normalizers import normalize_event
from services.ingest.normalizers.common import extract_correlation_id


settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("services.ingest")
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@dataclass(frozen=True)
class ServiceBusEnvelope:
    incident: IncidentEvent
    correlation_id: str


class ServiceBusPublisher:
    def __init__(self) -> None:
        self._topic = settings.service_bus.inbound_topic

    def publish(self, envelope: ServiceBusEnvelope) -> None:
        payload = {
            "correlation_id": envelope.correlation_id,
            "incident": envelope.incident.model_dump(mode="json"),
        }
        body = json.dumps(payload, ensure_ascii=True)

        if settings.service_bus.connection_string:
            client = ServiceBusClient.from_connection_string(
                conn_str=settings.service_bus.connection_string.get_secret_value()
            )
        elif settings.service_bus.namespace:
            client = ServiceBusClient(
                fully_qualified_namespace=settings.service_bus.namespace,
                credential=settings.build_credential(),
            )
        else:
            raise RuntimeError("Service Bus configuration is missing.")

        with client:
            sender = client.get_topic_sender(topic_name=self._topic)
            with sender:
                sender.send_messages(
                    ServiceBusMessage(
                        body,
                        content_type="application/json",
                        application_properties={
                            "correlation_id": envelope.correlation_id,
                            "incident_id": envelope.incident.incident_id,
                            "source": envelope.incident.source,
                        },
                    )
                )


publisher = ServiceBusPublisher()


def _json_body(req: func.HttpRequest) -> dict[str, Any]:
    body = req.get_body().decode("utf-8") if req.get_body() else "{}"
    parsed = json.loads(body)
    return parsed if isinstance(parsed, dict) else {"payload": parsed}


def _ingest_payload(event_type: str, payload: dict[str, Any], correlation_id: str) -> IncidentEvent:
    incident = normalize_event(event_type, payload, environment=settings.app_env)
    set_log_context(request_id=correlation_id, incident_id=incident.incident_id)
    logger.info(
        "normalized incident event",
        extra={
            "event_type": event_type,
            "source_event_id": incident.source_event_id,
            "service_name": incident.service_name,
            "environment": incident.environment,
        },
    )
    publisher.publish(ServiceBusEnvelope(incident=incident, correlation_id=correlation_id))
    logger.info("published normalized incident to service bus topic")
    return incident


@app.route(route="ingest/{event_type}", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_webhook(req: func.HttpRequest) -> func.HttpResponse:
    event_type = str(req.route_params.get("event_type", "")).strip().lower()
    correlation_id = req.headers.get("x-correlation-id") or req.headers.get("x-request-id")

    try:
        payload = _json_body(req)
        if not correlation_id:
            fallback = deterministic_fingerprint(json.dumps(payload, sort_keys=True, default=str))
            correlation_id = generate_id("corr", entropy=12) + "_" + fallback[:8]
        correlation_id = extract_correlation_id(payload, correlation_id)

        set_log_context(request_id=correlation_id)
        incident = _ingest_payload(event_type, payload, correlation_id)

        return func.HttpResponse(
            json.dumps(
                {
                    "status": "accepted",
                    "correlation_id": correlation_id,
                    "incident_id": incident.incident_id,
                    "source": incident.source,
                },
                ensure_ascii=True,
            ),
            status_code=202,
            mimetype="application/json",
            headers={"x-correlation-id": correlation_id},
        )
    except Exception as exc:
        logger.exception("ingest webhook failed", extra={"event_type": event_type, "error": str(exc)})
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=True),
            status_code=400,
            mimetype="application/json",
            headers={"x-correlation-id": correlation_id or ""},
        )
    finally:
        clear_log_context()


def _mock_dlq_snapshot() -> list[dict[str, Any]]:
    # TODO: replace with real DLQ monitor reader in Phase 6.
    return [
        {
            "entityPath": "acrge.integration.deadletter",
            "deadLetterReason": "MaxDeliveryCountExceeded",
            "deliveryCount": 12,
            "messageId": generate_id("dlqmsg", entropy=8),
        }
    ]


def _mock_logic_app_failures() -> list[dict[str, Any]]:
    # TODO: replace with real Logic App run status poller in Phase 6.
    return [
        {
            "workflowName": "acrge-integration-workflow",
            "actionName": "DispatchToERP",
            "status": "Failed",
            "trackingId": generate_id("logic", entropy=8),
        }
    ]


@app.timer_trigger(
    schedule="0 */5 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def monitor_service_bus_deadletter(timer: func.TimerRequest) -> None:
    correlation_id = generate_id("corr", entropy=12)
    set_log_context(request_id=correlation_id)
    try:
        logger.info("running service bus deadletter monitor", extra={"past_due": timer.past_due})
        for payload in _mock_dlq_snapshot():
            payload["correlationId"] = correlation_id
            _ingest_payload("service_bus", payload, correlation_id)
    except Exception:
        logger.exception("service bus deadletter monitor failed")
        raise
    finally:
        clear_log_context()


@app.timer_trigger(
    schedule="30 */5 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def monitor_logic_app_failures(timer: func.TimerRequest) -> None:
    correlation_id = generate_id("corr", entropy=12)
    set_log_context(request_id=correlation_id)
    try:
        logger.info("running logic app failure monitor", extra={"past_due": timer.past_due})
        for payload in _mock_logic_app_failures():
            payload["correlationId"] = correlation_id
            _ingest_payload("logic_app", payload, correlation_id)
    except Exception:
        logger.exception("logic app monitor failed")
        raise
    finally:
        clear_log_context()
