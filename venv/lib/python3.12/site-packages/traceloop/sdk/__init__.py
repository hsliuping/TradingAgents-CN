import os
import sys
from pathlib import Path

from typing import Callable, Optional, Set
from colorama import Fore
from opentelemetry.sdk.trace import SpanProcessor, ReadableSpan
from opentelemetry.sdk.trace.sampling import Sampler
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.metrics.export import MetricExporter
from opentelemetry.sdk._logs.export import LogExporter
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.propagators.textmap import TextMapPropagator
from opentelemetry.util.re import parse_env_headers

from traceloop.sdk.images.image_uploader import ImageUploader
from traceloop.sdk.metrics.metrics import MetricsWrapper
from traceloop.sdk.logging.logging import LoggerWrapper
from traceloop.sdk.telemetry import Telemetry
from traceloop.sdk.instruments import Instruments
from traceloop.sdk.config import (
    is_content_tracing_enabled,
    is_tracing_enabled,
    is_metrics_enabled,
    is_logging_enabled,
)
from traceloop.sdk.fetcher import Fetcher
from traceloop.sdk.tracing.tracing import (
    TracerWrapper,
    set_association_properties,
    set_external_prompt_tracing_context,
)
from typing import Dict
from traceloop.sdk.client.client import Client


class Traceloop:
    AUTO_CREATED_KEY_PATH = str(
        Path.home() / ".cache" / "traceloop" / "auto_created_key"
    )
    AUTO_CREATED_URL = str(Path.home() / ".cache" / "traceloop" / "auto_created_url")

    __tracer_wrapper: TracerWrapper
    __fetcher: Optional[Fetcher] = None
    __app_name: Optional[str] = None
    __client: Optional[Client] = None

    @staticmethod
    def init(
        app_name: str = sys.argv[0],
        api_endpoint: str = "https://api.traceloop.com",
        api_key: Optional[str] = None,
        enabled: bool = True,
        headers: Dict[str, str] = {},
        disable_batch=False,
        telemetry_enabled: bool = True,
        exporter: Optional[SpanExporter] = None,
        metrics_exporter: MetricExporter = None,
        metrics_headers: Dict[str, str] = None,
        logging_exporter: LogExporter = None,
        logging_headers: Dict[str, str] = None,
        processor: Optional[SpanProcessor] = None,
        propagator: TextMapPropagator = None,
        sampler: Optional[Sampler] = None,
        traceloop_sync_enabled: bool = False,
        should_enrich_metrics: bool = True,
        resource_attributes: dict = {},
        instruments: Optional[Set[Instruments]] = None,
        block_instruments: Optional[Set[Instruments]] = None,
        image_uploader: Optional[ImageUploader] = None,
        span_postprocess_callback: Optional[Callable[[ReadableSpan], None]] = None,
    ) -> Optional[Client]:
        if not enabled:
            TracerWrapper.set_disabled(True)
            print(
                Fore.YELLOW
                + "Traceloop instrumentation is disabled via init flag"
                + Fore.RESET
            )
            return

        telemetry_enabled = (
            telemetry_enabled
            and (os.getenv("TRACELOOP_TELEMETRY") or "true").lower() == "true"
        )
        if telemetry_enabled:
            Telemetry()

        api_endpoint = os.getenv("TRACELOOP_BASE_URL") or api_endpoint
        api_key = os.getenv("TRACELOOP_API_KEY") or api_key
        Traceloop.__app_name = app_name

        if not is_tracing_enabled():
            print(Fore.YELLOW + "Tracing is disabled" + Fore.RESET)
            return

        enable_content_tracing = is_content_tracing_enabled()

        if exporter or processor:
            print(Fore.GREEN + "Traceloop exporting traces to a custom exporter")

        headers = os.getenv("TRACELOOP_HEADERS") or headers

        if isinstance(headers, str):
            headers = parse_env_headers(headers)

        if (
            not exporter
            and not processor
            and api_endpoint == "https://api.traceloop.com"
            and not api_key
        ):
            print(
                Fore.RED
                + "Error: Missing Traceloop API key,"
                + " go to https://app.traceloop.com/settings/api-keys to create one"
            )
            print("Set the TRACELOOP_API_KEY environment variable to the key")
            print(Fore.RESET)
            return

        if not exporter and not processor and headers:
            print(
                Fore.GREEN
                + f"Traceloop exporting traces to {api_endpoint}, authenticating with custom headers"
            )

        if api_key and not exporter and not processor and not headers:
            print(
                Fore.GREEN
                + f"Traceloop exporting traces to {api_endpoint} authenticating with bearer token"
            )
            headers = {
                "Authorization": f"Bearer {api_key}",
            }

        print(Fore.RESET)

        # Tracer init
        resource_attributes.update({SERVICE_NAME: app_name})
        TracerWrapper.set_static_params(
            resource_attributes, enable_content_tracing, api_endpoint, headers
        )
        Traceloop.__tracer_wrapper = TracerWrapper(
            disable_batch=disable_batch,
            processor=processor,
            propagator=propagator,
            exporter=exporter,
            sampler=sampler,
            should_enrich_metrics=should_enrich_metrics,
            image_uploader=image_uploader or ImageUploader(api_endpoint, api_key),
            instruments=instruments,
            block_instruments=block_instruments,
            span_postprocess_callback=span_postprocess_callback,
        )

        if not is_metrics_enabled() or not metrics_exporter and exporter:
            print(Fore.YELLOW + "Metrics are disabled" + Fore.RESET)
        else:
            metrics_endpoint = os.getenv("TRACELOOP_METRICS_ENDPOINT") or api_endpoint
            metrics_headers = (
                os.getenv("TRACELOOP_METRICS_HEADERS") or metrics_headers or headers
            )
            if metrics_exporter or processor:
                print(Fore.GREEN + "Traceloop exporting metrics to a custom exporter")

            MetricsWrapper.set_static_params(
                resource_attributes, metrics_endpoint, metrics_headers
            )
            Traceloop.__metrics_wrapper = MetricsWrapper(exporter=metrics_exporter)

        if is_logging_enabled() and (logging_exporter or not exporter):
            logging_endpoint = os.getenv("TRACELOOP_LOGGING_ENDPOINT") or api_endpoint
            logging_headers = (
                os.getenv("TRACELOOP_LOGGING_HEADERS") or logging_headers or headers
            )
            if logging_exporter or processor:
                print(Fore.GREEN + "Traceloop exporting logs to a custom exporter")

            LoggerWrapper.set_static_params(
                resource_attributes, logging_endpoint, logging_headers
            )
            Traceloop.__logger_wrapper = LoggerWrapper(exporter=logging_exporter)

        if (
            api_endpoint.find("traceloop.com") != -1
            and api_key
            and (exporter is None)
            and (processor is None)
        ):
            if traceloop_sync_enabled:
                Traceloop.__fetcher = Fetcher(base_url=api_endpoint, api_key=api_key)
                Traceloop.__fetcher.run()
                print(
                    Fore.GREEN
                    + "Traceloop syncing configuration and prompts"
                    + Fore.RESET
                )
            Traceloop.__client = Client(
                api_key=api_key, app_name=app_name, api_endpoint=api_endpoint
            )
            return Traceloop.__client

    def set_association_properties(properties: dict) -> None:
        set_association_properties(properties)

    def set_prompt(template: str, variables: dict, version: int):
        set_external_prompt_tracing_context(template, variables, version)

    @staticmethod
    def get():
        """
        Returns the shared SDK client instance, using the current global configuration.

        To use the SDK as a singleton, first make sure you have called :func:`Traceloop.init()`
        at startup time. Then ``get()`` will return the same shared :class:`Traceloop.client.Client`
        instance each time. The client will be initialized if it has not been already.

        If you need to create multiple client instances with different configurations, instead of this
        singleton approach you can call the :class:`Traceloop.client.Client` constructor directly instead.
        """
        if not Traceloop.__client:
            raise Exception(
                "Client not initialized, you should call Traceloop.init() first. "
                "If you are still getting this error - you are missing the api key"
            )
        return Traceloop.__client
