# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=empty-docstring,no-value-for-parameter,no-member,no-name-in-module

"""
The OpenTelemetry `logging` integration automatically injects tracing context into
log statements, though it is opt-in and must be enabled explicitly by setting the
environment variable `OTEL_PYTHON_LOG_CORRELATION` to `true`.

.. code-block:: python

    import logging

    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    LoggingInstrumentor().instrument()

    logging.warning('OTel test')

When running the above example you will see the following output:

::

    2025-03-05 09:40:04,398 WARNING [root] [example.py:7] [trace_id=0 span_id=0 resource.service.name= trace_sampled=False] - OTel test

The environment variable `OTEL_PYTHON_LOG_CORRELATION` must be set to `true`
in order to enable trace context injection into logs by calling
`logging.basicConfig()` and setting a logging format that makes use of the
injected tracing variables.

Alternatively, `set_logging_format` argument can be set to `True` when
initializing the `LoggingInstrumentor` class to achieve the same effect:

.. code-block:: python

    import logging

    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    LoggingInstrumentor().instrument(set_logging_format=True)

    logging.warning('OTel test')

"""

import logging  # pylint: disable=import-self
from os import environ
from typing import Collection

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.logging.constants import (
    _MODULE_DOC,
    DEFAULT_LOGGING_FORMAT,
)
from opentelemetry.instrumentation.logging.environment_variables import (
    OTEL_PYTHON_LOG_CORRELATION,
    OTEL_PYTHON_LOG_FORMAT,
    OTEL_PYTHON_LOG_LEVEL,
)
from opentelemetry.instrumentation.logging.package import _instruments
from opentelemetry.trace import (
    INVALID_SPAN,
    INVALID_SPAN_CONTEXT,
    get_current_span,
    get_tracer_provider,
)

__doc__ = _MODULE_DOC  # noqa: A001

LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


class LoggingInstrumentor(BaseInstrumentor):  # pylint: disable=empty-docstring
    __doc__ = f"""An instrumentor for stdlib logging module.

    This instrumentor injects tracing context into logging records and optionally sets the global logging format to the following:

    .. code-block::

        {DEFAULT_LOGGING_FORMAT}

        def log_hook(span: Span, record: LogRecord):
                if span and span.is_recording():
                    record.custom_user_attribute_from_log_hook = "some-value"

    Args:
        tracer_provider: Tracer provider instance that can be used to fetch a tracer.
        set_logging_format: When set to True, it calls logging.basicConfig() and sets a logging format.
        logging_format: Accepts a string and sets it as the logging format when set_logging_format
            is set to True.
        log_level: Accepts one of the following values and sets the logging level to it.
            logging.INFO
            logging.DEBUG
            logging.WARN
            logging.ERROR
            logging.FATAL
        log_hook: execute custom logic when record is created

    See `BaseInstrumentor`
    """

    _old_factory = None
    _log_hook = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        provider = kwargs.get("tracer_provider", None) or get_tracer_provider()
        old_factory = logging.getLogRecordFactory()
        LoggingInstrumentor._old_factory = old_factory
        LoggingInstrumentor._log_hook = kwargs.get("log_hook", None)

        service_name = None

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)

            record.otelSpanID = "0"
            record.otelTraceID = "0"
            record.otelTraceSampled = False

            nonlocal service_name
            if service_name is None:
                resource = getattr(provider, "resource", None)
                if resource:
                    service_name = (
                        resource.attributes.get("service.name") or ""
                    )
                else:
                    service_name = ""

            record.otelServiceName = service_name

            span = get_current_span()
            if span != INVALID_SPAN:
                ctx = span.get_span_context()
                if ctx != INVALID_SPAN_CONTEXT:
                    record.otelSpanID = format(ctx.span_id, "016x")
                    record.otelTraceID = format(ctx.trace_id, "032x")
                    record.otelTraceSampled = ctx.trace_flags.sampled
                    if callable(LoggingInstrumentor._log_hook):
                        try:
                            LoggingInstrumentor._log_hook(  # pylint: disable=E1102
                                span, record
                            )
                        except Exception:  # pylint: disable=W0703
                            pass

            return record

        logging.setLogRecordFactory(record_factory)

        set_logging_format = kwargs.get(
            "set_logging_format",
            environ.get(OTEL_PYTHON_LOG_CORRELATION, "false").lower()
            == "true",
        )

        if set_logging_format:
            log_format = kwargs.get(
                "logging_format", environ.get(OTEL_PYTHON_LOG_FORMAT, None)
            )
            log_format = log_format or DEFAULT_LOGGING_FORMAT

            log_level = kwargs.get(
                "log_level", LEVELS.get(environ.get(OTEL_PYTHON_LOG_LEVEL))
            )
            log_level = log_level or logging.INFO

            logging.basicConfig(format=log_format, level=log_level)

    def _uninstrument(self, **kwargs):
        if LoggingInstrumentor._old_factory:
            logging.setLogRecordFactory(LoggingInstrumentor._old_factory)
            LoggingInstrumentor._old_factory = None
