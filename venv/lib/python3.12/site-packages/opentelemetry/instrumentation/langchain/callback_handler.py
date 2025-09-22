import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks import (
    BaseCallbackHandler,
)
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_RESPONSE_ID,
)
from opentelemetry.semconv_ai import (
    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY,
    LLMRequestTypeValues,
    SpanAttributes,
    TraceloopSpanKindValues,
)
from opentelemetry.context.context import Context
from opentelemetry.trace import SpanKind, set_span_in_context, Tracer
from opentelemetry.trace.span import Span
from opentelemetry.util.types import AttributeValue

from opentelemetry import context as context_api
from opentelemetry.instrumentation.langchain.utils import (
    CallbackFilteredJSONEncoder,
    dont_throw,
    should_send_prompts,
)
from opentelemetry.metrics import Histogram
from opentelemetry.trace.status import Status, StatusCode


@dataclass
class SpanHolder:
    span: Span
    token: Any
    context: Context
    children: list[UUID]
    workflow_name: str
    entity_name: str
    entity_path: str
    start_time: float = field(default_factory=time.time)
    request_model: Optional[str] = None


def _message_type_to_role(message_type: str) -> str:
    if message_type == "human":
        return "user"
    elif message_type == "system":
        return "system"
    elif message_type == "ai":
        return "assistant"
    elif message_type == "tool":
        return "tool"
    else:
        return "unknown"


def _set_span_attribute(span: Span, name: str, value: AttributeValue):
    if value is not None and value != "":
        span.set_attribute(name, value)


def _set_request_params(span, kwargs, span_holder: SpanHolder):
    for model_tag in ("model", "model_id", "model_name"):
        if (model := kwargs.get(model_tag)) is not None:
            span_holder.request_model = model
            break
        elif (
            model := (kwargs.get("invocation_params") or {}).get(model_tag)
        ) is not None:
            span_holder.request_model = model
            break
    else:
        model = "unknown"

    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, model)
    # response is not available for LLM requests (as opposed to chat)
    _set_span_attribute(span, SpanAttributes.LLM_RESPONSE_MODEL, model)

    if "invocation_params" in kwargs:
        params = (
            kwargs["invocation_params"].get("params") or kwargs["invocation_params"]
        )
    else:
        params = kwargs

    _set_span_attribute(
        span,
        SpanAttributes.LLM_REQUEST_MAX_TOKENS,
        params.get("max_tokens") or params.get("max_new_tokens"),
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, params.get("temperature")
    )
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TOP_P, params.get("top_p"))

    tools = kwargs.get("invocation_params", {}).get("tools", [])
    for i, tool in enumerate(tools):
        tool_function = tool.get("function", tool)
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_REQUEST_FUNCTIONS}.{i}.name",
            tool_function.get("name"),
        )
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_REQUEST_FUNCTIONS}.{i}.description",
            tool_function.get("description"),
        )
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_REQUEST_FUNCTIONS}.{i}.parameters",
            json.dumps(tool_function.get("parameters", tool.get("input_schema"))),
        )


def _set_llm_request(
    span: Span,
    serialized: dict[str, Any],
    prompts: list[str],
    kwargs: Any,
    span_holder: SpanHolder,
) -> None:
    _set_request_params(span, kwargs, span_holder)

    if should_send_prompts():
        for i, msg in enumerate(prompts):
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.{i}.role",
                "user",
            )
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.{i}.content",
                msg,
            )


