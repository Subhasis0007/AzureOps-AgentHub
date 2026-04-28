from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator


DIAGNOSTIC_REPORT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "incident_id",
        "summary",
        "confidence",
        "root_cause_hypotheses",
        "taxonomy",
    ],
    "properties": {
        "incident_id": {"type": "string", "minLength": 3},
        "summary": {"type": "string", "minLength": 5},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "root_cause_hypotheses": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 3},
        },
        "taxonomy": {
            "type": "string",
            "enum": ["infra", "code", "config", "data", "auth", "network", "unknown"],
        },
        "recommended_actions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "additionalProperties": True,
}


PULL_REQUEST_SPEC_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["incident_id", "title", "body", "target_branch", "source_branch"],
    "properties": {
        "incident_id": {"type": "string", "minLength": 3},
        "title": {"type": "string", "minLength": 8, "maxLength": 240},
        "body": {"type": "string", "minLength": 20},
        "source_branch": {"type": "string", "pattern": "^acrge/fix/.+"},
        "target_branch": {"type": "string", "minLength": 1},
        "files_changed": {
            "type": "array",
            "items": {"type": "string"},
        },
        "rollback_notes": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
    },
    "additionalProperties": True,
}


GOVERNANCE_DECISION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["decision", "requires_human_approval", "reasons", "policy_version"],
    "properties": {
        "decision": {"type": "string", "enum": ["approved", "rejected", "needs_human_review"]},
        "requires_human_approval": {"type": "boolean"},
        "reasons": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 3},
        },
        "policy_version": {"type": "string", "minLength": 1},
        "approver": {"type": ["string", "null"]},
        "expires_at": {"type": ["string", "null"], "format": "date-time"},
    },
    "additionalProperties": True,
}


SCHEMAS: dict[str, dict[str, Any]] = {
    "diagnostic_report": DIAGNOSTIC_REPORT_SCHEMA,
    "pull_request_spec": PULL_REQUEST_SPEC_SCHEMA,
    "governance_decision": GOVERNANCE_DECISION_SCHEMA,
}


def validate_payload(schema_name: str, payload: dict[str, Any]) -> None:
    if schema_name not in SCHEMAS:
        supported = ", ".join(sorted(SCHEMAS))
        raise ValueError(f"Unknown schema '{schema_name}'. Supported: {supported}")
    Draft202012Validator(SCHEMAS[schema_name]).validate(payload)
