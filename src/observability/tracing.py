from __future__ import annotations

from typing import Any, Literal

from services.observability import get_logger

_logger = get_logger("tracing")


def initialize_tracing(service_name: str = "quantvision-api") -> bool:
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        processor = BatchSpanProcessor(OTLPSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        _logger.info("tracing_initialized service=%s", service_name)
        return True
    except Exception as exc:  # pragma: no cover - optional dependency
        _logger.warning("tracing_not_initialized reason=%s", str(exc))
        return False


def get_tracer(name: str) -> Any | None:
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except Exception:  # pragma: no cover - optional dependency
        return None


def trace_kv_span(tracer: Any, span_name: str, **attributes: Any) -> Any:
    if tracer is None:

        class _Noop:
            def __enter__(self) -> "_Noop":
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_val: BaseException | None,
                exc_tb: object,
            ) -> Literal[False]:
                return False

        return _Noop()

    return tracer.start_as_current_span(span_name, attributes=attributes)
