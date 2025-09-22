"""OpenTelemetry LlamaIndex instrumentation"""

import logging
from importlib.metadata import version as import_version
from typing import Collection

from opentelemetry.instrumentation.llamaindex.config import Config
from opentelemetry.trace import get_tracer

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor

from opentelemetry.instrumentation.llamaindex.base_agent_instrumentor import (
    BaseAgentInstrumentor,
)
from opentelemetry.instrumentation.llamaindex.retriever_query_engine_instrumentor import (
    RetrieverQueryEngineInstrumentor,
)
from opentelemetry.instrumentation.llamaindex.base_retriever_instrumentor import (
    BaseRetrieverInstrumentor,
)
from opentelemetry.instrumentation.llamaindex.base_synthesizer_instrumentor import (
    BaseSynthesizerInstrumentor,
)
from opentelemetry.instrumentation.llamaindex.base_tool_instrumentor import (
    BaseToolInstrumentor,
)
from opentelemetry.instrumentation.llamaindex.base_embedding_instrumentor import (
    BaseEmbeddingInstrumentor,
)
from opentelemetry.instrumentation.llamaindex.custom_llm_instrumentor import (
    CustomLLMInstrumentor,
)
from opentelemetry.instrumentation.llamaindex.query_pipeline_instrumentor import (
    QueryPipelineInstrumentor,
)
from opentelemetry.instrumentation.llamaindex.version import __version__
from opentelemetry.instrumentation.llamaindex.dispatcher_wrapper import instrument_with_dispatcher

logger = logging.getLogger(__name__)

_core_instruments = ("llama-index-core >= 0.7.0", )
_full_instruments = ("llama-index >= 0.7.0",)


class LlamaIndexInstrumentor(BaseInstrumentor):
    """An instrumentor for both: core and legacy LlamaIndex SDK."""

    def __init__(self, exception_logger=None):
        self.legacy = LlamaIndexInstrumentorFull(exception_logger)
        self.core = LlamaIndexInstrumentorCore(exception_logger)

    def instrumentation_dependencies(self) -> Collection[str]:
        return ()

    def _instrument(self, **kwargs):
        # Try to use the legacy entry point for instrumentation
        if self.legacy._check_dependency_conflicts() is None:
            self.legacy.instrument(**kwargs)
        if not self.legacy._is_instrumented_by_opentelemetry:
            # it didn't work -> try the new package
            if self.core._check_dependency_conflicts() is None:
                self.core.instrument(**kwargs)

    def _uninstrument(self, **kwargs):
        self.legacy.uninstrument(**kwargs)
        self.core.uninstrument(**kwargs)

    @staticmethod
    def apply_instrumentation(name, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)

        if import_version(name) >= "0.10.20":
            instrument_with_dispatcher(tracer)
        else:
            RetrieverQueryEngineInstrumentor(tracer).instrument()
            BaseRetrieverInstrumentor(tracer).instrument()
            BaseSynthesizerInstrumentor(tracer).instrument()
            BaseEmbeddingInstrumentor(tracer).instrument()
            CustomLLMInstrumentor(tracer).instrument()
            QueryPipelineInstrumentor(tracer).instrument()
            BaseAgentInstrumentor(tracer).instrument()
            BaseToolInstrumentor(tracer).instrument()


class LlamaIndexInstrumentorCore(BaseInstrumentor):
    """An instrumentor for core LlamaIndex SDK."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _core_instruments

    def _instrument(self, **kwargs):
        LlamaIndexInstrumentor.apply_instrumentation("llama-index-core", **kwargs)

    def _uninstrument(self, **kwargs):
        pass


class LlamaIndexInstrumentorFull(BaseInstrumentor):
    """An instrumentor for legacy LlamaIndex SDK."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _full_instruments

    def _instrument(self, **kwargs):
        LlamaIndexInstrumentor.apply_instrumentation("llama-index", **kwargs)

    def _uninstrument(self, **kwargs):
        pass
