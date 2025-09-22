import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

try:
    from agents import tracing  # type: ignore[import]

    HAVE_AGENTS = True
except ImportError:
    HAVE_AGENTS = False

logger = logging.getLogger(__name__)

RunTypeT = Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"]

if HAVE_AGENTS:

    def parse_io(data: Any, default_key: str = "output") -> dict:
        """Parse inputs or outputs into a dictionary format.

        Args:
            data: The data to parse (can be inputs or outputs)
            default_key: The default key to use if data is not a dict
                ("input" or "output")

        Returns:
            Dict: The parsed data as a dictionary
        """
        if isinstance(data, dict):
            data_ = data
        elif isinstance(data, str):
            try:
                parsed_json = json.loads(data)
                if isinstance(parsed_json, dict):
                    data_ = parsed_json
                else:
                    data_ = {default_key: data}
            except json.JSONDecodeError:
                data_ = {default_key: data}
        elif (
            data is not None
            and hasattr(data, "model_dump")
            and callable(data.model_dump)
            and not isinstance(data, type)
        ):
            try:
                data_ = data.model_dump(exclude_none=True, mode="json")
            except Exception as e:
                logger.debug(
                    f"Failed to use model_dump to serialize {type(data)} to JSON: {e}"
                )
                data_ = {default_key: data}
        else:
            data_ = {default_key: data}

        return data_

    def get_run_type(span: tracing.Span) -> RunTypeT:
        span_type = getattr(span.span_data, "type", None)
        if span_type in ["agent", "handoff", "custom"]:
            return "chain"
        elif span_type in ["function", "guardrail"]:
            return "tool"
        elif span_type in ["generation", "response"]:
            return "llm"
        else:
            return "chain"

    def get_run_name(span: tracing.Span) -> str:
        if hasattr(span.span_data, "name") and span.span_data.name:
            return span.span_data.name
        span_type = getattr(span.span_data, "type", None)
        if span_type == "generation":
            return "Generation"
        elif span_type == "response":
            return "Response"
        elif span_type == "handoff":
            return "Handoff"
        else:
            return "Span"

    def _extract_function_span_data(
        span_data: tracing.FunctionSpanData,
    ) -> dict[str, Any]:
        return {
            "inputs": parse_io(span_data.input, "input"),
            "outputs": parse_io(span_data.output, "output"),
        }

    def _extract_generation_span_data(
        span_data: tracing.GenerationSpanData,
    ) -> dict[str, Any]:
        data = {
            "inputs": parse_io(span_data.input, "input"),
            "outputs": parse_io(span_data.output, "output"),
            "invocation_params": {
                "model": span_data.model,
                "model_config": span_data.model_config,
            },
        }
        if span_data.usage:
            data["outputs"]["usage_metadata"] = {
                "total_tokens": span_data.usage.get("total_tokens"),
                "input_tokens": span_data.usage.get("prompt_tokens"),
                "output_tokens": span_data.usage.get("completion_tokens"),
            }
        return data

    def _extract_response_span_data(
        span_data: tracing.ResponseSpanData,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if span_data.input is not None:
            data["inputs"] = {
                "input": span_data.input,
                "instructions": span_data.response.instructions,
            }
        if span_data.response is not None:
            response = span_data.response.model_dump(exclude_none=True, mode="json")
            data["outputs"] = {"output": response.pop("output", [])}
            if usage := response.pop("usage", None):
                # tokens -> token
                if "output_tokens_details" in usage:
                    usage["output_token_details"] = usage.pop("output_tokens_details")
                    usage["output_token_details"]["reasoning"] = usage[
                        "output_token_details"
                    ].pop("reasoning_tokens", 0)
                if "input_tokens_details" in usage:
                    usage["input_token_details"] = usage.pop("input_tokens_details")
                    usage["input_token_details"]["cache_read"] = usage[
                        "input_token_details"
                    ].pop("cached_tokens", 0)
                data["outputs"]["usage_metadata"] = usage

            data["invocation_params"] = {
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
            metadata = {
                k: v
                for k, v in response.items()
                if k
                not in (
                    {"output", "usage", "instructions"}.union(data["invocation_params"])
                )
            }
            metadata.update(
                {
                    "ls_model_name": data["invocation_params"].get("model"),
                    "ls_max_tokens": data["invocation_params"].get("max_output_tokens"),
                    "ls_temperature": data["invocation_params"].get("temperature"),
                    "ls_model_type": "chat",
                    "ls_provider": "openai",
                }
            )
            data["metadata"] = metadata

        return data

    def _extract_agent_span_data(span_data: tracing.AgentSpanData) -> dict[str, Any]:
        return {
            "invocation_params": {
                "tools": span_data.tools,
                "handoffs": span_data.handoffs,
            },
            "metadata": {
                "output_type": span_data.output_type,
            },
        }

    def _extract_handoff_span_data(
        span_data: tracing.HandoffSpanData,
    ) -> dict[str, Any]:
        return {
            "inputs": {
                "from_agent": span_data.from_agent,
                "to_agent": span_data.to_agent,
            }
        }

    def _extract_guardrail_span_data(
        span_data: tracing.GuardrailSpanData,
    ) -> dict[str, Any]:
        return {"metadata": {"triggered": span_data.triggered}}

    def _extract_custom_span_data(span_data: tracing.CustomSpanData) -> dict[str, Any]:
        return {"metadata": span_data.data}

    def extract_span_data(span: tracing.Span) -> dict[str, Any]:
        data: dict[str, Any] = {}

        if isinstance(span.span_data, tracing.FunctionSpanData):
            data.update(_extract_function_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.GenerationSpanData):
            data.update(_extract_generation_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.ResponseSpanData):
            data.update(_extract_response_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.AgentSpanData):
            data.update(_extract_agent_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.HandoffSpanData):
            data.update(_extract_handoff_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.GuardrailSpanData):
            data.update(_extract_guardrail_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.CustomSpanData):
            data.update(_extract_custom_span_data(span.span_data))
        else:
            return {}

        return data

    def ensure_dotted_order(
        start_time: Optional[datetime],
        run_id: Optional[str],
        parent_dotted_order: Optional[str] = None,
    ) -> str:
        """Create a dotted order from a start time and run id."""
        st = start_time or datetime.now(timezone.utc)
        id_ = run_id or str(uuid4())
        current_dotted_order = st.strftime("%Y%m%dT%H%M%S%fZ") + id_
        if parent_dotted_order is not None:
            return parent_dotted_order + "." + current_dotted_order
        return current_dotted_order
