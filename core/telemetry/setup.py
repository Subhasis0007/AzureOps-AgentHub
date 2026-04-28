from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from time import perf_counter
from types import TracebackType
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from core.config.settings import RuntimeSettings, get_settings

azure_monitor_exporter: Any | None
try:
    import azure.monitor.opentelemetry.exporter as azure_monitor_exporter
except Exception:  # pragma: no cover - optional for constrained local envs
    azure_monitor_exporter = None


@dataclass(frozen=True)
class ACRGEMetrics:
    incident_count: Counter
    agent_invocations: Counter
    llm_tokens_used: Counter
    llm_cost_estimate_usd: Counter
    prs_created: Counter
    remediation_success: Counter
    agent_latency_ms: Histogram
    rag_retrieval_score: Histogram
    mttr_seconds: Histogram
    cache_hit_rate: Histogram


class Telemetry:
    def __init__(self, settings: RuntimeSettings) -> None:
        self._settings = settings
        self._meter = metrics.get_meter("acrge-lite")
        self.metrics = ACRGEMetrics(
            incident_count=self._meter.create_counter(
                "acrge.incident.count", description="Total incidents processed"
            ),
            agent_invocations=self._meter.create_counter(
                "acrge.agent.invocations", description="Agent execution count"
            ),
            llm_tokens_used=self._meter.create_counter(
                "acrge.llm.tokens.used", description="Estimated LLM tokens used"
            ),
            llm_cost_estimate_usd=self._meter.create_counter(
                "acrge.llm.cost.estimate.usd", description="Estimated LLM spend in USD"
            ),
            prs_created=self._meter.create_counter(
                "acrge.prs.created", description="Pull requests drafted by the platform"
            ),
            remediation_success=self._meter.create_counter(
                "acrge.remediation.success", description="Successful remediation actions"
            ),
            agent_latency_ms=self._meter.create_histogram(
                "acrge.agent.latency.ms", description="Agent latency in milliseconds"
            ),
            rag_retrieval_score=self._meter.create_histogram(
                "acrge.rag.retrieval.score", description="RAG retrieval quality score"
            ),
            mttr_seconds=self._meter.create_histogram(
                "acrge.mttr.seconds", description="Mean time to remediation/resolve"
            ),
            cache_hit_rate=self._meter.create_histogram(
                "acrge.cache.hit.rate", description="Semantic cache hit rate"
            ),
        )

    def start_span(self, name: str) -> AbstractContextManager[Any]:
        tracer = trace.get_tracer("acrge-lite")
        return tracer.start_as_current_span(name)

    def timed_block(self, metric: Histogram, attributes: dict[str, Any]) -> AbstractContextManager[None]:
        class _Timer:
            def __enter__(self) -> None:
                self.start = perf_counter()

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                elapsed_ms = (perf_counter() - self.start) * 1000
                metric.record(elapsed_ms, attributes=attributes)

        return _Timer()


def _build_resource(settings: RuntimeSettings) -> Resource:
    return Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.namespace": "acrge",
            "deployment.environment": settings.app_env,
            "service.version": "0.1.0",
        }
    )


def configure_telemetry(settings: RuntimeSettings | None = None) -> Telemetry:
    effective_settings = settings or get_settings()
    resource = _build_resource(effective_settings)

    metric_readers: list[PeriodicExportingMetricReader] = []

    if effective_settings.applicationinsights_connection_string and azure_monitor_exporter is not None:
        metric_exporter = azure_monitor_exporter.AzureMonitorMetricExporter(
            connection_string=effective_settings.applicationinsights_connection_string.get_secret_value()
        )
        metric_readers.append(PeriodicExportingMetricReader(metric_exporter))
    else:
        metric_readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))

    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)

    tracer_provider = TracerProvider(resource=resource)
    if effective_settings.applicationinsights_connection_string and azure_monitor_exporter is not None:
        trace_exporter = azure_monitor_exporter.AzureMonitorTraceExporter(
            connection_string=effective_settings.applicationinsights_connection_string.get_secret_value()
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    else:
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(tracer_provider)

    if effective_settings.applicationinsights_connection_string and azure_monitor_exporter is not None:
        # Reserved for future logging pipeline hookup.
        _ = azure_monitor_exporter.AzureMonitorLogExporter(
            connection_string=effective_settings.applicationinsights_connection_string.get_secret_value()
        )

    return Telemetry(effective_settings)
