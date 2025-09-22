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
# type: ignore

"""
OpenTelemetry Base Instrumentor
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any, Collection

from opentelemetry.instrumentation._semconv import (
    _OpenTelemetrySemanticConventionStability,
)
from opentelemetry.instrumentation.dependencies import (
    DependencyConflict,
    DependencyConflictError,
    get_dependency_conflicts,
)

_LOG = getLogger(__name__)


class BaseInstrumentor(ABC):
    """An ABC for instrumentors.

    Child classes of this ABC should instrument specific third
    party libraries or frameworks either by using the
    ``opentelemetry-instrument`` command or by calling their methods
    directly.

    Since every third party library or framework is different and has different
    instrumentation needs, more methods can be added to the child classes as
    needed to provide practical instrumentation to the end user.
    """

    _instance = None
    _is_instrumented_by_opentelemetry = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls)

        return cls._instance

    @property
    def is_instrumented_by_opentelemetry(self):
        return self._is_instrumented_by_opentelemetry

    @abstractmethod
    def instrumentation_dependencies(self) -> Collection[str]:
        """Return a list of python packages with versions that the will be instrumented.

        The format should be the same as used in requirements.txt or pyproject.toml.

        For example, if an instrumentation instruments requests 1.x, this method should look
        like:

            def instrumentation_dependencies(self) -> Collection[str]:
                return ['requests ~= 1.0']

        This will ensure that the instrumentation will only be used when the specified library
        is present in the environment.
        """

    def _instrument(self, **kwargs: Any):
        """Instrument the library"""

    @abstractmethod
    def _uninstrument(self, **kwargs: Any):
        """Uninstrument the library"""

    def _check_dependency_conflicts(self) -> DependencyConflict | None:
        dependencies = self.instrumentation_dependencies()
        return get_dependency_conflicts(dependencies)

    def instrument(self, **kwargs: Any):
        """Instrument the library

        This method will be called without any optional arguments by the
        ``opentelemetry-instrument`` command.

        This means that calling this method directly without passing any
        optional values should do the very same thing that the
        ``opentelemetry-instrument`` command does.
        """

        if self._is_instrumented_by_opentelemetry:
            _LOG.warning("Attempting to instrument while already instrumented")
            return None

        # check if instrumentor has any missing or conflicting dependencies
        skip_dep_check = kwargs.pop("skip_dep_check", False)
        raise_exception_on_conflict = kwargs.pop(
            "raise_exception_on_conflict", False
        )
        if not skip_dep_check:
            conflict = self._check_dependency_conflicts()
            if conflict:
                # auto-instrumentation path: don't log conflict as error, instead
                # let _load_instrumentors handle the exception
                if raise_exception_on_conflict:
                    raise DependencyConflictError(conflict)
                # manual instrumentation path: log the conflict as error
                _LOG.error(conflict)
                return None

        # initialize semantic conventions opt-in if needed
        _OpenTelemetrySemanticConventionStability._initialize()

        result = self._instrument(  # pylint: disable=assignment-from-no-return
            **kwargs
        )
        self._is_instrumented_by_opentelemetry = True
        return result

    def uninstrument(self, **kwargs: Any):
        """Uninstrument the library

        See ``BaseInstrumentor.instrument`` for more information regarding the
        usage of ``kwargs``.
        """

        if self._is_instrumented_by_opentelemetry:
            result = self._uninstrument(**kwargs)
            self._is_instrumented_by_opentelemetry = False
            return result

        _LOG.warning("Attempting to uninstrument while already uninstrumented")

        return None


__all__ = ["BaseInstrumentor"]
