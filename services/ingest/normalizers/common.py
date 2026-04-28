from __future__ import annotations

import json
from typing import Any, Literal, cast

from core.state.schema import IncidentEvent, IncidentSeverity, IncidentSource
from core.utils.ids import deterministic_fingerprint


def extract_correlation_id(payload: dict[str, Any], fallback: str) -> str:
    candidates = [
        payload.get("correlationId"),
        payload.get("correlation_id"),
        payload.get("trackingId"),
        payload.get("traceId"),
        payload.get("trace_id"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return fallback


def normalize_severity(value: str | None) -> IncidentSeverity:
    raw = (value or "").strip().lower()
    mapping = {
        "sev0": IncidentSeverity.CRITICAL,
        "sev1": IncidentSeverity.HIGH,
        "sev2": IncidentSeverity.MEDIUM,
        "sev3": IncidentSeverity.LOW,
        "critical": IncidentSeverity.CRITICAL,
        "high": IncidentSeverity.HIGH,
        "medium": IncidentSeverity.MEDIUM,
        "low": IncidentSeverity.LOW,
        "error": IncidentSeverity.HIGH,
        "warning": IncidentSeverity.MEDIUM,
        "info": IncidentSeverity.LOW,
    }
    return mapping.get(raw, IncidentSeverity.MEDIUM)


def source_event_id(payload: dict[str, Any]) -> str:
    keys = ["id", "eventId", "messageId", "runId", "pipelineRunId", "activityRunId", "alertId"]
    for key in keys:
        candidate = payload.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if isinstance(candidate, int):
            return str(candidate)
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return deterministic_fingerprint(serialized)


def build_incident(
    *,
    source: IncidentSource,
    payload: dict[str, Any],
    title: str,
    description: str,
    service_name: str,
    environment: str,
    severity_hint: str | None = None,
    evidence_uris: list[str] | None = None,
    requires_human: bool = False,
) -> IncidentEvent:
    safe_env = cast(
        Literal["dev", "test", "stage", "prod"],
        environment if environment in {"dev", "test", "stage", "prod"} else "dev",
    )
    return IncidentEvent(
        source=source,
        source_event_id=source_event_id(payload),
        title=title[:500],
        description=description[:20000],
        service_name=service_name[:200] if service_name else "unknown-service",
        environment=safe_env,
        severity=normalize_severity(severity_hint),
        tags={
            "source": source.value,
            "environment": safe_env,
        },
        evidence_uris=evidence_uris or [],
        raw_payload=payload,
        requires_human=requires_human,
    )
