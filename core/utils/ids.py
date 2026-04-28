from __future__ import annotations

from datetime import UTC, datetime
from hashlib import blake2b
from uuid import uuid4


DEFAULT_INCIDENT_PREFIX = "inc"
DEFAULT_AUDIT_PREFIX = "aud"
DEFAULT_PR_PREFIX = "pr"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(tz=UTC)


def compact_timestamp(ts: datetime | None = None) -> str:
    """Build a compact UTC timestamp useful for stable identifiers."""
    reference = ts or utc_now()
    return reference.strftime("%Y%m%d%H%M%S")


def generate_id(prefix: str, *, entropy: int = 10) -> str:
    """
    Generate a safe, compact identifier.

    Format: <prefix>_<utc_timestamp>_<random>
    Example: inc_20260428153001_a3f92c5e11
    """
    normalized_prefix = prefix.strip().lower().replace(" ", "-")
    random_fragment = uuid4().hex[:entropy]
    return f"{normalized_prefix}_{compact_timestamp()}_{random_fragment}"


def incident_id() -> str:
    return generate_id(DEFAULT_INCIDENT_PREFIX)


def audit_id() -> str:
    return generate_id(DEFAULT_AUDIT_PREFIX)


def pr_branch_name(incident_identifier: str) -> str:
    """
    Generate branch names in the required shape: acrge/fix/{incident_id}.
    """
    sanitized = incident_identifier.strip().replace(" ", "-").replace("/", "-")
    return f"acrge/fix/{sanitized}"


def deterministic_fingerprint(content: str, *, digest_size: int = 16) -> str:
    """Create deterministic fingerprints for dedupe/idempotency checks."""
    hasher = blake2b(digest_size=digest_size)
    hasher.update(content.encode("utf-8"))
    return hasher.hexdigest()
