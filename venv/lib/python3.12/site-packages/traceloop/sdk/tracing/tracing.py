import atexit
import logging
import os


from colorama import Fore
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor, ReadableSpan
from opentelemetry.sdk.trace.sampling import Sampler
from opentelemetry.propagators.textmap import TextMapPropagator
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SimpleSpanProcessor,
    BatchSpanProcessor,
)
from opentelemetry.trace import get_tracer_provider, ProxyTracerProvider
from opentelemetry.context import get_value, attach, set_value
from opentelemetry.instrumentation.threading import ThreadingInstrumentor

from opentelemetry.semconv_ai import SpanAttributes
from traceloop.sdk import Telemetry
from traceloop.sdk.images.image_uploader import ImageUploader
from traceloop.sdk.instruments import Instruments
from traceloop.sdk.tracing.content_allow_list import ContentAllowList
from traceloop.sdk.utils import is_notebook
from traceloop.sdk.utils.package_check import is_package_installed
from typing import Callable, Dict, Optional, Set


TRACER_NAME = "traceloop.tracer"
EXCLUDED_URLS = """
    iam.cloud.ibm.com,
    dataplatform.cloud.ibm.com,
    ml.cloud.ibm.com,
    api.openai.com,
    openai.azure.com,
    api.anthropic.com,
    api.cohere.ai,
    pinecone.io,
    traceloop.com,
    posthog.com,
    sentry.io,
    bedrock-runtime,
    sagemaker-runtime,
    googleapis.com,
    githubusercontent.com,
    openaipublic.blob.core.windows.net"""