def _set_chat_request(
    span: Span,
    serialized: dict[str, Any],
    messages: list[list[BaseMessage]],
    kwargs: Any,
    span_holder: SpanHolder,
) -> None:
    _set_request_params(span, kwargs, span_holder)

    if should_send_prompts():
        for i, function in enumerate(
            kwargs.get("invocation_params", {}).get("functions", [])
        ):
            prefix = f"{SpanAttributes.LLM_REQUEST_FUNCTIONS}.{i}"

            _set_span_attribute(span, f"{prefix}.name", function.get("name"))
            _set_span_attribute(
                span, f"{prefix}.description", function.get("description")
            )
            _set_span_attribute(
                span, f"{prefix}.parameters", json.dumps(function.get("parameters"))
            )

        i = 0
        for message in messages:
            for msg in message:
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_PROMPTS}.{i}.role",
                    _message_type_to_role(msg.type),
                )
                tool_calls = (
                    msg.tool_calls
                    if hasattr(msg, "tool_calls")
                    else msg.additional_kwargs.get("tool_calls")
                )

                if tool_calls:
                    _set_chat_tool_calls(span, f"{SpanAttributes.LLM_PROMPTS}.{i}", tool_calls)

                else:
                    content = (
                        msg.content
                        if isinstance(msg.content, str)
                        else json.dumps(msg.content, cls=CallbackFilteredJSONEncoder)
                    )
                    _set_span_attribute(
                        span,
                        f"{SpanAttributes.LLM_PROMPTS}.{i}.content",
                        content,
                    )

                if msg.type == "tool" and hasattr(msg, "tool_call_id"):
                    _set_span_attribute(
                        span,
                        f"{SpanAttributes.LLM_PROMPTS}.{i}.tool_call_id",
                        msg.tool_call_id,
                    )

                i += 1


def _set_chat_response(span: Span, response: LLMResult) -> None:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    cache_read_tokens = 0

    i = 0
    for generations in response.generations:
        for generation in generations:
            if (
                hasattr(generation, "message")
                and hasattr(generation.message, "usage_metadata")
                and generation.message.usage_metadata is not None
            ):
                input_tokens += (
                    generation.message.usage_metadata.get("input_tokens")
                    or generation.message.usage_metadata.get("prompt_tokens")
                    or 0
                )
                output_tokens += (
                    generation.message.usage_metadata.get("output_tokens")
                    or generation.message.usage_metadata.get("completion_tokens")
                    or 0
                )
                total_tokens = input_tokens + output_tokens

                if generation.message.usage_metadata.get("input_token_details"):
                    input_token_details = generation.message.usage_metadata.get("input_token_details", {})
                    cache_read_tokens += input_token_details.get("cache_read", 0)

            if should_send_prompts():
                prefix = f"{SpanAttributes.LLM_COMPLETIONS}.{i}"
                if hasattr(generation, "text") and generation.text != "":
                    _set_span_attribute(
                        span,
                        f"{prefix}.content",
                        generation.text,
                    )
                    _set_span_attribute(span, f"{prefix}.role", "assistant")
                else:
                    _set_span_attribute(
                        span,
                        f"{prefix}.role",
                        _message_type_to_role(generation.type),
                    )
                    if generation.message.content is str:
                        _set_span_attribute(
                            span,
                            f"{prefix}.content",
                            generation.message.content,
                        )
                    else:
                        _set_span_attribute(
                            span,
                            f"{prefix}.content",
                            json.dumps(
                                generation.message.content, cls=CallbackFilteredJSONEncoder
                            ),
                        )
                    if generation.generation_info.get("finish_reason"):
                        _set_span_attribute(
                            span,
                            f"{prefix}.finish_reason",
                            generation.generation_info.get("finish_reason"),
                        )

                    if generation.message.additional_kwargs.get("function_call"):
                        _set_span_attribute(
                            span,
                            f"{prefix}.tool_calls.0.name",
                            generation.message.additional_kwargs.get("function_call").get(
                                "name"
                            ),
                        )
                        _set_span_attribute(
                            span,
                            f"{prefix}.tool_calls.0.arguments",
                            generation.message.additional_kwargs.get("function_call").get(
                                "arguments"
                            ),
                        )

                if hasattr(generation, "message"):
                    tool_calls = (
                        generation.message.tool_calls
                        if hasattr(generation.message, "tool_calls")
                        else generation.message.additional_kwargs.get("tool_calls")
                    )
                    if tool_calls and isinstance(tool_calls, list):
                        _set_span_attribute(
                            span,
                            f"{prefix}.role",
                            "assistant",
                        )
                        _set_chat_tool_calls(span, prefix, tool_calls)
        i += 1

    if input_tokens > 0 or output_tokens > 0 or total_tokens > 0 or cache_read_tokens > 0:
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_PROMPT_TOKENS,
            input_tokens,
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_COMPLETION_TOKENS,
            output_tokens,
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_TOTAL_TOKENS,
            total_tokens,
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_CACHE_READ_INPUT_TOKENS,
            cache_read_tokens,
        )


