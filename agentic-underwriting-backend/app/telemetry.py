"""
Telemetry bootstrap for Azure Monitor / Application Insights via OpenTelemetry.
Best-effort: failures to export telemetry will not break the app.
"""
import logging
import os

from dotenv import load_dotenv

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource

# Load .env so APPLICATIONINSIGHTS_CONNECTION_STRING is available during import
load_dotenv()

_connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

# Configure exporter only when telemetry is actually configured.
# The app must continue to start without Application Insights.
if _connection_string:
    try:
        configure_azure_monitor(connection_string=_connection_string)
    except Exception:
        logging.exception("Azure Monitor telemetry initialization failed; continuing without telemetry.")
else:
    logging.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set; skipping Azure Monitor telemetry initialization.")

# Define resource attributes (can also be set via OTEL_RESOURCE_ATTRIBUTES env)
_resource = Resource.create({
    "service.name": os.getenv("OTEL_SERVICE_NAME", "agentic-underwriting-backend"),
})

# Instrument stdlib logging so logs ship to App Insights, while keeping console logs
LoggingInstrumentor().instrument(set_logging_format=True, log_level=logging.INFO)


def instrument_app(app):
    """Instrument FastAPI and outbound HTTP (requests)."""
    FastAPIInstrumentor.instrument_app(app, tracer_provider=None)  # use default provider/exporter
    RequestsInstrumentor().instrument()
