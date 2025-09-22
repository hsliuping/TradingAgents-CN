from typing import Any, Dict, List, Optional

from literalai import ChatGeneration, CompletionGeneration, GenerationMessage
from llama_index.core.callbacks import TokenCountingHandler
from llama_index.core.callbacks.schema import CBEventType, EventPayload
from llama_index.core.llms import ChatMessage, ChatResponse, CompletionResponse
from llama_index.core.tools.types import ToolMetadata

from chainlit.context import context_var
from chainlit.element import Text
from chainlit.step import Step, StepType
from chainlit.utils import utc_now

DEFAULT_IGNORE = [
    CBEventType.CHUNKING,
    CBEventType.SYNTHESIZE,
    CBEventType.EMBEDDING,
    CBEventType.NODE_PARSING,
    CBEventType.TREE,
]


class LlamaIndexCallbackHandler(TokenCountingHandler):
    """Base callback handler that can be used to track event starts and ends."""

    steps: Dict[str, Step]

    def __init__(
        self,
        event_starts_to_ignore: List[CBEventType] = DEFAULT_IGNORE,
        event_ends_to_ignore: List[CBEventType] = DEFAULT_IGNORE,
    ) -> None:
        """Initialize the base callback handler."""
        super().__init__(
            event_starts_to_ignore=event_starts_to_ignore,
            event_ends_to_ignore=event_ends_to_ignore,
        )

        self.steps = {}

    def _get_parent_id(self, event_parent_id: Optional[str] = None) -> Optional[str]:
        if event_parent_id and event_parent_id in self.steps:
            return event_parent_id
        elif context_var.get().current_step:
            return context_var.get().current_step.id
        else:
            return None

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Run when an event starts and return id of event."""
        step_type: StepType = "undefined"
        step_name: str = event_type.value
        step_input: Optional[Dict[str, Any]] = payload
        if event_type == CBEventType.FUNCTION_CALL:
            step_type = "tool"
            if payload:
                metadata: Optional[ToolMetadata] = payload.get(EventPayload.TOOL)
                if metadata:
                    step_name = getattr(metadata, "name", step_name)
                step_input = payload.get(EventPayload.FUNCTION_CALL)
        elif event_type == CBEventType.RETRIEVE:
            step_type = "tool"
        elif event_type == CBEventType.QUERY:
            step_type = "tool"
        elif event_type == CBEventType.LLM:
            step_type = "llm"
        else:
            return event_id

        step = Step(
            name=step_name,
            type=step_type,
            parent_id=self._get_parent_id(parent_id),
            id=event_id,
        )

        self.steps[event_id] = step
        step.start = utc_now()
        step.input = step_input or {}
        context_var.get().loop.create_task(step.send())
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Run when an event ends."""
        step = self.steps.get(event_id, None)

        if payload is None or step is None:
            return

        step.end = utc_now()

        if event_type == CBEventType.FUNCTION_CALL:
            response = payload.get(EventPayload.FUNCTION_OUTPUT)
            if response:
                step.output = f"{response}"
                context_var.get().loop.create_task(step.update())

        elif event_type == CBEventType.QUERY:
            response = payload.get(EventPayload.RESPONSE)
            source_nodes = getattr(response, "source_nodes", None)
            if source_nodes:
                source_refs = ", ".join(
                    [f"Source {idx}" for idx, _ in enumerate(source_nodes)]
                )
                step.elements = [
                    Text(
                        name=f"Source {idx}",
                        content=source.text or "Empty node",
                        display="side",
                    )
                    for idx, source in enumerate(source_nodes)
                ]
                step.output = f"Retrieved the following sources: {source_refs}"
                context_var.get().loop.create_task(step.update())

        elif event_type == CBEventType.RETRIEVE:
            sources = payload.get(EventPayload.NODES)
            if sources:
                source_refs = ", ".join(
                    [f"Source {idx}" for idx, _ in enumerate(sources)]
                )
                step.elements = [
                    Text(
                        name=f"Source {idx}",
                        display="side",
                        content=source.node.get_text() or "Empty node",
                    )
                    for idx, source in enumerate(sources)
                ]
                step.output = f"Retrieved the following sources: {source_refs}"
            context_var.get().loop.create_task(step.update())

        elif event_type == CBEventType.LLM:
            formatted_messages = payload.get(EventPayload.MESSAGES)  # type: Optional[List[ChatMessage]]
            formatted_prompt = payload.get(EventPayload.PROMPT)
            response = payload.get(EventPayload.RESPONSE)

            if formatted_messages:
                messages = [
                    GenerationMessage(
                        role=m.role.value,  # type: ignore
                        content=m.content or "",
                    )
                    for m in formatted_messages
                ]
            else:
                messages = None

            if isinstance(response, ChatResponse):
                content = response.message.content or ""
            elif isinstance(response, CompletionResponse):
                content = response.text
            else:
                content = ""

            step.output = content

            token_count = self.total_llm_token_count or None
            raw_response = response.raw if response else None
            model = getattr(raw_response, "model", None)

            if messages and isinstance(response, ChatResponse):
                msg: ChatMessage = response.message
                step.generation = ChatGeneration(
                    model=model,
                    messages=messages,
                    message_completion=GenerationMessage(
                        role=msg.role.value,  # type: ignore
                        content=content,
                    ),
                    token_count=token_count,
                )
            elif formatted_prompt:
                step.generation = CompletionGeneration(
                    model=model,
                    prompt=formatted_prompt,
                    completion=content,
                    token_count=token_count,
                )

            context_var.get().loop.create_task(step.update())

        else:
            step.output = payload
            context_var.get().loop.create_task(step.update())

        self.steps.pop(event_id, None)

    def _noop(self, *args, **kwargs):
        pass

    start_trace = _noop
    end_trace = _noop
