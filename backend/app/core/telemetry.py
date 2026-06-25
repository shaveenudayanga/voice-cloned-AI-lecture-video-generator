# SPDX-License-Identifier: Apache-2.0
import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter

from app.core.config import settings

logger = structlog.get_logger(__name__)


def configure_telemetry() -> None:
    """Initialize OpenTelemetry tracing. Exporter is configured via OTEL_EXPORTER env."""
    resource = Resource.create({"service.name": "lecturevoice-api", "service.version": settings.app_version})
    provider = TracerProvider(resource=resource)

    exporter: SpanExporter
    if settings.otel_exporter == "otlp" and settings.otel_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        logger.info("otel_exporter_otlp", endpoint=settings.otel_endpoint)
    else:
        exporter = ConsoleSpanExporter()
        logger.info("otel_exporter_stdout")

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