class TracerWrapper(object):
    resource_attributes: dict = {}
    enable_content_tracing: bool = True
    endpoint: str = None
    headers: Dict[str, str] = {}
    __tracer_provider: TracerProvider = None
    __image_uploader: ImageUploader = None
    __disabled: bool = False

    def __new__(
        cls,
        disable_batch=False,
        processor: SpanProcessor = None,
        propagator: TextMapPropagator = None,
        exporter: SpanExporter = None,
        sampler: Optional[Sampler] = None,
        should_enrich_metrics: bool = True,
        instruments: Optional[Set[Instruments]] = None,
        block_instruments: Optional[Set[Instruments]] = None,
        image_uploader: ImageUploader = None,
        span_postprocess_callback: Optional[Callable[[ReadableSpan], None]] = None,
    ) -> "TracerWrapper":
        if not hasattr(cls, "instance"):
            obj = cls.instance = super(TracerWrapper, cls).__new__(cls)
            if not TracerWrapper.endpoint:
                return obj

            obj.__image_uploader = image_uploader
            obj.__resource = Resource(attributes=TracerWrapper.resource_attributes)
            obj.__tracer_provider = init_tracer_provider(resource=obj.__resource, sampler=sampler)
            if processor:
                Telemetry().capture("tracer:init", {"processor": "custom"})
                obj.__spans_processor: SpanProcessor = processor
                obj.__spans_processor_original_on_start = processor.on_start
            else:
                if exporter:
                    Telemetry().capture(
                        "tracer:init",
                        {
                            "exporter": "custom",
                            "processor": "simple" if disable_batch else "batch",
                        },
                    )
                else:
                    Telemetry().capture(
                        "tracer:init",
                        {
                            "exporter": TracerWrapper.endpoint,
                            "processor": "simple" if disable_batch else "batch",
                        },
                    )

                obj.__spans_exporter: SpanExporter = (
                    exporter
                    if exporter
                    else init_spans_exporter(
                        TracerWrapper.endpoint, TracerWrapper.headers
                    )
                )
                if disable_batch or is_notebook():
                    obj.__spans_processor: SpanProcessor = SimpleSpanProcessor(
                        obj.__spans_exporter
                    )
                else:
                    obj.__spans_processor: SpanProcessor = BatchSpanProcessor(
                        obj.__spans_exporter
                    )
                obj.__spans_processor_original_on_start = None
                if span_postprocess_callback:
                    # Create a wrapper that calls both the custom and original methods
                    original_on_end = obj.__spans_processor.on_end

                    def wrapped_on_end(span):
                        # Call the custom on_end first
                        span_postprocess_callback(span)
                        # Then call the original to ensure normal processing
                        original_on_end(span)
                    obj.__spans_processor.on_end = wrapped_on_end

            obj.__spans_processor.on_start = obj._span_processor_on_start
            obj.__tracer_provider.add_span_processor(obj.__spans_processor)

            if propagator:
                set_global_textmap(propagator)

            # this makes sure otel context is propagated so we always want it
            ThreadingInstrumentor().instrument()

            init_instrumentations(
                should_enrich_metrics,
                image_uploader.aupload_base64_image,
                instruments,
                block_instruments,
            )

            obj.__content_allow_list = ContentAllowList()

            # Force flushes for debug environments (e.g. local development)
            atexit.register(obj.exit_handler)

        return cls.instance

    def exit_handler(self):
        self.flush()

    def _span_processor_on_start(self, span, parent_context):
        workflow_name = get_value("workflow_name")
        if workflow_name is not None:
            span.set_attribute(SpanAttributes.TRACELOOP_WORKFLOW_NAME, workflow_name)

        entity_path = get_value("entity_path")
        if entity_path is not None:
            span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_PATH, entity_path)

        association_properties = get_value("association_properties")
        if association_properties is not None:
            _set_association_properties_attributes(span, association_properties)

            if not self.enable_content_tracing:
                if self.__content_allow_list.is_allowed(association_properties):
                    attach(set_value("override_enable_content_tracing", True))
                else:
                    attach(set_value("override_enable_content_tracing", False))

        if is_llm_span(span):
            managed_prompt = get_value("managed_prompt")
            if managed_prompt is not None:
                span.set_attribute(
                    SpanAttributes.TRACELOOP_PROMPT_MANAGED, managed_prompt
                )

            prompt_key = get_value("prompt_key")
            if prompt_key is not None:
                span.set_attribute(SpanAttributes.TRACELOOP_PROMPT_KEY, prompt_key)

            prompt_version = get_value("prompt_version")
            if prompt_version is not None:
                span.set_attribute(
                    SpanAttributes.TRACELOOP_PROMPT_VERSION, prompt_version
                )

            prompt_version_name = get_value("prompt_version_name")
            if prompt_version_name is not None:
                span.set_attribute(
                    SpanAttributes.TRACELOOP_PROMPT_VERSION_NAME, prompt_version_name
                )

            prompt_version_hash = get_value("prompt_version_hash")
            if prompt_version_hash is not None:
                span.set_attribute(
                    SpanAttributes.TRACELOOP_PROMPT_VERSION_HASH, prompt_version_hash
                )

            prompt_template = get_value("prompt_template")
            if prompt_template is not None:
                span.set_attribute(
                    SpanAttributes.TRACELOOP_PROMPT_TEMPLATE, prompt_template
                )

            prompt_template_variables = get_value("prompt_template_variables")
            if prompt_template_variables is not None:
                for key, value in prompt_template_variables.items():
                    span.set_attribute(
                        f"{SpanAttributes.TRACELOOP_PROMPT_TEMPLATE_VARIABLES}.{key}",
                        value,
                    )

        # Call original on_start method if it exists in custom processor
        if self.__spans_processor_original_on_start:
            self.__spans_processor_original_on_start(span, parent_context)

    @staticmethod
    def set_static_params(
        resource_attributes: dict,
        enable_content_tracing: bool,
        endpoint: str,
        headers: Dict[str, str],
    ) -> None:
        TracerWrapper.resource_attributes = resource_attributes
        TracerWrapper.enable_content_tracing = enable_content_tracing
        TracerWrapper.endpoint = endpoint
        TracerWrapper.headers = headers

    @classmethod
    def verify_initialized(cls) -> bool:
        if cls.__disabled:
            return False

        if hasattr(cls, "instance"):
            return True

        if (os.getenv("TRACELOOP_SUPPRESS_WARNINGS") or "false").lower() == "true":
            return False

        print(
            Fore.RED
            + "Warning: Traceloop not initialized, make sure you call Traceloop.init()"
        )
        print(Fore.RESET)
        return False

    @classmethod
    def set_disabled(cls, disabled: bool) -> None:
        cls.__disabled = disabled

    def flush(self):
        self.__spans_processor.force_flush()

    def get_tracer(self):
        return self.__tracer_provider.get_tracer(TRACER_NAME)


def set_association_properties(properties: dict) -> None:
    attach(set_value("association_properties", properties))

    # Attach association properties to the current span, if it's a workflow or a task
    span = trace.get_current_span()
    if get_value("workflow_name") is not None or get_value("entity_name") is not None:
        _set_association_properties_attributes(span, properties)


