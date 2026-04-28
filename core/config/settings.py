from __future__ import annotations

from functools import lru_cache
from typing import Literal

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from pydantic import BaseModel, Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceBusSettings(BaseModel):
    namespace: str = Field(default="")
    connection_string: SecretStr | None = None
    inbound_topic: str = Field(default="acrge.events.inbound", min_length=3)


class CosmosSettings(BaseModel):
    endpoint: str = ""
    database_name: str = "acrge"
    incidents_container: str = "incidents"
    audit_container: str = "audit"


class RedisSettings(BaseModel):
    host: str = ""
    port: int = Field(default=6380, ge=1, le=65535)
    ssl: bool = True
    password: SecretStr | None = None
    ttl_seconds: int = Field(default=900, ge=60, le=86400)


class BlobSettings(BaseModel):
    account_url: str = ""
    raw_logs_container: str = "acrge-raw-logs"
    artifacts_container: str = "acrge-artifacts"


class SearchSettings(BaseModel):
    endpoint: str = ""
    incidents_index: str = "acrge-incidents"
    api_key: SecretStr | None = None


class FoundrySettings(BaseModel):
    project_endpoint: str = ""
    gpt4o_deployment: str = "gpt-4o"
    gpt4o_mini_deployment: str = "gpt-4o-mini"
    embedding_deployment: str = "text-embedding-3-large"


class AzureDevOpsSettings(BaseModel):
    org_url: str = ""
    project: str = ""
    repository_id: str = ""
    pat: SecretStr | None = None


class TelemetrySettings(BaseModel):
    app_insights_connection_string: SecretStr | None = None
    otlp_endpoint: str = ""
    service_name: str = "acrge-lite"


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["dev", "test", "stage", "prod"] = "dev"
    app_name: str = Field(default="acrge-lite", min_length=3)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    azure_tenant_id: str | None = None
    azure_subscription_id: str | None = None
    azure_client_id: str | None = None

    servicebus_fully_qualified_namespace: str = ""
    servicebus_connection_string: SecretStr | None = None
    acrge_inbound_topic: str = "acrge.events.inbound"

    cosmos_endpoint: str = ""
    cosmos_database_name: str = "acrge"
    cosmos_incidents_container: str = "incidents"
    cosmos_audit_container: str = "audit"

    redis_host: str = ""
    redis_port: int = 6380
    redis_ssl: bool = True
    redis_password: SecretStr | None = None
    redis_ttl_seconds: int = 900

    blob_account_url: str = ""
    blob_container_raw_logs: str = "acrge-raw-logs"
    blob_container_artifacts: str = "acrge-artifacts"

    ai_search_endpoint: str = ""
    ai_search_index_incidents: str = "acrge-incidents"
    ai_search_api_key: SecretStr | None = None

    foundry_project_endpoint: str = ""
    foundry_model_deployment_name_gpt4o: str = "gpt-4o"
    foundry_model_deployment_name_gpt4o_mini: str = "gpt-4o-mini"
    foundry_embedding_deployment_name: str = "text-embedding-3-large"

    key_vault_url: str = ""
    app_config_endpoint: str = ""
    app_config_policy_key: str = "acrge/policies/governance"

    azdo_org_url: str = ""
    azdo_project: str = ""
    azdo_repo_id: str = ""
    azdo_pat: SecretStr | None = None

    teams_webhook_url: str = ""

    auto_remediation_enabled: bool = False
    human_approval_required_default: bool = True

    applicationinsights_connection_string: SecretStr | None = None
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "acrge-lite"

    @field_validator("acrge_inbound_topic")
    @classmethod
    def validate_topic_name(cls, value: str) -> str:
        normalized = value.strip()
        if "." not in normalized:
            raise ValueError("Inbound topic must follow namespace.topic naming style.")
        return normalized

    @computed_field
    @property
    def service_bus(self) -> ServiceBusSettings:
        return ServiceBusSettings(
            namespace=self.servicebus_fully_qualified_namespace,
            connection_string=self.servicebus_connection_string,
            inbound_topic=self.acrge_inbound_topic,
        )

    @computed_field
    @property
    def cosmos(self) -> CosmosSettings:
        return CosmosSettings(
            endpoint=self.cosmos_endpoint,
            database_name=self.cosmos_database_name,
            incidents_container=self.cosmos_incidents_container,
            audit_container=self.cosmos_audit_container,
        )

    @computed_field
    @property
    def redis(self) -> RedisSettings:
        return RedisSettings(
            host=self.redis_host,
            port=self.redis_port,
            ssl=self.redis_ssl,
            password=self.redis_password,
            ttl_seconds=self.redis_ttl_seconds,
        )

    @computed_field
    @property
    def blob(self) -> BlobSettings:
        return BlobSettings(
            account_url=self.blob_account_url,
            raw_logs_container=self.blob_container_raw_logs,
            artifacts_container=self.blob_container_artifacts,
        )

    @computed_field
    @property
    def search(self) -> SearchSettings:
        return SearchSettings(
            endpoint=self.ai_search_endpoint,
            incidents_index=self.ai_search_index_incidents,
            api_key=self.ai_search_api_key,
        )

    @computed_field
    @property
    def foundry(self) -> FoundrySettings:
        return FoundrySettings(
            project_endpoint=self.foundry_project_endpoint,
            gpt4o_deployment=self.foundry_model_deployment_name_gpt4o,
            gpt4o_mini_deployment=self.foundry_model_deployment_name_gpt4o_mini,
            embedding_deployment=self.foundry_embedding_deployment_name,
        )

    @computed_field
    @property
    def azure_devops(self) -> AzureDevOpsSettings:
        return AzureDevOpsSettings(
            org_url=self.azdo_org_url,
            project=self.azdo_project,
            repository_id=self.azdo_repo_id,
            pat=self.azdo_pat,
        )

    @computed_field
    @property
    def telemetry(self) -> TelemetrySettings:
        return TelemetrySettings(
            app_insights_connection_string=self.applicationinsights_connection_string,
            otlp_endpoint=self.otel_exporter_otlp_endpoint,
            service_name=self.otel_service_name,
        )

    def use_managed_identity(self) -> bool:
        return bool(self.azure_client_id) or self.app_env in {"stage", "prod"}

    def build_credential(self) -> DefaultAzureCredential | ManagedIdentityCredential:
        if self.use_managed_identity() and self.azure_client_id:
            return ManagedIdentityCredential(client_id=self.azure_client_id)
        if self.use_managed_identity():
            return ManagedIdentityCredential()
        return DefaultAzureCredential(exclude_interactive_browser_credential=False)


@lru_cache(maxsize=1)
def get_settings() -> RuntimeSettings:
    return RuntimeSettings()
