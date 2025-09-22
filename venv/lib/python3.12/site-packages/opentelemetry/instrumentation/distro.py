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
OpenTelemetry Base Distribution (Distro)
"""

from abc import ABC, abstractmethod
from logging import getLogger

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.util._importlib_metadata import EntryPoint

_LOG = getLogger(__name__)


class BaseDistro(ABC):
    """An ABC for distro"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kwargs)

        return cls._instance

    @abstractmethod
    def _configure(self, **kwargs):
        """Configure the distribution"""

    def configure(self, **kwargs):
        """Configure the distribution"""
        self._configure(**kwargs)

    def load_instrumentor(  # pylint: disable=no-self-use
        self, entry_point: EntryPoint, **kwargs
    ):
        """Takes an instrumentation entry point and activates it by instantiating
        and calling instrument() on it.
        This is called for each opentelemetry_instrumentor entry point by auto
        instrumentation.

        Distros can override this method to customize the behavior by
        inspecting each entry point and configuring them in special ways,
        passing additional arguments, load a replacement/fork instead,
        skip loading entirely, etc.
        """
        instrumentor: BaseInstrumentor = entry_point.load()
        instrumentor().instrument(**kwargs)


class DefaultDistro(BaseDistro):
    def _configure(self, **kwargs):
        pass


__all__ = ["BaseDistro", "DefaultDistro"]