def _set_association_properties_attributes(span, properties: dict) -> None:
    for key, value in properties.items():
        span.set_attribute(
            f"{SpanAttributes.TRACELOOP_ASSOCIATION_PROPERTIES}.{key}", value
        )


def set_workflow_name(workflow_name: str) -> None:
    attach(set_value("workflow_name", workflow_name))


def set_entity_path(entity_path: str) -> None:
    attach(set_value("entity_path", entity_path))


def get_chained_entity_path(entity_name: str) -> str:
    parent = get_value("entity_path")
    if parent is None:
        return entity_name
    else:
        return f"{parent}.{entity_name}"


def set_managed_prompt_tracing_context(
    key: str,
    version: int,
    version_name: str,
    version_hash: str,
    template_variables: dict,
) -> None:
    attach(set_value("managed_prompt", True))
    attach(set_value("prompt_key", key))
    attach(set_value("prompt_version", version))
    attach(set_value("prompt_version_name", version_name))
    attach(set_value("prompt_version_hash", version_hash))
    attach(set_value("prompt_template_variables", template_variables))


def set_external_prompt_tracing_context(
    template: str, variables: dict, version: int
) -> None:
    attach(set_value("managed_prompt", False))
    attach(set_value("prompt_version", version))
    attach(set_value("prompt_template", template))
    attach(set_value("prompt_template_variables", variables))


def is_llm_span(span) -> bool:
    return span.attributes.get(SpanAttributes.LLM_REQUEST_TYPE) is not None


def init_spans_exporter(api_endpoint: str, headers: Dict[str, str]) -> SpanExporter:
    if "http" in api_endpoint.lower() or "https" in api_endpoint.lower():
        return HTTPExporter(endpoint=f"{api_endpoint}/v1/traces", headers=headers)
    else:
        return GRPCExporter(endpoint=f"{api_endpoint}", headers=headers)


def init_tracer_provider(resource: Resource, sampler: Optional[Sampler] = None) -> TracerProvider:
    provider: TracerProvider = None
    default_provider: TracerProvider = get_tracer_provider()

    if isinstance(default_provider, ProxyTracerProvider):
        if sampler is not None:
            provider = TracerProvider(resource=resource, sampler=sampler)
        else:
            provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
    elif not hasattr(default_provider, "add_span_processor"):
        logging.error(
            "Cannot add span processor to the default provider since it doesn't support it"
        )
        return
    else:
        provider = default_provider

    return provider


