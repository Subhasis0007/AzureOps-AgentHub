from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import azure.functions as func
import httpx

from core.config.settings import get_settings
from core.utils.ids import generate_id
from core.utils.logging import clear_log_context, configure_logging, get_logger, set_log_context

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("services.notifier")
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@dataclass(frozen=True)
class NotificationEnvelope:
    correlation_id: str
    incident_id: str
    summary: str
    decision: str
    requires_human_approval: bool


class TeamsNotifier:
    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def send(self, envelope: NotificationEnvelope) -> None:
        if not self._webhook_url:
            logger.warning("teams webhook url not configured; skipping notification")
            return

        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "weight": "Bolder",
                                "size": "Medium",
                                "text": f"ACRGE Incident Update: {envelope.incident_id}",
                            },
                            {"type": "TextBlock", "text": envelope.summary, "wrap": True},
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "Decision", "value": envelope.decision},
                                    {
                                        "title": "Human approval",
                                        "value": str(envelope.requires_human_approval),
                                    },
                                    {"title": "Correlation ID", "value": envelope.correlation_id},
                                ],
                            },
                        ],
                    },
                }
            ],
        }

        with httpx.Client(timeout=5.0) as client:
            response = client.post(self._webhook_url, json=card)
            response.raise_for_status()


notifier = TeamsNotifier(settings.teams_webhook_url)


@app.route(route="notify", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def notify(req: func.HttpRequest) -> func.HttpResponse:
    correlation_id = req.headers.get("x-correlation-id") or generate_id("corr", entropy=10)
    set_log_context(request_id=correlation_id)
    try:
        payload: dict[str, Any] = json.loads(req.get_body().decode("utf-8") or "{}")
        envelope = NotificationEnvelope(
            correlation_id=correlation_id,
            incident_id=str(payload.get("incident_id") or payload.get("incidentId") or "unknown-incident"),
            summary=str(payload.get("summary") or "No summary provided."),
            decision=str(payload.get("decision") or "needs_human_review"),
            requires_human_approval=bool(payload.get("requires_human_approval", True)),
        )

        set_log_context(request_id=correlation_id, incident_id=envelope.incident_id)
        notifier.send(envelope)
        logger.info("notification processed", extra={"decision": envelope.decision})

        return func.HttpResponse(
            json.dumps({"status": "sent", "correlation_id": correlation_id}, ensure_ascii=True),
            status_code=202,
            mimetype="application/json",
            headers={"x-correlation-id": correlation_id},
        )
    except Exception as exc:
        logger.exception("notify endpoint failed", extra={"error": str(exc)})
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=True),
            status_code=400,
            mimetype="application/json",
            headers={"x-correlation-id": correlation_id},
        )
    finally:
        clear_log_context()


@app.timer_trigger(
    schedule="0 */15 * * * *",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def notifier_health_monitor(timer: func.TimerRequest) -> None:
    correlation_id = generate_id("corr", entropy=10)
    set_log_context(request_id=correlation_id)
    try:
        logger.info("notifier monitor heartbeat", extra={"past_due": timer.past_due})
    finally:
        clear_log_context()
