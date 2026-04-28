from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, cast

from opentelemetry.metrics import Histogram

from core.config.settings import RuntimeSettings
from core.telemetry.setup import Telemetry


class FakeCounter:
    def __init__(self) -> None:
        self.values: list[float] = []

    def add(self, value: float, attributes: dict[str, Any] | None = None) -> None:
        self.values.append(value)


class FakeHistogram:
    def __init__(self) -> None:
        self.records: list[float] = []

    def record(self, value: float, attributes: dict[str, Any] | None = None) -> None:
        self.records.append(value)


class FakeMeter:
    def create_counter(self, name: str, description: str = "") -> FakeCounter:
        return FakeCounter()

    def create_histogram(self, name: str, description: str = "") -> FakeHistogram:
        return FakeHistogram()


class FakeMetricsModule:
    def get_meter(self, name: str) -> FakeMeter:
        return FakeMeter()


class FakeTraceModule:
    @contextmanager
    def _span(self) -> Iterator[object]:
        yield object()

    def get_tracer(self, name: str) -> Any:
        class _Tracer:
            def start_as_current_span(self, span_name: str) -> AbstractContextManager[object]:
                return FakeTraceModule()._span()

        return _Tracer()


def test_telemetry_timed_block_records_latency(monkeypatch: Any) -> None:
    import core.telemetry.setup as telemetry_setup

    monkeypatch.setattr(telemetry_setup, "metrics", FakeMetricsModule())
    monkeypatch.setattr(telemetry_setup, "trace", FakeTraceModule())

    telemetry = Telemetry(RuntimeSettings())
    histogram = cast(FakeHistogram, telemetry.metrics.agent_latency_ms)

    with telemetry.timed_block(cast(Histogram, histogram), attributes={"agent": "test"}):
        _ = 1 + 1

    assert len(histogram.records) == 1
    assert histogram.records[0] >= 0.0


def test_telemetry_start_span_context_manager(monkeypatch: Any) -> None:
    import core.telemetry.setup as telemetry_setup

    monkeypatch.setattr(telemetry_setup, "metrics", FakeMetricsModule())
    monkeypatch.setattr(telemetry_setup, "trace", FakeTraceModule())

    telemetry = Telemetry(RuntimeSettings())
    with telemetry.start_span("sample-span"):
        value = 42
    assert value == 42