def init_instrumentations(
    should_enrich_metrics: bool,
    base64_image_uploader: Callable[[str, str, str], str],
    instruments: Optional[Set[Instruments]] = None,
    block_instruments: Optional[Set[Instruments]] = None,
):
    block_instruments = block_instruments or set()
    instruments = instruments or set(
        Instruments
    )  # Use all instruments if none specified

    # Remove any instruments that were explicitly blocked
    instruments = instruments - block_instruments

    instrument_set = False
    for instrument in instruments:
        if instrument == Instruments.ALEPHALPHA:
            if init_alephalpha_instrumentor():
                instrument_set = True
        elif instrument == Instruments.ANTHROPIC:
            if init_anthropic_instrumentor(
                should_enrich_metrics, base64_image_uploader
            ):
                instrument_set = True
        elif instrument == Instruments.BEDROCK:
            if init_bedrock_instrumentor(should_enrich_metrics):
                instrument_set = True
        elif instrument == Instruments.CHROMA:
            if init_chroma_instrumentor():
                instrument_set = True
        elif instrument == Instruments.COHERE:
            if init_cohere_instrumentor():
                instrument_set = True
        elif instrument == Instruments.CREW:
            if init_crewai_instrumentor():
                instrument_set = True
        elif instrument == Instruments.GOOGLE_GENERATIVEAI:
            if init_google_generativeai_instrumentor():
                instrument_set = True
        elif instrument == Instruments.GROQ:
            if init_groq_instrumentor():
                instrument_set = True
        elif instrument == Instruments.HAYSTACK:
            if init_haystack_instrumentor():
                instrument_set = True
        elif instrument == Instruments.LANCEDB:
            if init_lancedb_instrumentor():
                instrument_set = True
        elif instrument == Instruments.LANGCHAIN:
            if init_langchain_instrumentor():
                instrument_set = True
        elif instrument == Instruments.LLAMA_INDEX:
            if init_llama_index_instrumentor():
                instrument_set = True
        elif instrument == Instruments.MARQO:
            if init_marqo_instrumentor():
                instrument_set = True
        elif instrument == Instruments.MCP:
            if init_mcp_instrumentor():
                instrument_set = True
        elif instrument == Instruments.MILVUS:
            if init_milvus_instrumentor():
                instrument_set = True
        elif instrument == Instruments.MISTRAL:
            if init_mistralai_instrumentor():
                instrument_set = True
        elif instrument == Instruments.OLLAMA:
            if init_ollama_instrumentor():
                instrument_set = True
        elif instrument == Instruments.OPENAI:
            if init_openai_instrumentor(should_enrich_metrics, base64_image_uploader):
                instrument_set = True
        elif instrument == Instruments.PINECONE:
            if init_pinecone_instrumentor():
                instrument_set = True
        elif instrument == Instruments.PYMYSQL:
            if init_pymysql_instrumentor():
                instrument_set = True
        elif instrument == Instruments.QDRANT:
            if init_qdrant_instrumentor():
                instrument_set = True
        elif instrument == Instruments.REDIS:
            if init_redis_instrumentor():
                instrument_set = True
        elif instrument == Instruments.REPLICATE:
            if init_replicate_instrumentor():
                instrument_set = True
        elif instrument == Instruments.REQUESTS:
            if init_requests_instrumentor():
                instrument_set = True
        elif instrument == Instruments.SAGEMAKER:
            if init_sagemaker_instrumentor(should_enrich_metrics):
                instrument_set = True
        elif instrument == Instruments.TOGETHER:
            if init_together_instrumentor():
                instrument_set = True
        elif instrument == Instruments.TRANSFORMERS:
            if init_transformers_instrumentor():
                instrument_set = True
        elif instrument == Instruments.URLLIB3:
            if init_urllib3_instrumentor():
                instrument_set = True
        elif instrument == Instruments.VERTEXAI:
            if init_vertexai_instrumentor():
                instrument_set = True
        elif instrument == Instruments.WATSONX:
            if init_watsonx_instrumentor():
                instrument_set = True
        elif instrument == Instruments.WEAVIATE:
            if init_weaviate_instrumentor():
                instrument_set = True
        else:
            print(Fore.RED + f"Warning: {instrument} instrumentation does not exist.")
            print(
                "Usage:\n"
                "from traceloop.sdk.instruments import Instruments\n"
                "Traceloop.init(app_name='...', instruments=set([Instruments.OPENAI]))"
            )
            print(Fore.RESET)

    if not instrument_set:
        print(
            Fore.RED
            + "Warning: No valid instruments set. "
            + "Ensure the instrumented libraries are installed, specify valid instruments, "
            + "or remove 'instruments' argument to use all instruments."
        )
        print(Fore.RESET)

    return instrument_set


