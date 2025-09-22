import logging
from typing import Dict

from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter as GRPCExporter,
)
from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    OTLPLogExporter as HTTPExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk._logs.export import LogExporter, BatchLogRecordProcessor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler

from opentelemetry.instrumentation.logging import LoggingInstrumentor


class LoggerWrapper(object):
    resource_attributes: dict = {}
    endpoint: str = None
    headers: Dict[str, str] = {}
    __logging_exporter: LogExporter = None
    __logging_provider: LoggerProvider = None

    def __new__(cls, exporter: LogExporter = None) -> "LoggerWrapper":
        if not hasattr(cls, "instance"):
            obj = cls.instance = super(LoggerWrapper, cls).__new__(cls)
            if not LoggerWrapper.endpoint:
                return obj

            obj.__logging_exporter = (
                exporter
                if exporter
                else init_logging_exporter(LoggerWrapper.endpoint, LoggerWrapper.headers)
            )
            obj.__logging_provider = init_logging_provider(
                obj.__logging_exporter, LoggerWrapper.resource_attributes
            )
            LoggingInstrumentor().instrument(set_logging_format=True)

        return cls.instance

    @staticmethod
    def set_static_params(
        resource_attributes: dict,
        endpoint: str,
        headers: Dict[str, str],
    ) -> None:
        LoggerWrapper.resource_attributes = resource_attributes
        LoggerWrapper.endpoint = endpoint
        LoggerWrapper.headers = headers


def init_logging_exporter(endpoint: str, headers: Dict[str, str]) -> LogExporter:
    if "http" in endpoint.lower() or "https" in endpoint.lower():
        return HTTPExporter(endpoint=f"{endpoint}/v1/logs", headers=headers)
    else:
        return GRPCExporter(endpoint=endpoint, headers=headers)


def init_logging_provider(
    exporter: LogExporter, resource_attributes: dict = None
) -> LoggerProvider:
    resource = (
        Resource.create(resource_attributes)
        if resource_attributes
        else Resource.create()
    )

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    logging_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logging.basicConfig(level=logging.INFO, handlers=[logging_handler])

    return logger_provider
