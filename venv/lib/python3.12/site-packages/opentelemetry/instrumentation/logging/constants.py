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

DEFAULT_LOGGING_FORMAT = "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s trace_sampled=%(otelTraceSampled)s] - %(message)s"


_MODULE_DOC = """
The OpenTelemetry ``logging`` integration automatically injects tracing context into log statements.

The integration registers a custom log record factory with the the standard library logging module that automatically inject
tracing context into log record objects. Optionally, the integration can also call ``logging.basicConfig()`` to set a logging
format with placeholders for span ID, trace ID and service name.

The following keys are injected into log record objects by the factory:

- ``otelSpanID``
- ``otelTraceID``
- ``otelServiceName``
- ``otelTraceSampled``

The integration uses the following logging format by default:

.. code-block::

    {default_logging_format}

Enable trace context injection
------------------------------

The integration is opt-in and must be enabled explicitly by setting the environment variable ``OTEL_PYTHON_LOG_CORRELATION`` to ``true``.

The integration always registers the custom factory that injects the tracing context into the log record objects. Setting
``OTEL_PYTHON_LOG_CORRELATION`` to ``true`` calls ``logging.basicConfig()`` to set a logging format that actually makes
use of the injected variables.


Environment variables
---------------------

.. envvar:: OTEL_PYTHON_LOG_CORRELATION

This env var must be set to ``true`` in order to enable trace context injection into logs by calling ``logging.basicConfig()`` and
setting a logging format that makes use of the injected tracing variables.

Alternatively, ``set_logging_format`` argument can be set to ``True`` when initializing the ``LoggingInstrumentor`` class to achieve the
same effect.

.. code-block::

    LoggingInstrumentor(set_logging_format=True)

The default value is ``false``.

.. envvar:: OTEL_PYTHON_LOG_FORMAT

This env var can be used to instruct the instrumentation to use a custom logging format.

Alternatively, a custom logging format can be passed to the ``LoggingInstrumentor`` as the ``logging_format`` argument. For example:

.. code-block::

    LoggingInstrumentor(logging_format='%(msg)s [span_id=%(span_id)s]')


The default value is:

.. code-block::

    {default_logging_format}

.. envvar:: OTEL_PYTHON_LOG_LEVEL

This env var can be used to set a custom logging level.

Alternatively, log level can be passed to the ``LoggingInstrumentor`` during initialization. For example:

.. code-block::

    LoggingInstrumentor(log_level=logging.DEBUG)


The default value is ``info``.

Options are:

- ``info``
- ``error``
- ``debug``
- ``warning``

Manually calling logging.basicConfig
------------------------------------

``logging.basicConfig()`` can be called to set a global logging level and format. Only the first ever call has any effect on the global logger.
Any subsequent calls have no effect and do not override a previously configured global logger. This integration calls ``logging.basicConfig()`` for you
when ``OTEL_PYTHON_LOG_CORRELATION`` is set to ``true``. It uses the format and level specified by ``OTEL_PYTHON_LOG_FORMAT`` and ``OTEL_PYTHON_LOG_LEVEL``
environment variables respectively.

If you code or some other library/framework you are using calls logging.basicConfig before this integration is enabled, then this integration's logging
format will not be used and log statements will not contain tracing context. For this reason, you'll need to make sure this integration is enabled as early
as possible in the service lifecycle or your framework is configured to use a logging format with placeholders for tracing context. This can be achieved by
adding the following placeholders to your logging format:

.. code-block::

    %(otelSpanID)s %(otelTraceID)s %(otelServiceName)s %(otelTraceSampled)s



API
-----

.. code-block:: python

    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    LoggingInstrumentor().instrument(set_logging_format=True)


Note
-----

If you do not set ``OTEL_PYTHON_LOG_CORRELATION`` to ``true`` but instead set the logging format manually or through your framework, you must ensure that this
integration is enabled before you set the logging format. This is important because unless the integration is enabled, the tracing context variables
are not injected into the log record objects. This means any attempted log statements made after setting the logging format and before enabling this integration
will result in KeyError exceptions. Such exceptions are automatically swallowed by the logging module and do not result in crashes but you may still lose out
on important log messages.
""".format(default_logging_format=DEFAULT_LOGGING_FORMAT)