def init_openai_instrumentor(
    should_enrich_metrics: bool, base64_image_uploader: Callable[[str, str, str], str]
):
    try:
        if is_package_installed("openai"):
            Telemetry().capture("instrumentation:openai:init")
            from opentelemetry.instrumentation.openai import OpenAIInstrumentor

            instrumentor = OpenAIInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
                enrich_assistant=should_enrich_metrics,
                enrich_token_usage=should_enrich_metrics,
                get_common_metrics_attributes=metrics_common_attributes,
                upload_base64_image=base64_image_uploader,
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True

    except Exception as e:
        logging.error(f"Error initializing OpenAI instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_anthropic_instrumentor(
    should_enrich_metrics: bool, base64_image_uploader: Callable[[str, str, str], str]
):
    try:
        if is_package_installed("anthropic"):
            Telemetry().capture("instrumentation:anthropic:init")
            from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor

            instrumentor = AnthropicInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
                enrich_token_usage=should_enrich_metrics,
                get_common_metrics_attributes=metrics_common_attributes,
                upload_base64_image=base64_image_uploader,
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Anthropic instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_cohere_instrumentor():
    try:
        if is_package_installed("cohere"):
            Telemetry().capture("instrumentation:cohere:init")
            from opentelemetry.instrumentation.cohere import CohereInstrumentor

            instrumentor = CohereInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Cohere instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_pinecone_instrumentor():
    try:
        if is_package_installed("pinecone"):
            Telemetry().capture("instrumentation:pinecone:init")
            from opentelemetry.instrumentation.pinecone import PineconeInstrumentor

            instrumentor = PineconeInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Pinecone instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_qdrant_instrumentor():
    try:
        if is_package_installed("qdrant_client"):
            Telemetry().capture("instrumentation:qdrant:init")
            from opentelemetry.instrumentation.qdrant import QdrantInstrumentor

            instrumentor = QdrantInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Qdrant instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_chroma_instrumentor():
    try:
        if is_package_installed("chromadb"):
            Telemetry().capture("instrumentation:chromadb:init")
            from opentelemetry.instrumentation.chromadb import ChromaInstrumentor

            instrumentor = ChromaInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Chroma instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_google_generativeai_instrumentor():
    try:
        if is_package_installed("google-generativeai") or is_package_installed("google-genai"):
            Telemetry().capture("instrumentation:gemini:init")
            from opentelemetry.instrumentation.google_generativeai import (
                GoogleGenerativeAiInstrumentor,
            )

            instrumentor = GoogleGenerativeAiInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Gemini instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_haystack_instrumentor():
    try:
        if is_package_installed("haystack"):
            Telemetry().capture("instrumentation:haystack:init")
            from opentelemetry.instrumentation.haystack import HaystackInstrumentor

            instrumentor = HaystackInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Haystack instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_langchain_instrumentor():
    try:
        if is_package_installed("langchain") or is_package_installed("langgraph"):
            Telemetry().capture("instrumentation:langchain:init")
            from opentelemetry.instrumentation.langchain import LangchainInstrumentor

            instrumentor = LangchainInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing LangChain instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_mistralai_instrumentor():
    try:
        if is_package_installed("mistralai"):
            Telemetry().capture("instrumentation:mistralai:init")
            from opentelemetry.instrumentation.mistralai import MistralAiInstrumentor

            instrumentor = MistralAiInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing MistralAI instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_ollama_instrumentor():
    try:
        if is_package_installed("ollama"):
            Telemetry().capture("instrumentation:ollama:init")
            from opentelemetry.instrumentation.ollama import OllamaInstrumentor

            instrumentor = OllamaInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Ollama instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_transformers_instrumentor():
    try:
        if is_package_installed("transformers"):
            Telemetry().capture("instrumentation:transformers:init")
            from opentelemetry.instrumentation.transformers import (
                TransformersInstrumentor,
            )

            instrumentor = TransformersInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Transformers instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_together_instrumentor():
    try:
        if is_package_installed("together"):
            Telemetry().capture("instrumentation:together:init")
            from opentelemetry.instrumentation.together import TogetherAiInstrumentor

            instrumentor = TogetherAiInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing TogetherAI instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_llama_index_instrumentor():
    try:
        if is_package_installed("llama-index") or is_package_installed("llama_index"):
            Telemetry().capture("instrumentation:llamaindex:init")
            from opentelemetry.instrumentation.llamaindex import LlamaIndexInstrumentor

            instrumentor = LlamaIndexInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing LlamaIndex instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_milvus_instrumentor():
    try:
        if is_package_installed("pymilvus"):
            Telemetry().capture("instrumentation:milvus:init")
            from opentelemetry.instrumentation.milvus import MilvusInstrumentor

            instrumentor = MilvusInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Milvus instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_requests_instrumentor():
    try:
        if is_package_installed("requests"):
            from opentelemetry.instrumentation.requests import RequestsInstrumentor

            instrumentor = RequestsInstrumentor()
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument(excluded_urls=EXCLUDED_URLS)
            return True
    except Exception as e:
        logging.error(f"Error initializing Requests instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_urllib3_instrumentor():
    try:
        if is_package_installed("urllib3"):
            from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

            instrumentor = URLLib3Instrumentor()
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument(excluded_urls=EXCLUDED_URLS)
            return True
    except Exception as e:
        logging.error(f"Error initializing urllib3 instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_pymysql_instrumentor():
    try:
        if is_package_installed("sqlalchemy"):
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

            instrumentor = SQLAlchemyInstrumentor()
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing SQLAlchemy instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_bedrock_instrumentor(should_enrich_metrics: bool):
    try:
        if is_package_installed("boto3"):
            from opentelemetry.instrumentation.bedrock import BedrockInstrumentor

            instrumentor = BedrockInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
                enrich_token_usage=should_enrich_metrics,
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Bedrock instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_sagemaker_instrumentor(should_enrich_metrics: bool):
    try:
        if is_package_installed("boto3"):
            from opentelemetry.instrumentation.sagemaker import SageMakerInstrumentor

            instrumentor = SageMakerInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
                enrich_token_usage=should_enrich_metrics,
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing SageMaker instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_replicate_instrumentor():
    try:
        if is_package_installed("replicate"):
            Telemetry().capture("instrumentation:replicate:init")
            from opentelemetry.instrumentation.replicate import ReplicateInstrumentor

            instrumentor = ReplicateInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Replicate instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_vertexai_instrumentor():
    try:
        if is_package_installed("google-cloud-aiplatform"):
            Telemetry().capture("instrumentation:vertexai:init")
            from opentelemetry.instrumentation.vertexai import VertexAIInstrumentor

            instrumentor = VertexAIInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.warning(f"Error initializing Vertex AI instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_watsonx_instrumentor():
    try:
        if is_package_installed("ibm-watsonx-ai") or is_package_installed(
            "ibm_watson_machine_learning"
        ):
            Telemetry().capture("instrumentation:watsonx:init")
            from opentelemetry.instrumentation.watsonx import WatsonxInstrumentor

            instrumentor = WatsonxInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.warning(f"Error initializing Watsonx instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_weaviate_instrumentor():
    try:
        if is_package_installed("weaviate"):
            Telemetry().capture("instrumentation:weaviate:init")
            from opentelemetry.instrumentation.weaviate import WeaviateInstrumentor

            instrumentor = WeaviateInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.warning(f"Error initializing Weaviate instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_alephalpha_instrumentor():
    try:
        if is_package_installed("aleph_alpha_client"):
            Telemetry().capture("instrumentation:alephalpha:init")
            from opentelemetry.instrumentation.alephalpha import AlephAlphaInstrumentor

            instrumentor = AlephAlphaInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Aleph Alpha instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_marqo_instrumentor():
    try:
        if is_package_installed("marqo"):
            Telemetry().capture("instrumentation:marqo:init")
            from opentelemetry.instrumentation.marqo import MarqoInstrumentor

            instrumentor = MarqoInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing marqo instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_lancedb_instrumentor():
    try:
        if is_package_installed("lancedb"):
            Telemetry().capture("instrumentation:lancedb:init")
            from opentelemetry.instrumentation.lancedb import LanceInstrumentor

            instrumentor = LanceInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing LanceDB instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_redis_instrumentor():
    try:
        if is_package_installed("redis"):
            from opentelemetry.instrumentation.redis import RedisInstrumentor

            instrumentor = RedisInstrumentor()
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument(excluded_urls=EXCLUDED_URLS)
            return True
    except Exception as e:
        logging.error(f"Error initializing redis instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_groq_instrumentor():
    try:
        if is_package_installed("groq"):
            Telemetry().capture("instrumentation:groq:init")
            from opentelemetry.instrumentation.groq import GroqInstrumentor

            instrumentor = GroqInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing Groq instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_crewai_instrumentor():
    try:
        if is_package_installed("crewai"):
            Telemetry().capture("instrumentation:crewai:init")
            from opentelemetry.instrumentation.crewai import CrewAIInstrumentor

            instrumentor = CrewAIInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing CrewAI instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def init_mcp_instrumentor():
    try:
        if is_package_installed("mcp"):
            Telemetry().capture("instrumentation:mcp:init")
            from opentelemetry.instrumentation.mcp import McpInstrumentor

            instrumentor = McpInstrumentor(
                exception_logger=lambda e: Telemetry().log_exception(e),
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument()
            return True
    except Exception as e:
        logging.error(f"Error initializing MCP instrumentor: {e}")
        Telemetry().log_exception(e)
    return False


def metrics_common_attributes():
    common_attributes = {}
    workflow_name = get_value("workflow_name")
    if workflow_name is not None:
        common_attributes[SpanAttributes.TRACELOOP_WORKFLOW_NAME] = workflow_name

    entity_name = get_value("entity_name")
    if entity_name is not None:
        common_attributes[SpanAttributes.TRACELOOP_ENTITY_NAME] = entity_name

    association_properties = get_value("association_properties")
    if association_properties is not None:
        for key, value in association_properties.items():
            common_attributes[
                f"{SpanAttributes.TRACELOOP_ASSOCIATION_PROPERTIES}.{key}"
            ] = value

    return common_attributes
