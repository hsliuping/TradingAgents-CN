"""OpenTelemetry exporter for LangSmith runs."""

from __future__ import annotations

import datetime
import logging
import uuid
import warnings
from typing import Any, Optional

from langsmith import utils as ls_utils
from langsmith._internal import _orjson
from langsmith._internal._operations import (
    SerializedRunOperation,
)
from langsmith._internal._otel_utils import (
    get_otel_span_id_from_uuid,
    get_otel_trace_id_from_uuid,
)

HAS_OTEL = False
try:
    if ls_utils.is_truish(ls_utils.get_env_var("OTEL_ENABLED")):
        from opentelemetry import trace  # type: ignore[import]
        from opentelemetry.context.context import Context  # type: ignore[import]
        from opentelemetry.trace import (  # type: ignore[import]
            NonRecordingSpan,
            Span,
            SpanContext,
            TraceFlags,
            TraceState,
            set_span_in_context,
        )

        HAS_OTEL = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

# OpenTelemetry GenAI semconv attribute names
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
GEN_AI_REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
GEN_AI_REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GENAI_PROMPT = "gen_ai.prompt"
GENAI_COMPLETION = "gen_ai.completion"

GEN_AI_REQUEST_EXTRA_QUERY = "gen_ai.request.extra_query"
GEN_AI_REQUEST_EXTRA_BODY = "gen_ai.request.extra_body"
GEN_AI_SERIALIZED_NAME = "gen_ai.serialized.name"
GEN_AI_SERIALIZED_SIGNATURE = "gen_ai.serialized.signature"
GEN_AI_SERIALIZED_DOC = "gen_ai.serialized.doc"
GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_RESPONSE_SERVICE_TIER = "gen_ai.response.service_tier"
GEN_AI_RESPONSE_SYSTEM_FINGERPRINT = "gen_ai.response.system_fingerprint"
GEN_AI_USAGE_INPUT_TOKEN_DETAILS = "gen_ai.usage.input_token_details"
GEN_AI_USAGE_OUTPUT_TOKEN_DETAILS = "gen_ai.usage.output_token_details"

# LangSmith custom attributes
LANGSMITH_RUN_ID = "langsmith.span.id"
LANGSMITH_TRACE_ID = "langsmith.trace.id"
LANGSMITH_DOTTED_ORDER = "langsmith.span.dotted_order"
LANGSMITH_PARENT_RUN_ID = "langsmith.span.parent_id"
LANGSMITH_SESSION_ID = "langsmith.trace.session_id"
LANGSMITH_SESSION_NAME = "langsmith.trace.session_name"
LANGSMITH_RUN_TYPE = "langsmith.span.kind"
LANGSMITH_NAME = "langsmith.trace.name"
LANGSMITH_METADATA = "langsmith.metadata"
LANGSMITH_TAGS = "langsmith.span.tags"
LANGSMITH_RUNTIME = "langsmith.span.runtime"
LANGSMITH_REQUEST_STREAMING = "langsmith.request.streaming"
LANGSMITH_REQUEST_HEADERS = "langsmith.request.headers"

# GenAI event names
GEN_AI_SYSTEM_MESSAGE = "gen_ai.system.message"
GEN_AI_USER_MESSAGE = "gen_ai.user.message"
GEN_AI_ASSISTANT_MESSAGE = "gen_ai.assistant.message"
GEN_AI_CHOICE = "gen_ai.choice"

WELL_KNOWN_OPERATION_NAMES = {
    "llm": "chat",
    "tool": "execute_tool",
    "retriever": "embeddings",
    "embedding": "embeddings",
    "prompt": "chat",
}


def _get_operation_name(run_type: str) -> str:
    return WELL_KNOWN_OPERATION_NAMES.get(run_type, run_type)


