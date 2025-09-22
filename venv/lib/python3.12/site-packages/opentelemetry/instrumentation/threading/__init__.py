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
"""
Instrument threading to propagate OpenTelemetry context.

Usage
-----

.. code-block:: python

    from opentelemetry.instrumentation.threading import ThreadingInstrumentor

    ThreadingInstrumentor().instrument()

This library provides instrumentation for the `threading` module to ensure that
the OpenTelemetry context is propagated across threads. It is important to note
that this instrumentation does not produce any telemetry data on its own. It
merely ensures that the context is correctly propagated when threads are used.


When instrumented, new threads created using threading.Thread, threading.Timer,
or within futures.ThreadPoolExecutor will have the current OpenTelemetry
context attached, and this context will be re-activated in the thread's
run method or the executor's worker thread."
"""

from __future__ import annotations

import threading
from concurrent import futures
from typing import TYPE_CHECKING, Any, Callable, Collection

from wrapt import (
    wrap_function_wrapper,  # type: ignore[reportUnknownVariableType]
)

from opentelemetry import context
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.threading.package import _instruments
from opentelemetry.instrumentation.utils import unwrap

if TYPE_CHECKING:
    from typing import Protocol, TypeVar

    R = TypeVar("R")

    class HasOtelContext(Protocol):
        _otel_context: context.Context


class ThreadingInstrumentor(BaseInstrumentor):
    __WRAPPER_START_METHOD = "start"
    __WRAPPER_RUN_METHOD = "run"
    __WRAPPER_SUBMIT_METHOD = "submit"

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any):
        self._instrument_thread()
        self._instrument_timer()
        self._instrument_thread_pool()

    def _uninstrument(self, **kwargs: Any):
        self._uninstrument_thread()
        self._uninstrument_timer()
        self._uninstrument_thread_pool()

    @staticmethod
    def _instrument_thread():
        wrap_function_wrapper(
            threading.Thread,
            ThreadingInstrumentor.__WRAPPER_START_METHOD,
            ThreadingInstrumentor.__wrap_threading_start,
        )
        wrap_function_wrapper(
            threading.Thread,
            ThreadingInstrumentor.__WRAPPER_RUN_METHOD,
            ThreadingInstrumentor.__wrap_threading_run,
        )

    @staticmethod
    def _instrument_timer():
        wrap_function_wrapper(
            threading.Timer,
            ThreadingInstrumentor.__WRAPPER_START_METHOD,
            ThreadingInstrumentor.__wrap_threading_start,
        )
        wrap_function_wrapper(
            threading.Timer,
            ThreadingInstrumentor.__WRAPPER_RUN_METHOD,
            ThreadingInstrumentor.__wrap_threading_run,
        )

    @staticmethod
    def _instrument_thread_pool():
        wrap_function_wrapper(
            futures.ThreadPoolExecutor,
            ThreadingInstrumentor.__WRAPPER_SUBMIT_METHOD,
            ThreadingInstrumentor.__wrap_thread_pool_submit,
        )

    @staticmethod
    def _uninstrument_thread():
        unwrap(threading.Thread, ThreadingInstrumentor.__WRAPPER_START_METHOD)
        unwrap(threading.Thread, ThreadingInstrumentor.__WRAPPER_RUN_METHOD)

    @staticmethod
    def _uninstrument_timer():
        unwrap(threading.Timer, ThreadingInstrumentor.__WRAPPER_START_METHOD)
        unwrap(threading.Timer, ThreadingInstrumentor.__WRAPPER_RUN_METHOD)

    @staticmethod
    def _uninstrument_thread_pool():
        unwrap(
            futures.ThreadPoolExecutor,
            ThreadingInstrumentor.__WRAPPER_SUBMIT_METHOD,
        )

    @staticmethod
    def __wrap_threading_start(
        call_wrapped: Callable[[], None],
        instance: HasOtelContext,
        args: tuple[()],
        kwargs: dict[str, Any],
    ) -> None:
        instance._otel_context = context.get_current()
        return call_wrapped(*args, **kwargs)

    @staticmethod
    def __wrap_threading_run(
        call_wrapped: Callable[..., R],
        instance: HasOtelContext,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> R:
        token = None
        try:
            token = context.attach(instance._otel_context)
            return call_wrapped(*args, **kwargs)
        finally:
            if token is not None:
                context.detach(token)

    @staticmethod
    def __wrap_thread_pool_submit(
        call_wrapped: Callable[..., R],
        instance: futures.ThreadPoolExecutor,
        args: tuple[Callable[..., Any], ...],
        kwargs: dict[str, Any],
    ) -> R:
        # obtain the original function and wrapped kwargs
        original_func = args[0]
        otel_context = context.get_current()

        def wrapped_func(*func_args: Any, **func_kwargs: Any) -> R:
            token = None
            try:
                token = context.attach(otel_context)
                return original_func(*func_args, **func_kwargs)
            finally:
                if token is not None:
                    context.detach(token)

        # replace the original function with the wrapped function
        new_args: tuple[Callable[..., Any], ...] = (wrapped_func,) + args[1:]
        return call_wrapped(*new_args, **kwargs)
