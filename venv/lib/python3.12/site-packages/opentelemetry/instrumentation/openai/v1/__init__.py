from typing import Collection

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import get_tracer

from opentelemetry.metrics import get_meter
from opentelemetry.semconv._incubating.metrics import gen_ai_metrics as GenAIMetrics

from wrapt import wrap_function_wrapper

from opentelemetry.instrumentation.openai.shared.chat_wrappers import (
    chat_wrapper,
    achat_wrapper,
)
from opentelemetry.instrumentation.openai.shared.completion_wrappers import (
    completion_wrapper,
    acompletion_wrapper,
)
from opentelemetry.instrumentation.openai.shared.embeddings_wrappers import (
    embeddings_wrapper,
    aembeddings_wrapper,
)
from opentelemetry.instrumentation.openai.shared.image_gen_wrappers import (
    image_gen_metrics_wrapper,
)
from opentelemetry.instrumentation.openai.v1.assistant_wrappers import (
    assistants_create_wrapper,
    runs_create_wrapper,
    runs_retrieve_wrapper,
    runs_create_and_stream_wrapper,
    messages_list_wrapper,
)

from opentelemetry.instrumentation.openai.utils import is_metrics_enabled
from opentelemetry.instrumentation.openai.version import __version__

from opentelemetry.semconv_ai import Meters

_instruments = ("openai >= 1.0.0",)


class OpenAIV1Instrumentor(BaseInstrumentor):
    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)

        # meter and counters are inited here
        meter_provider = kwargs.get("meter_provider")
        meter = get_meter(__name__, __version__, meter_provider)

        if is_metrics_enabled():
            tokens_histogram = meter.create_histogram(
                name=Meters.LLM_TOKEN_USAGE,
                unit="token",
                description="Measures number of input and output tokens used",
            )

            chat_choice_counter = meter.create_counter(
                name=Meters.LLM_GENERATION_CHOICES,
                unit="choice",
                description="Number of choices returned by chat completions call",
            )

            duration_histogram = meter.create_histogram(
                name=Meters.LLM_OPERATION_DURATION,
                unit="s",
                description="GenAI operation duration",
            )

            chat_exception_counter = meter.create_counter(
                name=Meters.LLM_COMPLETIONS_EXCEPTIONS,
                unit="time",
                description="Number of exceptions occurred during chat completions",
            )

            streaming_time_to_first_token = meter.create_histogram(
                name=GenAIMetrics.GEN_AI_SERVER_TIME_TO_FIRST_TOKEN,
                unit="s",
                description="Time to first token in streaming chat completions",
            )
            streaming_time_to_generate = meter.create_histogram(
                name=Meters.LLM_STREAMING_TIME_TO_GENERATE,
                unit="s",
                description="Time between first token and completion in streaming chat completions",
            )
        else:
            (
                tokens_histogram,
                chat_choice_counter,
                duration_histogram,
                chat_exception_counter,
                streaming_time_to_first_token,
                streaming_time_to_generate,
            ) = (None, None, None, None, None, None)

        wrap_function_wrapper(
            "openai.resources.chat.completions",
            "Completions.create",
            chat_wrapper(
                tracer,
                tokens_histogram,
                chat_choice_counter,
                duration_histogram,
                chat_exception_counter,
                streaming_time_to_first_token,
                streaming_time_to_generate,
            ),
        )

        wrap_function_wrapper(
            "openai.resources.completions",
            "Completions.create",
            completion_wrapper(tracer),
        )

        if is_metrics_enabled():
            embeddings_vector_size_counter = meter.create_counter(
                name=Meters.LLM_EMBEDDINGS_VECTOR_SIZE,
                unit="element",
                description="he size of returned vector",
            )
            embeddings_exception_counter = meter.create_counter(
                name=Meters.LLM_EMBEDDINGS_EXCEPTIONS,
                unit="time",
                description="Number of exceptions occurred during embeddings operation",
            )
        else:
            (
                tokens_histogram,
                embeddings_vector_size_counter,
                embeddings_exception_counter,
            ) = (None, None, None)

        wrap_function_wrapper(
            "openai.resources.embeddings",
            "Embeddings.create",
            embeddings_wrapper(
                tracer,
                tokens_histogram,
                embeddings_vector_size_counter,
                duration_histogram,
                embeddings_exception_counter,
            ),
        )

        wrap_function_wrapper(
            "openai.resources.chat.completions",
            "AsyncCompletions.create",
            achat_wrapper(
                tracer,
                tokens_histogram,
                chat_choice_counter,
                duration_histogram,
                chat_exception_counter,
                streaming_time_to_first_token,
                streaming_time_to_generate,
            ),
        )
        wrap_function_wrapper(
            "openai.resources.completions",
            "AsyncCompletions.create",
            acompletion_wrapper(tracer),
        )
        wrap_function_wrapper(
            "openai.resources.embeddings",
            "AsyncEmbeddings.create",
            aembeddings_wrapper(
                tracer,
                tokens_histogram,
                embeddings_vector_size_counter,
                duration_histogram,
                embeddings_exception_counter,
            ),
        )

        if is_metrics_enabled():
            image_gen_exception_counter = meter.create_counter(
                name=Meters.LLM_IMAGE_GENERATIONS_EXCEPTIONS,
                unit="time",
                description="Number of exceptions occurred during image generations operation",
            )
        else:
            image_gen_exception_counter = None

        wrap_function_wrapper(
            "openai.resources.images",
            "Images.generate",
            image_gen_metrics_wrapper(duration_histogram, image_gen_exception_counter),
        )

        # Beta APIs may not be available consistently in all versions
        try:
            wrap_function_wrapper(
                "openai.resources.beta.assistants",
                "Assistants.create",
                assistants_create_wrapper(tracer),
            )
            wrap_function_wrapper(
                "openai.resources.beta.chat.completions",
                "Completions.parse",
                chat_wrapper(
                    tracer,
                    tokens_histogram,
                    chat_choice_counter,
                    duration_histogram,
                    chat_exception_counter,
                    streaming_time_to_first_token,
                    streaming_time_to_generate,
                ),
            )
            wrap_function_wrapper(
                "openai.resources.beta.chat.completions",
                "AsyncCompletions.parse",
                achat_wrapper(
                    tracer,
                    tokens_histogram,
                    chat_choice_counter,
                    duration_histogram,
                    chat_exception_counter,
                    streaming_time_to_first_token,
                    streaming_time_to_generate,
                ),
            )
            wrap_function_wrapper(
                "openai.resources.beta.threads.runs",
                "Runs.create",
                runs_create_wrapper(tracer),
            )
            wrap_function_wrapper(
                "openai.resources.beta.threads.runs",
                "Runs.retrieve",
                runs_retrieve_wrapper(tracer),
            )
            wrap_function_wrapper(
                "openai.resources.beta.threads.runs",
                "Runs.create_and_stream",
                runs_create_and_stream_wrapper(tracer),
            )
            wrap_function_wrapper(
                "openai.resources.beta.threads.messages",
                "Messages.list",
                messages_list_wrapper(tracer),
            )
        except (AttributeError, ModuleNotFoundError):
            pass

    def _uninstrument(self, **kwargs):
        pass
