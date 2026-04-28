from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from core.config.settings import RuntimeSettings, get_settings

azure_appconfiguration: Any | None
try:
    import azure.appconfiguration as azure_appconfiguration
except Exception:  # pragma: no cover - optional import path for local testing
    azure_appconfiguration = None


class GovernancePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str = Field(default="v1", min_length=1)
    auto_approve_max_risk: str = Field(default="low")
    confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    protected_branches: list[str] = Field(default_factory=lambda: ["main", "release"])
    require_human_for_production: bool = True
    require_human_for_data_mutation: bool = True
    allow_auto_remediation: bool = False
    outbound_allowlist: list[str] = Field(default_factory=list)

    @field_validator("auto_approve_max_risk")
    @classmethod
    def normalize_risk(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"low", "medium", "high", "critical"}:
            raise ValueError("auto_approve_max_risk must be one of low/medium/high/critical")
        return normalized


DEFAULT_POLICY = GovernancePolicy(
    policy_version="v1",
    auto_approve_max_risk="low",
    confidence_threshold=0.65,
    protected_branches=["main", "release"],
    require_human_for_production=True,
    require_human_for_data_mutation=True,
    allow_auto_remediation=False,
    outbound_allowlist=[],
)


def _parse_policy_blob(raw: str | dict[str, Any]) -> GovernancePolicy:
    if isinstance(raw, str):
        loaded = yaml.safe_load(raw) or {}
    else:
        loaded = raw
    try:
        return GovernancePolicy.model_validate(loaded)
    except ValidationError:
        return DEFAULT_POLICY


def load_policy_from_file(path: str | Path) -> GovernancePolicy:
    policy_path = Path(path)
    if not policy_path.exists():
        return DEFAULT_POLICY
    text = policy_path.read_text(encoding="utf-8")
    return _parse_policy_blob(text)


def load_policy_from_app_config(settings: RuntimeSettings) -> GovernancePolicy:
    if not settings.app_config_endpoint or azure_appconfiguration is None:
        return DEFAULT_POLICY

    client = azure_appconfiguration.AzureAppConfigurationClient(
        base_url=settings.app_config_endpoint,
        credential=settings.build_credential(),
    )

    try:
        setting = client.get_configuration_setting(key=settings.app_config_policy_key)
        if setting is None or not setting.value:
            return DEFAULT_POLICY
        return _parse_policy_blob(setting.value)
    except Exception:
        return DEFAULT_POLICY
    finally:
        client.close()


def load_governance_policy(
    *,
    settings: RuntimeSettings | None = None,
    local_override_path: str | Path | None = None,
) -> GovernancePolicy:
    """
    Resolve policy with secure precedence:
    1) Local override file if explicitly supplied (dev/test convenience)
    2) Azure App Configuration
    3) Built-in secure defaults
    """
    effective_settings = settings or get_settings()

    if local_override_path:
        file_policy = load_policy_from_file(local_override_path)
        if file_policy != DEFAULT_POLICY:
            return file_policy

    cloud_policy = load_policy_from_app_config(effective_settings)
    return cloud_policy
