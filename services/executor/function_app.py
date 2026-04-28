from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import azure.functions as func

from agents.supervisor.agent import SupervisorAgent
from core.config.settings import get_settings
from core.state.schema import ACRGEState, IncidentEvent, MessageTrace
from core.utils.ids import generate_id
from core.utils.logging import clear_log_context, configure_logging, get_logger, set_log_context


settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("services.executor")
app = func.FunctionApp()


@dataclass(frozen=True)
class InboundEnvelope:
    correlation_id: str
    incident: IncidentEvent


class ServiceBusConsumer:
    def deserialize(self, payload: str) -> InboundEnvelope:
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("Service Bus payload must be a JSON object")

        incident_payload = parsed.get("incident")
        if not isinstance(incident_payload, dict):
            raise ValueError("Missing incident object in message")

        correlation_id = str(parsed.get("correlation_id") or generate_id("corr", entropy=10))
        incident = IncidentEvent.model_validate(incident_payload)
        return InboundEnvelope(correlation_id=correlation_id, incident=incident)


consumer = ServiceBusConsumer()
supervisor = SupervisorAgent()


@app.service_bus_topic_trigger(
    arg_name="message",
    topic_name="acrge.events.inbound",
    subscription_name="executor",
    connection="SERVICEBUS_CONNECTION_STRING",
)
def execute_incident(message: func.ServiceBusMessage) -> None:
    correlation_id = generate_id("corr", entropy=10)
    try:
        body = message.get_body().decode("utf-8")
        envelope = consumer.deserialize(body)
        correlation_id = envelope.correlation_id

        set_log_context(request_id=correlation_id, incident_id=envelope.incident.incident_id)
        logger.info(
            "executor received incident",
            extra={
                "source": envelope.incident.source,
                "source_event_id": envelope.incident.source_event_id,
                "service_name": envelope.incident.service_name,
            },
        )

        state = ACRGEState(
            incident=envelope.incident,
            messages=[
                MessageTrace(
                    role="system",
                    content="Executor initialized state from Service Bus event.",
                    metadata={"correlation_id": correlation_id},
                )
            ],
        )

        routed = supervisor.run(state)
        logger.info(
            "supervisor completed routing",
            extra={
                "reasoning_steps": len(routed.reasoning_trace),
                "has_governance_decision": routed.governance_decision is not None,
            },
        )
    except Exception:
        logger.exception("executor failed to process inbound incident message")
        raise
    finally:
        clear_log_context()
