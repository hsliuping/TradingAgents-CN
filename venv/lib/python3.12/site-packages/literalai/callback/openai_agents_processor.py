from __future__ import annotations

import logging
from importlib.metadata import version
from typing import TYPE_CHECKING, Any, Dict, Optional

from literalai.context import active_thread_var
from literalai.helper import ensure_values_serializable, force_dict
from literalai.observability.generation import ChatGeneration
from literalai.observability.step import Step, StepType

if TYPE_CHECKING:
    from literalai.client import LiteralClient


logger = logging.getLogger(__name__)


def get_openai_agents_tracing_processor():
    try:
        version("openai-agents")
    except Exception:
        raise Exception(
            "Please install agents to use the agents tracing processor. "
            "You can install it with `pip install openai-agents.`"
        )

    from agents.tracing import Span, Trace, TracingProcessor
    from agents.tracing.span_data import (
        AgentSpanData,
        CustomSpanData,
        FunctionSpanData,
        GenerationSpanData,
        GuardrailSpanData,
        HandoffSpanData,
        ResponseSpanData,
        SpanData,
    )

    def _get_span_name(obj: Span) -> str:
        if hasattr(data := obj.span_data, "name") and isinstance(
            name := data.name, str
        ):
            return name
        if isinstance(obj.span_data, HandoffSpanData) and obj.span_data.to_agent:
            return f"handoff to {obj.span_data.to_agent}"
        return obj.span_data.type

    def _get_span_type(obj: SpanData) -> StepType:
        if isinstance(obj, AgentSpanData):
            return "run"
        if isinstance(obj, FunctionSpanData):
            return "tool"
        if isinstance(obj, GenerationSpanData):
            return "llm"
        if isinstance(obj, ResponseSpanData):
            return "llm"
        if isinstance(obj, HandoffSpanData):
            return "tool"
        if isinstance(obj, CustomSpanData):
            return "undefined"
        if isinstance(obj, GuardrailSpanData):
            return "undefined"
        return "undefined"

    def _extract_function_span_data(
        span_data: FunctionSpanData,
    ) -> Dict[str, Any]:
        return {
            "inputs": force_dict(ensure_values_serializable(span_data.input)),
            "outputs": force_dict(ensure_values_serializable(span_data.output)),
        }

    def _extract_generation_span_data(span_data: GenerationSpanData) -> Dict[str, Any]:
        """Extract data from a generation span."""

        generation = ChatGeneration(
            provider=getattr(span_data, "provider", "unknown"),
            model=getattr(span_data, "model", None),
            settings=getattr(span_data, "model_config", None),
            token_count=span_data.usage.get("total_tokens"),
            input_token_count=span_data.usage.get("prompt_tokens"),
            output_token_count=span_data.usage.get("completion_tokens"),
            messages=span_data.input,
        )

        return {"generation": generation}

    def _extract_response_span_data(span_data: ResponseSpanData) -> Dict[str, Any]:
        """Extract data from a response span."""
        data: Dict[str, Any] = {}

        generation = ChatGeneration(provider="openai")

        metadata = {}

        if span_data.input is not None:
            generation.messages = span_data.input
            metadata["instructions"] = span_data.response.instructions

        if span_data.response is not None:
            response = span_data.response.model_dump(exclude_none=True, mode="json")
            output = response.pop("output", [])
            if output:
                generation.message_completion = {
                    "role": "assistant",
                    "content": span_data.response.output_text,
                }

            if usage := response.pop("usage", None):
                if "output_tokens" in usage:
                    generation.output_token_count = usage.pop("output_tokens")
                if "input_tokens" in usage:
                    generation.input_token_count = usage.pop("input_tokens")
                if "total_tokens" in usage:
                    generation.token_count = usage.pop("total_tokens")

                metadata["usage"] = usage

            generation.settings = {
                k: v
                for k, v in response.items()
                if k
                in (
                    "max_output_tokens",
                    "model",
                    "parallel_tool_calls",
                    "reasoning",
                    "temperature",
                    "text",
                    "tool_choice",
                    "tools",
                    "top_p",
                    "truncation",
                )
            }
            generation.model = generation.settings.get("model")
            generation.tools = generation.settings.pop("tools", [])
        data["generation"] = generation
        data["metadata"] = metadata

        return data

    def _extract_agent_span_data(span_data: AgentSpanData) -> Dict[str, Any]:
        """Extract data from an agent span."""
        breakpoint()
        return {
            "inputs": force_dict(
                ensure_values_serializable(getattr(span_data, "input", None))
            ),
            "outputs": force_dict(
                ensure_values_serializable(getattr(span_data, "output", None))
            ),
            "invocation_params": {
                "tools": getattr(span_data, "tools", []),
                "handoffs": getattr(span_data, "handoffs", []),
            },
            "metadata": {
                "output_type": getattr(span_data, "output_type", None),
                "type": "agent",
            },
        }

    def _extract_handoff_span_data(span_data: HandoffSpanData) -> Dict[str, Any]:
        """Extract data from a handoff span."""
        return {
            "inputs": {
                "from_agent": getattr(span_data, "from_agent", None),
                "to_agent": getattr(span_data, "to_agent", None),
                "content": getattr(span_data, "content", None),
            },
            "metadata": {
                "type": "handoff",
            },
        }

    def _extract_guardrail_span_data(span_data: GuardrailSpanData) -> Dict[str, Any]:
        """Extract data from a guardrail span."""
        return {
            "inputs": force_dict(
                ensure_values_serializable(getattr(span_data, "input", None))
            ),
            "outputs": force_dict(
                ensure_values_serializable(getattr(span_data, "output", None))
            ),
            "metadata": {
                "triggered": getattr(span_data, "triggered", False),
                "type": "guardrail",
            },
        }

    def _extract_custom_span_data(span_data: CustomSpanData) -> Dict[str, Any]:
        """Extract data from a custom span."""
        data = {"metadata": {"type": "custom"}}

        if hasattr(span_data, "data"):
            if isinstance(span_data.data, dict):
                data["metadata"].update(span_data.data)
            else:
                data["metadata"]["data"] = str(span_data.data)

        return data

    def _extract_span_data(span: Span[Any]) -> Dict[str, Any]:
        """Extract data from a span based on its type."""
        data: Dict[str, Any] = {}

        if isinstance(span.span_data, FunctionSpanData):
            data.update(_extract_function_span_data(span.span_data))
        elif isinstance(span.span_data, GenerationSpanData):
            data.update(_extract_generation_span_data(span.span_data))
        elif isinstance(span.span_data, ResponseSpanData):
            data.update(_extract_response_span_data(span.span_data))
        elif isinstance(span.span_data, AgentSpanData):
            data.update(_extract_agent_span_data(span.span_data))
        elif isinstance(span.span_data, HandoffSpanData):
            data.update(_extract_handoff_span_data(span.span_data))
        elif isinstance(span.span_data, GuardrailSpanData):
            data.update(_extract_guardrail_span_data(span.span_data))
        elif isinstance(span.span_data, CustomSpanData):
            data.update(_extract_custom_span_data(span.span_data))

        return data

    class AgentsTracingProcessor(TracingProcessor):
        """Processor for sending agent traces to LiteralAI."""

        def __init__(
            self,
            literal_client: LiteralClient,
            thread_id: Optional[str] = None,
            include_metadata: bool = True,
        ) -> None:
            """
            Initialize the LiteralAI tracing processor.

            Args:
                literal_client: The LiteralAI client to use for sending traces.
                thread_id: Optional thread ID to associate with the traces.
                include_metadata: Whether to include metadata in the traces.
            """
            self.client = literal_client
            self.thread_id = thread_id
            self.include_metadata = include_metadata
            self._steps: Dict[str, Step] = {}
            self._root_steps: Dict[str, Step] = {}

        def on_trace_start(self, trace: Trace) -> None:
            """Called when a trace is started.

            Args:
                trace: The trace that started.
            """
            thread_id = self.thread_id
            if not thread_id and (active_thread := active_thread_var.get()):
                thread_id = active_thread.id

            root_step = self.client.start_step(
                name=trace.name,
                type="run",
                thread_id=thread_id,
            )

            trace_dict = trace.export() or {}
            metadata = trace_dict.get("metadata") or {}

            root_step.metadata = metadata

            self._root_steps[trace.trace_id] = root_step

        def on_trace_end(self, trace: Trace) -> None:
            """Called when a trace is finished.

            Args:
                trace: The trace that started.
            """
            if root_step := self._root_steps.pop(trace.trace_id, None):
                root_step.end()
                self.client.event_processor.flush()

        def on_span_start(self, span: Span[Any]) -> None:
            """Called when a span is started.

            Args:
                span: The span that started.
            """
            if not span.started_at:
                return

            parent_step = None
            if span.parent_id and span.parent_id in self._steps:
                parent_step = self._steps[span.parent_id]
            elif span.trace_id in self._root_steps:
                parent_step = self._root_steps[span.trace_id]

            span_name = _get_span_name(span)
            span_type = _get_span_type(span.span_data)

            thread_id = self.thread_id
            if not thread_id and (active_thread := active_thread_var.get()):
                thread_id = active_thread.id

            step = self.client.start_step(
                name=span_name,
                type=span_type,  # type: ignore
                parent_id=parent_step.id if parent_step else None,
                thread_id=thread_id,
            )

            self._steps[span.span_id] = step

        def on_span_end(self, span: Span[Any]) -> None:
            """Called when a span is finished. Should not block or raise exceptions.

            Args:
                span: The span that finished.
            """
            if not (step := self._steps.pop(span.span_id, None)):
                return

            try:
                # Extract all data from the span using our extraction helpers
                extracted_data = _extract_span_data(span)

                # Set inputs on the step if available
                if "inputs" in extracted_data:
                    step.input = extracted_data["inputs"]

                # Set outputs on the step if available
                if "outputs" in extracted_data:
                    step.output = extracted_data["outputs"]

                if "generation" in extracted_data:
                    step.generation = extracted_data["generation"]

                # Add metadata from extracted data
                if "metadata" in extracted_data:
                    if step.metadata is None:
                        step.metadata = {}
                    step.metadata.update(extracted_data["metadata"])

                # Handle errors
                if span.error:
                    step.error = span.error.message

            except Exception as e:
                logger.error(f"Error processing span: {e}")
                step.error = str(e)
            finally:
                step.end()

        def force_flush(self) -> None:
            """Forces an immediate flush of all queued spans/traces."""
            self.client.event_processor.flush()

        def shutdown(self) -> None:
            """Called when the application stops."""
            self.client.flush_and_stop()

    return AgentsTracingProcessor