def _set_chat_tool_calls(span: Span, prefix: str, tool_calls: list[dict[str, Any]]) -> None:
    for idx, tool_call in enumerate(tool_calls):
        tool_call_prefix = f"{prefix}.tool_calls.{idx}"
        tool_call_dict = dict(tool_call)
        tool_id = tool_call_dict.get("id")
        tool_name = tool_call_dict.get("name", tool_call_dict.get("function", {}).get("name"))
        tool_args = tool_call_dict.get("args", tool_call_dict.get("function", {}).get("arguments"))

        _set_span_attribute(
            span,
            f"{tool_call_prefix}.id", tool_id
        )
        _set_span_attribute(
            span,
            f"{tool_call_prefix}.name",
            tool_name,
        )
        _set_span_attribute(
            span,
            f"{tool_call_prefix}.arguments",
            json.dumps(tool_args, cls=CallbackFilteredJSONEncoder),
        )


def _sanitize_metadata_value(value: Any) -> Any:
    """Convert metadata values to OpenTelemetry-compatible types."""
    if value is None:
        return None
    if isinstance(value, (bool, str, bytes, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [str(_sanitize_metadata_value(v)) for v in value]
    # Convert other types to strings
    return str(value)


class TraceloopCallbackHandler(BaseCallbackHandler):
    def __init__(
        self, tracer: Tracer, duration_histogram: Histogram, token_histogram: Histogram
    ) -> None:
        super().__init__()
        self.tracer = tracer
        self.duration_histogram = duration_histogram
        self.token_histogram = token_histogram
        self.spans: dict[UUID, SpanHolder] = {}
        self.run_inline = True

    @staticmethod
    def _get_name_from_callback(
        serialized: dict[str, Any],
        _tags: Optional[list[str]] = None,
        _metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Get the name to be used for the span. Based on heuristic. Can be extended."""
        if serialized and "kwargs" in serialized and serialized["kwargs"].get("name"):
            return serialized["kwargs"]["name"]
        if kwargs.get("name"):
            return kwargs["name"]
        if serialized.get("name"):
            return serialized["name"]
        if "id" in serialized:
            return serialized["id"][-1]

        return "unknown"

    def _get_span(self, run_id: UUID) -> Span:
        return self.spans[run_id].span

    def _end_span(self, span: Span, run_id: UUID) -> None:
        for child_id in self.spans[run_id].children:
            child_span = self.spans[child_id].span
            if child_span.end_time is None:  # avoid warning on ended spans
                child_span.end()
        span.end()

    def _create_span(
        self,
        run_id: UUID,
        parent_run_id: Optional[UUID],
        span_name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        workflow_name: str = "",
        entity_name: str = "",
        entity_path: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Span:
        if metadata is not None:
            current_association_properties = (
                context_api.get_value("association_properties") or {}
            )
            # Sanitize metadata values to ensure they're compatible with OpenTelemetry
            sanitized_metadata = {
                k: _sanitize_metadata_value(v)
                for k, v in metadata.items()
                if v is not None
            }
            context_api.attach(
                context_api.set_value(
                    "association_properties",
                    {**current_association_properties, **sanitized_metadata},
                )
            )

        if parent_run_id is not None and parent_run_id in self.spans:
            span = self.tracer.start_span(
                span_name,
                context=set_span_in_context(self.spans[parent_run_id].span),
                kind=kind,
            )
        else:
            span = self.tracer.start_span(span_name, kind=kind)

        _set_span_attribute(span, SpanAttributes.TRACELOOP_WORKFLOW_NAME, workflow_name)
        _set_span_attribute(span, SpanAttributes.TRACELOOP_ENTITY_PATH, entity_path)

        token = context_api.attach(
            context_api.set_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY, True)
        )

        self.spans[run_id] = SpanHolder(
            span, token, None, [], workflow_name, entity_name, entity_path
        )

        if parent_run_id is not None and parent_run_id in self.spans:
            self.spans[parent_run_id].children.append(run_id)

        return span

    def _create_task_span(
        self,
        run_id: UUID,
        parent_run_id: Optional[UUID],
        name: str,
        kind: TraceloopSpanKindValues,
        workflow_name: str,
        entity_name: str = "",
        entity_path: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Span:
        span_name = f"{name}.{kind.value}"
        span = self._create_span(
            run_id,
            parent_run_id,
            span_name,
            workflow_name=workflow_name,
            entity_name=entity_name,
            entity_path=entity_path,
            metadata=metadata,
        )

        _set_span_attribute(span, SpanAttributes.TRACELOOP_SPAN_KIND, kind.value)
        _set_span_attribute(span, SpanAttributes.TRACELOOP_ENTITY_NAME, entity_name)

        return span

    def _create_llm_span(
        self,
        run_id: UUID,
        parent_run_id: Optional[UUID],
        name: str,
        request_type: LLMRequestTypeValues,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Span:
        workflow_name = self.get_workflow_name(parent_run_id)
        entity_path = self.get_entity_path(parent_run_id)

        span = self._create_span(
            run_id,
            parent_run_id,
            f"{name}.{request_type.value}",
            kind=SpanKind.CLIENT,
            workflow_name=workflow_name,
            entity_path=entity_path,
            metadata=metadata,
        )
        _set_span_attribute(span, SpanAttributes.LLM_SYSTEM, "Langchain")
        _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TYPE, request_type.value)

        return span

    @dont_throw
    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when chain starts running."""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        workflow_name = ""
        entity_path = ""

        name = self._get_name_from_callback(serialized, **kwargs)
        kind = (
            TraceloopSpanKindValues.WORKFLOW
            if parent_run_id is None or parent_run_id not in self.spans
            else TraceloopSpanKindValues.TASK
        )

        if kind == TraceloopSpanKindValues.WORKFLOW:
            workflow_name = name
        else:
            workflow_name = self.get_workflow_name(parent_run_id)
            entity_path = self.get_entity_path(parent_run_id)

        span = self._create_task_span(
            run_id,
            parent_run_id,
            name,
            kind,
            workflow_name,
            name,
            entity_path,
            metadata,
        )
        if should_send_prompts():
            _set_span_attribute(
                span,
                SpanAttributes.TRACELOOP_ENTITY_INPUT,
                json.dumps(
                    {
                        "inputs": inputs,
                        "tags": tags,
                        "metadata": metadata,
                        "kwargs": kwargs,
                    },
                    cls=CallbackFilteredJSONEncoder,
                ),
            )

        # The start_time is now automatically set when creating the SpanHolder

    @dont_throw
    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when chain ends running."""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        span_holder = self.spans[run_id]
        span = span_holder.span
        if should_send_prompts():
            _set_span_attribute(
                span,
                SpanAttributes.TRACELOOP_ENTITY_OUTPUT,
                json.dumps(
                    {"outputs": outputs, "kwargs": kwargs},
                    cls=CallbackFilteredJSONEncoder,
                ),
            )

        self._end_span(span, run_id)
        if parent_run_id is None:
            context_api.attach(
                context_api.set_value(
                    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY, False
                )
            )

    @dont_throw
    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        tags: Optional[list[str]] = None,
        parent_run_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Run when Chat Model starts running."""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        name = self._get_name_from_callback(serialized, kwargs=kwargs)
        span = self._create_llm_span(
            run_id, parent_run_id, name, LLMRequestTypeValues.CHAT, metadata=metadata
        )
        _set_chat_request(span, serialized, messages, kwargs, self.spans[run_id])

    @dont_throw
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        tags: Optional[list[str]] = None,
        parent_run_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Run when Chat Model starts running."""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        name = self._get_name_from_callback(serialized, kwargs=kwargs)
        span = self._create_llm_span(
            run_id, parent_run_id, name, LLMRequestTypeValues.COMPLETION
        )
        _set_llm_request(span, serialized, prompts, kwargs, self.spans[run_id])

    @dont_throw
    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Union[UUID, None] = None,
        **kwargs: Any,
    ):
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        span = self._get_span(run_id)

        model_name = None
        if response.llm_output is not None:
            model_name = response.llm_output.get(
                "model_name"
            ) or response.llm_output.get("model_id")
            if model_name is not None:
                _set_span_attribute(span, SpanAttributes.LLM_RESPONSE_MODEL, model_name)

                if self.spans[run_id].request_model is None:
                    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, model_name)
            id = response.llm_output.get("id")
            if id is not None and id != "":
                _set_span_attribute(span, GEN_AI_RESPONSE_ID, id)

        token_usage = (response.llm_output or {}).get("token_usage") or (
            response.llm_output or {}
        ).get("usage")
        if token_usage is not None:
            prompt_tokens = (
                token_usage.get("prompt_tokens")
                or token_usage.get("input_token_count")
                or token_usage.get("input_tokens")
            )
            completion_tokens = (
                token_usage.get("completion_tokens")
                or token_usage.get("generated_token_count")
                or token_usage.get("output_tokens")
            )
            total_tokens = token_usage.get("total_tokens") or (
                prompt_tokens + completion_tokens
            )

            _set_span_attribute(
                span, SpanAttributes.LLM_USAGE_PROMPT_TOKENS, prompt_tokens
            )
            _set_span_attribute(
                span, SpanAttributes.LLM_USAGE_COMPLETION_TOKENS, completion_tokens
            )
            _set_span_attribute(
                span, SpanAttributes.LLM_USAGE_TOTAL_TOKENS, total_tokens
            )

            # Record token usage metrics
            if prompt_tokens > 0:
                self.token_histogram.record(
                    prompt_tokens,
                    attributes={
                        SpanAttributes.LLM_SYSTEM: "Langchain",
                        SpanAttributes.LLM_TOKEN_TYPE: "input",
                        SpanAttributes.LLM_RESPONSE_MODEL: model_name or "unknown",
                    },
                )

            if completion_tokens > 0:
                self.token_histogram.record(
                    completion_tokens,
                    attributes={
                        SpanAttributes.LLM_SYSTEM: "Langchain",
                        SpanAttributes.LLM_TOKEN_TYPE: "output",
                        SpanAttributes.LLM_RESPONSE_MODEL: model_name or "unknown",
                    },
                )

        _set_chat_response(span, response)
        self._end_span(span, run_id)

        # Record duration
        duration = time.time() - self.spans[run_id].start_time
        self.duration_histogram.record(
            duration,
            attributes={
                SpanAttributes.LLM_SYSTEM: "Langchain",
                SpanAttributes.LLM_RESPONSE_MODEL: model_name or "unknown",
            },
        )

    @dont_throw
    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        inputs: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when tool starts running."""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        name = self._get_name_from_callback(serialized, kwargs=kwargs)
        workflow_name = self.get_workflow_name(parent_run_id)
        entity_path = self.get_entity_path(parent_run_id)

        span = self._create_task_span(
            run_id,
            parent_run_id,
            name,
            TraceloopSpanKindValues.TOOL,
            workflow_name,
            name,
            entity_path,
        )
        if should_send_prompts():
            _set_span_attribute(
                span,
                SpanAttributes.TRACELOOP_ENTITY_INPUT,
                json.dumps(
                    {
                        "input_str": input_str,
                        "tags": tags,
                        "metadata": metadata,
                        "inputs": inputs,
                        "kwargs": kwargs,
                    },
                    cls=CallbackFilteredJSONEncoder,
                ),
            )

    @dont_throw
    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when tool ends running."""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        span = self._get_span(run_id)
        if should_send_prompts():
            _set_span_attribute(
                span,
                SpanAttributes.TRACELOOP_ENTITY_OUTPUT,
                json.dumps(
                    {"output": output, "kwargs": kwargs},
                    cls=CallbackFilteredJSONEncoder,
                ),
            )
        self._end_span(span, run_id)

    def get_parent_span(self, parent_run_id: Optional[str] = None):
        if parent_run_id is None:
            return None
        return self.spans[parent_run_id]

    def get_workflow_name(self, parent_run_id: str):
        parent_span = self.get_parent_span(parent_run_id)

        if parent_span is None:
            return ""

        return parent_span.workflow_name

    def get_entity_path(self, parent_run_id: str):
        parent_span = self.get_parent_span(parent_run_id)

        if parent_span is None:
            return ""
        elif (
            parent_span.entity_path == ""
            and parent_span.entity_name == parent_span.workflow_name
        ):
            return ""
        elif parent_span.entity_path == "":
            return f"{parent_span.entity_name}"
        else:
            return f"{parent_span.entity_path}.{parent_span.entity_name}"

    def _handle_error(
        self,
        error: BaseException,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Common error handling logic for all components."""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        span = self._get_span(run_id)
        span.set_status(Status(StatusCode.ERROR))
        span.record_exception(error)
        self._end_span(span, run_id)

    @dont_throw
    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM errors."""
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when chain errors."""
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when tool errors."""
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    def on_agent_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when agent errors."""
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when retriever errors."""
        self._handle_error(error, run_id, parent_run_id, **kwargs)