class OTELExporter:
    __slots__ = ["_tracer", "_spans"]
    """OpenTelemetry exporter for LangSmith runs."""

    def __init__(self, tracer_provider=None):
        """Initialize the OTEL exporter.

        Args:
            tracer_provider: Optional tracer provider to use. If not provided,
                the global tracer provider will be used.
        """
        if not HAS_OTEL:
            warnings.warn(
                "OTEL_ENABLED is set but OpenTelemetry packages are not installed. "
                "Install with `pip install langsmith[otel]`"
            )
            return

        self._tracer = trace.get_tracer("langsmith", tracer_provider=tracer_provider)
        self._spans = {}

    def export_batch(
        self,
        operations: list[SerializedRunOperation],
        otel_context_map: dict[uuid.UUID, Optional[Context]],
    ) -> None:
        """Export a batch of serialized run operations to OTEL.

        Args:
            operations: List of serialized run operations to export.
        """
        # Create a dictionary mapping run IDs to their operations

        for op in operations:
            try:
                run_info = self._deserialize_run_info(op)
                if not run_info:
                    continue
                if op.operation == "post":
                    span = self._create_span_for_run(
                        op, run_info, otel_context_map.get(op.id)
                    )
                    if span:
                        self._spans[op.id] = span
                else:
                    self._update_span_for_run(op, run_info)
            except Exception as e:
                logger.exception(f"Error processing operation {op.id}: {e}")

    def _deserialize_run_info(self, op: SerializedRunOperation) -> Optional[dict]:
        """Deserialize the run info from the operation.

        Args:
            op: The serialized run operation.

        Returns:
            The deserialized run info as a dictionary, or None if deserialization
            failed.
        """
        try:
            run_info = _orjson.loads(op._none)

            # convert run_info to a Run Schema
            return run_info
        except Exception as e:
            logger.exception(f"Failed to deserialize run info for {op.id}: {e}")
            return None

    def _create_span_for_run(
        self,
        op: SerializedRunOperation,
        run_info: dict,
        otel_context: Optional[Context] = None,
    ) -> Optional[Span]:
        """Create an OpenTelemetry span for a run operation.

        Args:
            op: The serialized run operation.
            run_info: The deserialized run info.
            parent_span: Optional parent span.

        Returns:
            The created span, or None if creation failed.
        """
        try:
            start_time = run_info.get("start_time")
            start_time_utc_nano = self._as_utc_nano(start_time)

            end_time = run_info.get("end_time")
            end_time_utc_nano = self._as_utc_nano(end_time)

            # Create deterministic trace and span IDs to match user OpenTelemetry spans
            trace_id_int = get_otel_trace_id_from_uuid(op.trace_id)
            span_id_int = get_otel_span_id_from_uuid(op.id)

            # Create SpanContext with deterministic IDs
            span_context = SpanContext(
                trace_id=trace_id_int,
                span_id=span_id_int,
                is_remote=False,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
                trace_state=TraceState(),
            )

            # Create NonRecordingSpan for context setting
            non_recording_span = NonRecordingSpan(span_context)
            deterministic_context = set_span_in_context(non_recording_span)

            # Start the span with appropriate context
            parent_run_id = run_info.get("parent_run_id")
            if parent_run_id is not None and uuid.UUID(parent_run_id) in self._spans:
                # Use the parent span context
                span = self._tracer.start_span(
                    run_info.get("name"),
                    context=set_span_in_context(self._spans[uuid.UUID(parent_run_id)]),
                    start_time=start_time_utc_nano,
                )
            else:
                # For root spans, check if there's an existing OpenTelemetry context
                # If so, inherit from it; otherwise use our deterministic context
                current_context = (
                    otel_context if otel_context else deterministic_context
                )
                span = self._tracer.start_span(
                    run_info.get("name"),
                    context=current_context,
                    start_time=start_time_utc_nano,
                )

            # Set all attributes
            self._set_span_attributes(span, run_info, op)

            # Set status based on error
            if run_info.get("error"):
                span.set_status(trace.StatusCode.ERROR)
                span.record_exception(Exception(run_info.get("error")))
            else:
                span.set_status(trace.StatusCode.OK)

            # End the span if end_time is present
            end_time = run_info.get("end_time")
            if end_time:
                end_time_utc_nano = self._as_utc_nano(end_time)
                if end_time_utc_nano:
                    span.end(end_time=end_time_utc_nano)
                else:
                    span.end()

            return span
        except Exception as e:
            logger.exception(f"Failed to create span for run {op.id}: {e}")
            return None

    def _update_span_for_run(self, op: SerializedRunOperation, run_info: dict) -> None:
        """Update an OpenTelemetry span for a run operation.

        Args:
            op: The serialized run operation.
            run_info: The deserialized run info.
        """
        try:
            # Get the span for this run
            if op.id not in self._spans:
                logger.debug(f"No span found for run {op.id} during update")
                return

            span = self._spans[op.id]

            # Update attributes
            self._set_span_attributes(span, run_info, op)
            # Update status based on error
            if run_info.get("error"):
                span.set_status(trace.StatusCode.ERROR)
                span.record_exception(Exception(run_info.get("error")))
            else:
                span.set_status(trace.StatusCode.OK)

            # End the span if end_time is present
            end_time = run_info.get("end_time")
            if end_time:
                end_time_utc_nano = self._as_utc_nano(end_time)
                if end_time_utc_nano:
                    span.end(end_time=end_time_utc_nano)
                else:
                    span.end()
                # Remove the span from our dictionary
                del self._spans[op.id]

        except Exception as e:
            logger.exception(f"Failed to update span for run {op.id}: {e}")

    def _extract_model_name(self, run_info: dict) -> Optional[str]:
        """Extract model name from run info.

        Args:
            run_info: The run info.

        Returns:
            The model name, or None if not found.
        """
        # Try to get model name from metadata
        if run_info.get("extra") and run_info["extra"].get("metadata"):
            metadata = run_info["extra"]["metadata"]

            # First check for ls_model_name in metadata
            if metadata.get("ls_model_name"):
                return metadata["ls_model_name"]

            # Then check invocation_params for model info
            if "invocation_params" in metadata:
                invocation_params = metadata["invocation_params"]
                # Check model first, then model_name
                if invocation_params.get("model"):
                    return invocation_params["model"]
                elif invocation_params.get("model_name"):
                    return invocation_params["model_name"]

        return None

    def _set_span_attributes(
        self, span: Span, run_info: dict, op: SerializedRunOperation
    ) -> None:
        """Set attributes on the span.

        Args:
            span: The span to set attributes on.
            run_info: The deserialized run info.
            op: The serialized run operation.
        """
        # Set LangSmith-specific attributes
        span.set_attribute(LANGSMITH_RUN_ID, str(op.id))
        span.set_attribute(LANGSMITH_TRACE_ID, str(op.trace_id))

        if run_info.get("dotted_order"):
            span.set_attribute(
                LANGSMITH_DOTTED_ORDER, str(run_info.get("dotted_order"))
            )

        if run_info.get("parent_run_id"):
            span.set_attribute(
                LANGSMITH_PARENT_RUN_ID, str(run_info.get("parent_run_id"))
            )
        if run_info.get("run_type"):
            span.set_attribute(LANGSMITH_RUN_TYPE, str(run_info.get("run_type")))

        if run_info.get("name"):
            span.set_attribute(LANGSMITH_NAME, str(run_info.get("name")))

        if run_info.get("session_id"):
            span.set_attribute(LANGSMITH_SESSION_ID, str(run_info.get("session_id")))
        if run_info.get("session_name"):
            span.set_attribute(
                LANGSMITH_SESSION_NAME, str(run_info.get("session_name"))
            )

        # Set GenAI attributes according to OTEL semantic conventions
        # Set gen_ai.operation.name
        operation_name = _get_operation_name(run_info.get("run_type", "chain"))
        span.set_attribute(GEN_AI_OPERATION_NAME, operation_name)

        # Set gen_ai.system
        self._set_gen_ai_system(span, run_info)

        # Set model name if available
        model_name = self._extract_model_name(run_info)
        if model_name:
            span.set_attribute(GEN_AI_REQUEST_MODEL, model_name)

        # Set token usage information
        if run_info.get("prompt_tokens") is not None:
            prompt_tokens = run_info["prompt_tokens"]
            span.set_attribute(GEN_AI_USAGE_INPUT_TOKENS, int(prompt_tokens))

        if run_info.get("completion_tokens") is not None:
            completion_tokens = run_info["completion_tokens"]
            span.set_attribute(GEN_AI_USAGE_OUTPUT_TOKENS, int(completion_tokens))

        if run_info.get("total_tokens") is not None:
            total_tokens = run_info["total_tokens"]
            span.set_attribute(GEN_AI_USAGE_TOTAL_TOKENS, int(total_tokens))

        # Set other parameters from invocation_params
        self._set_invocation_parameters(span, run_info)

        # Set metadata and tags if available
        extra = run_info.get("extra", {})
        metadata = extra.get("metadata", {})
        for key, value in metadata.items():
            if value is not None:
                span.set_attribute(f"{LANGSMITH_METADATA}.{key}", value)

        tags = run_info.get("tags")
        if tags:
            if isinstance(tags, list):
                span.set_attribute(LANGSMITH_TAGS, ", ".join(tags))
            else:
                span.set_attribute(LANGSMITH_TAGS, tags)

        # Support additional serialized attributes, if present
        if run_info.get("serialized") and isinstance(run_info["serialized"], dict):
            serialized = run_info["serialized"]
            if "name" in serialized and serialized["name"] is not None:
                span.set_attribute(GEN_AI_SERIALIZED_NAME, serialized["name"])
            if "signature" in serialized and serialized["signature"] is not None:
                span.set_attribute(GEN_AI_SERIALIZED_SIGNATURE, serialized["signature"])
            if "doc" in serialized and serialized["doc"] is not None:
                span.set_attribute(GEN_AI_SERIALIZED_DOC, serialized["doc"])

        # Set inputs/outputs if available
        self._set_io_attributes(span, op)

    def _set_gen_ai_system(self, span: Span, run_info: dict) -> None:
        """Set the gen_ai.system attribute on the span based on the model provider.

        Args:
            span: The span to set attributes on.
            run_info: The deserialized run info.
        """
        # Default to "langchain" if we can't determine the system
        system = "langchain"

        # Extract model name to determine the system
        model_name = self._extract_model_name(run_info)
        if model_name:
            model_lower = model_name.lower()
            if "anthropic" in model_lower or model_lower.startswith("claude"):
                system = "anthropic"
            elif "bedrock" in model_lower:
                system = "aws.bedrock"
            elif "azure" in model_lower and "openai" in model_lower:
                system = "az.ai.openai"
            elif "azure" in model_lower and "inference" in model_lower:
                system = "az.ai.inference"
            elif "cohere" in model_lower:
                system = "cohere"
            elif "deepseek" in model_lower:
                system = "deepseek"
            elif "gemini" in model_lower:
                system = "gemini"
            elif "groq" in model_lower:
                system = "groq"
            elif "watson" in model_lower or "ibm" in model_lower:
                system = "ibm.watsonx.ai"
            elif "mistral" in model_lower:
                system = "mistral_ai"
            elif "gpt" in model_lower or "openai" in model_lower:
                system = "openai"
            elif "perplexity" in model_lower or "sonar" in model_lower:
                system = "perplexity"
            elif "vertex" in model_lower:
                system = "vertex_ai"
            elif "xai" in model_lower or "grok" in model_lower:
                system = "xai"

        span.set_attribute(GEN_AI_SYSTEM, system)
        setattr(span, "_gen_ai_system", system)

    def _set_invocation_parameters(self, span: Span, run_info: dict) -> None:
        """Set invocation parameters on the span.

        Args:
            span: The span to set attributes on.
            run_info: The deserialized run info.
        """
        if not (run_info.get("extra") and run_info["extra"].get("metadata")):
            return

        metadata = run_info["extra"]["metadata"]
        if "invocation_params" not in metadata:
            return

        invocation_params = metadata["invocation_params"]

        # Set relevant invocation parameters
        if "max_tokens" in invocation_params:
            span.set_attribute(
                GEN_AI_REQUEST_MAX_TOKENS, invocation_params["max_tokens"]
            )

        if "temperature" in invocation_params:
            span.set_attribute(
                GEN_AI_REQUEST_TEMPERATURE, invocation_params["temperature"]
            )

        if "top_p" in invocation_params:
            span.set_attribute(GEN_AI_REQUEST_TOP_P, invocation_params["top_p"])

        if "frequency_penalty" in invocation_params:
            span.set_attribute(
                GEN_AI_REQUEST_FREQUENCY_PENALTY, invocation_params["frequency_penalty"]
            )

        if "presence_penalty" in invocation_params:
            span.set_attribute(
                GEN_AI_REQUEST_PRESENCE_PENALTY, invocation_params["presence_penalty"]
            )

    def _set_io_attributes(self, span: Span, op: SerializedRunOperation) -> None:
        """Set input/output attributes on the span.

        Args:
            span: The span to set attributes on.
            op: The serialized run operation.
        """
        if op.inputs:
            try:
                inputs = _orjson.loads(op.inputs)

                if isinstance(inputs, dict):
                    if (
                        "model" in inputs
                        and isinstance(inputs.get("messages"), list)
                        and inputs["model"] is not None
                    ):
                        span.set_attribute(GEN_AI_REQUEST_MODEL, inputs["model"])

                    # Set additional request attributes if available.
                    if "stream" in inputs and inputs["stream"] is not None:
                        span.set_attribute(
                            LANGSMITH_REQUEST_STREAMING, inputs["stream"]
                        )
                    if (
                        "extra_headers" in inputs
                        and inputs["extra_headers"] is not None
                    ):
                        span.set_attribute(
                            LANGSMITH_REQUEST_HEADERS, inputs["extra_headers"]
                        )
                    if "extra_query" in inputs and inputs["extra_query"] is not None:
                        span.set_attribute(
                            GEN_AI_REQUEST_EXTRA_QUERY, inputs["extra_query"]
                        )
                    if "extra_body" in inputs and inputs["extra_body"] is not None:
                        span.set_attribute(
                            GEN_AI_REQUEST_EXTRA_BODY, inputs["extra_body"]
                        )

                span.set_attribute(GENAI_PROMPT, op.inputs)

            except Exception:
                logger.debug(
                    "Failed to process inputs for run %s", op.id, exc_info=True
                )

        if op.outputs:
            try:
                outputs = _orjson.loads(op.outputs)

                # Extract token usage from outputs (for LLM runs)
                token_usage = self.get_unified_run_tokens(outputs)
                if token_usage:
                    span.set_attribute(GEN_AI_USAGE_INPUT_TOKENS, token_usage[0])
                    span.set_attribute(GEN_AI_USAGE_OUTPUT_TOKENS, token_usage[1])
                    span.set_attribute(
                        GEN_AI_USAGE_TOTAL_TOKENS, token_usage[0] + token_usage[1]
                    )

                    if "model" in outputs:
                        span.set_attribute(GEN_AI_RESPONSE_MODEL, str(outputs["model"]))
                # Extract additional response attributes.
                if isinstance(outputs, dict):
                    if "id" in outputs and outputs["id"] is not None:
                        span.set_attribute(GEN_AI_RESPONSE_ID, outputs["id"])
                    if "choices" in outputs and isinstance(outputs["choices"], list):
                        finish_reasons = []
                        for choice in outputs["choices"]:
                            if (
                                "finish_reason" in choice
                                and choice["finish_reason"] is not None
                            ):
                                finish_reasons.append(str(choice["finish_reason"]))
                        if finish_reasons:
                            span.set_attribute(
                                GEN_AI_RESPONSE_FINISH_REASONS,
                                ", ".join(finish_reasons),
                            )
                    if (
                        "service_tier" in outputs
                        and outputs["service_tier"] is not None
                    ):
                        span.set_attribute(
                            GEN_AI_RESPONSE_SERVICE_TIER, outputs["service_tier"]
                        )
                    if (
                        "system_fingerprint" in outputs
                        and outputs["system_fingerprint"] is not None
                    ):
                        span.set_attribute(
                            GEN_AI_RESPONSE_SYSTEM_FINGERPRINT,
                            outputs["system_fingerprint"],
                        )
                    if "usage_metadata" in outputs and isinstance(
                        outputs["usage_metadata"], dict
                    ):
                        usage_metadata = outputs["usage_metadata"]
                        if (
                            "input_token_details" in usage_metadata
                            and usage_metadata["input_token_details"] is not None
                        ):
                            input_token_details = str(
                                usage_metadata["input_token_details"]
                            )
                            span.set_attribute(
                                GEN_AI_USAGE_INPUT_TOKEN_DETAILS, input_token_details
                            )
                        if (
                            "output_token_details" in usage_metadata
                            and usage_metadata["output_token_details"] is not None
                        ):
                            output_token_details = str(
                                usage_metadata["output_token_details"]
                            )
                            span.set_attribute(
                                GEN_AI_USAGE_OUTPUT_TOKEN_DETAILS, output_token_details
                            )

                span.set_attribute(GENAI_COMPLETION, op.outputs)

            except Exception:
                logger.debug(
                    "Failed to process outputs for run %s", op.id, exc_info=True
                )

    def _as_utc_nano(self, timestamp: Optional[str]) -> Optional[int]:
        if not timestamp:
            return None
        try:
            dt = datetime.datetime.fromisoformat(timestamp)
            return int(dt.astimezone(datetime.timezone.utc).timestamp() * 1_000_000_000)
        except ValueError:
            logger.exception(f"Failed to parse timestamp {timestamp}")
            return None

    def get_unified_run_tokens(
        self, outputs: Optional[dict]
    ) -> Optional[tuple[int, int]]:
        if not outputs:
            return None

        # search in non-generations lists
        if output := self._extract_unified_run_tokens(outputs.get("usage_metadata")):
            return output

        # find if direct kwarg in outputs
        keys = outputs.keys()
        for key in keys:
            haystack = outputs[key]
            if not haystack or not isinstance(haystack, dict):
                continue

            if output := self._extract_unified_run_tokens(
                haystack.get("usage_metadata")
            ):
                return output

            if (
                haystack.get("lc") == 1
                and "kwargs" in haystack
                and isinstance(haystack["kwargs"], dict)
                and (
                    output := self._extract_unified_run_tokens(
                        haystack["kwargs"].get("usage_metadata")
                    )
                )
            ):
                return output

        # find in generations
        generations = outputs.get("generations") or []
        if not isinstance(generations, list):
            return None
        if generations and not isinstance(generations[0], list):
            generations = [generations]

        for generation in [x for xs in generations for x in xs]:
            if (
                isinstance(generation, dict)
                and "message" in generation
                and isinstance(generation["message"], dict)
                and "kwargs" in generation["message"]
                and isinstance(generation["message"]["kwargs"], dict)
                and (
                    output := self._extract_unified_run_tokens(
                        generation["message"]["kwargs"].get("usage_metadata")
                    )
                )
            ):
                return output
        return None

    def _extract_unified_run_tokens(
        self, outputs: Optional[Any]
    ) -> Optional[tuple[int, int]]:
        if not outputs or not isinstance(outputs, dict):
            return None

        if "input_tokens" not in outputs or "output_tokens" not in outputs:
            return None

        if not isinstance(outputs["input_tokens"], int) or not isinstance(
            outputs["output_tokens"], int
        ):
            return None

        return outputs["input_tokens"], outputs["output_tokens"]
