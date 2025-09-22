import logging
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional, Union, cast

from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.base.response.schema import Response, StreamingResponse
from llama_index.core.instrumentation.event_handlers import BaseEventHandler
from llama_index.core.instrumentation.events import BaseEvent
from llama_index.core.instrumentation.events.agent import (
    AgentChatWithStepEndEvent,
    AgentChatWithStepStartEvent,
    AgentRunStepEndEvent,
    AgentRunStepStartEvent,
)
from llama_index.core.instrumentation.events.embedding import (
    EmbeddingEndEvent,
    EmbeddingStartEvent,
)
from llama_index.core.instrumentation.events.llm import (
    LLMChatEndEvent,
    LLMChatStartEvent,
)
from llama_index.core.instrumentation.events.query import QueryEndEvent, QueryStartEvent
from llama_index.core.instrumentation.events.retrieval import (
    RetrievalEndEvent,
    RetrievalStartEvent,
)
from llama_index.core.instrumentation.events.synthesis import SynthesizeEndEvent
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import PrivateAttr

from literalai.context import active_thread_var
from literalai.instrumentation.llamaindex.span_handler import LiteralSpanHandler
from literalai.observability.generation import (
    ChatGeneration,
    GenerationMessage,
    GenerationMessageRole,
)
from literalai.observability.step import Step, StepType

if TYPE_CHECKING:
    from literalai.client import LiteralClient


def convert_message_role(role: MessageRole) -> GenerationMessageRole:
    mapping = {
        MessageRole.SYSTEM: "system",
        MessageRole.USER: "user",
        MessageRole.ASSISTANT: "assistant",
        MessageRole.FUNCTION: "function",
        MessageRole.TOOL: "tool",
        MessageRole.CHATBOT: "assistant",
        MessageRole.MODEL: "assistant",
    }

    return cast(GenerationMessageRole, mapping.get(role, "user"))


def extract_query_from_bundle(str_or_query_bundle: Union[str, QueryBundle]):
    if isinstance(str_or_query_bundle, QueryBundle):
        return str_or_query_bundle.query_str

    return str_or_query_bundle


def extract_document_info(nodes: List[NodeWithScore]):
    if not nodes:
        return []

    return [
        {
            "id_": node.id_,
            "metadata": node.metadata,
            "text": node.get_text(),
            "mimetype": node.node.mimetype,
            "start_char_idx": node.node.start_char_idx,
            "end_char_idx": node.node.end_char_idx,
            "char_length": (
                node.node.end_char_idx - node.node.start_char_idx
                if node.node.end_char_idx is not None
                and node.node.start_char_idx is not None
                else None
            ),
            "score": node.get_score(),
        }
        for node in nodes
        if isinstance(node.node, TextNode)
    ]


def build_message_dict(message: ChatMessage):
    message_dict: GenerationMessage = {
        "role": convert_message_role(message.role),
        "content": message.content,
    }

    kwargs = message.additional_kwargs

    if kwargs:
        if kwargs.get("tool_call_id", None):
            message_dict["tool_call_id"] = kwargs.get("tool_call_id")
        if kwargs.get("name", None):
            message_dict["name"] = kwargs.get("name")
        tool_calls = kwargs.get("tool_calls", [])
        if len(tool_calls) > 0:
            message_dict["tool_calls"] = [
                tool_call.to_dict() for tool_call in tool_calls
            ]
    return message_dict


def create_generation(event: LLMChatStartEvent):
    model_dict = event.model_dict

    return ChatGeneration(
        provider=model_dict.get("class_name"),
        model=model_dict.get("model"),
        settings={
            "model": model_dict.get("model"),
            "temperature": model_dict.get("temperature"),
            "max_tokens": model_dict.get("max_tokens"),
            "logprobs": model_dict.get("logprobs"),
            "top_logprobs": model_dict.get("top_logprobs"),
        },
        messages=[build_message_dict(message) for message in event.messages],
    )


def extract_query(x: Union[str, QueryBundle]):
    return x.query_str if isinstance(x, QueryBundle) else x


class LiteralEventHandler(BaseEventHandler):
    """This class handles events coming from LlamaIndex."""

    _client: "LiteralClient" = PrivateAttr()
    _span_handler: "LiteralSpanHandler" = PrivateAttr()
    runs: Dict[str, List[Step]] = {}
    streaming_run_ids: List[str] = []
    _standalone_step_id: Optional[str] = None
    open_runs: List[Step] = []

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        literal_client: "LiteralClient",
        llama_index_span_handler: "LiteralSpanHandler",
    ):
        super().__init__()
        object.__setattr__(self, "_client", literal_client)
        object.__setattr__(self, "_span_handler", llama_index_span_handler)

    def _convert_message(self, message: ChatMessage):
        tool_calls = message.additional_kwargs.get("tool_calls")
        msg: GenerationMessage = {
            "name": getattr(message, "name", None),
            "role": convert_message_role(message.role),
            "content": message.content,
            "tool_calls": (
                [tool_call.to_dict() for tool_call in tool_calls]
                if tool_calls
                else None
            ),
        }

        return msg

    def handle(self, event: BaseEvent, **kwargs) -> None:
        """Logic for handling event."""
        try:
            thread_id = self._span_handler.get_thread_id(event.span_id)
            run_id = self._span_handler.get_run_id(event.span_id)

            # AgentChatWithStep wraps several AgentRunStep events
            # as the agent may want to perform multiple tool calls in a row.
            if isinstance(event, AgentChatWithStepStartEvent) or isinstance(
                event, AgentRunStepStartEvent
            ):
                run_name = (
                    "Agent Chat"
                    if isinstance(event, AgentChatWithStepStartEvent)
                    else "Agent Step"
                )
                parent_run_id = None
                if len(self.open_runs) > 0:
                    parent_run_id = self.open_runs[-1].id

                agent_run_id = str(uuid.uuid4())

                run = self._client.start_step(
                    name=run_name,
                    type="run",
                    id=agent_run_id,
                    parent_id=parent_run_id,
                )

                self.open_runs.append(run)

            if isinstance(event, AgentChatWithStepEndEvent) or isinstance(
                event, AgentRunStepEndEvent
            ):
                try:
                    step = self.open_runs.pop()
                except IndexError:
                    logging.error(
                        "[Literal] Error in Llamaindex instrumentation: AgentRunStepEndEvent called without an open run."
                    )
                if step:
                    step.end()

            if isinstance(event, QueryStartEvent):
                active_thread = active_thread_var.get()
                query = extract_query(event.query)

                if not active_thread or not active_thread.name:
                    self._client.api.upsert_thread(id=thread_id, name=query)

                self._client.message(
                    name="User query",
                    id=str(event.id_),
                    type="user_message",
                    thread_id=thread_id,
                    content=query,
                )

            # Retrieval wraps the Embedding step in LlamaIndex
            if isinstance(event, RetrievalStartEvent):
                run = self._client.start_step(
                    name="RAG",
                    type="run",
                    id=run_id,
                    thread_id=thread_id,
                )

                self.store_step(run_id=run_id, step=run)

                retrieval_step = self._client.start_step(
                    type="retrieval",
                    name="Retrieval",
                    parent_id=run_id,
                    thread_id=thread_id,
                )

                self.store_step(run_id=run_id, step=retrieval_step)

            if isinstance(event, EmbeddingStartEvent):
                retrieval_step = self.get_first_step_of_type(
                    run_id=run_id, step_type="retrieval"
                )

                if run_id and retrieval_step:
                    embedding_step = self._client.start_step(
                        type="embedding",
                        name="Embedding",
                        parent_id=retrieval_step.id,
                        thread_id=thread_id,
                    )
                    embedding_step.metadata = event.model_dict
                    self.store_step(run_id=run_id, step=embedding_step)

            if isinstance(event, EmbeddingEndEvent):
                embedding_step = self.get_first_step_of_type(
                    run_id=run_id, step_type="embedding"
                )

                if run_id and embedding_step:
                    embedding_step.input = {"query": event.chunks}
                    embedding_step.output = {"embeddings": event.embeddings}
                    embedding_step.end()

            if isinstance(event, RetrievalEndEvent):
                retrieval_step = self.get_first_step_of_type(
                    run_id=run_id, step_type="retrieval"
                )

                if run_id and retrieval_step:
                    retrieved_documents = extract_document_info(event.nodes)
                    query = extract_query(event.str_or_query_bundle)

                    retrieval_step.input = {"query": query}
                    retrieval_step.output = {"retrieved_documents": retrieved_documents}
                    retrieval_step.end()

            # Only event where we create LLM steps
            if isinstance(event, LLMChatStartEvent):
                if run_id:
                    self._client.step()
                    llm_step = self._client.start_step(
                        type="llm",
                        parent_id=run_id,
                        thread_id=thread_id,
                    )
                    self.store_step(run_id=run_id, step=llm_step)
                llm_step = self.get_first_step_of_type(run_id=run_id, step_type="llm")

                if not run_id and not llm_step:
                    self._standalone_step_id = str(uuid.uuid4())
                    llm_step = self._client.start_step(
                        name=event.model_dict.get("model", "LLM"),
                        type="llm",
                        id=self._standalone_step_id,
                        # Remove thread_id for standalone runs
                    )
                    self.store_step(run_id=self._standalone_step_id, step=llm_step)

                if llm_step:
                    generation = create_generation(event=event)
                    llm_step.generation = generation
                    llm_step.name = event.model_dict.get("model")

            # Actual creation of the event happens upon ending the event
            if isinstance(event, LLMChatEndEvent):
                llm_step = self.get_first_step_of_type(run_id=run_id, step_type="llm")
                if not llm_step and self._standalone_step_id:
                    llm_step = self.get_first_step_of_type(
                        run_id=self._standalone_step_id, step_type="llm"
                    )

                response = event.response

                if llm_step and response:
                    chat_completion = response.raw

                    # ChatCompletionChunk needed for chat stream methods
                    if isinstance(chat_completion, ChatCompletion) or isinstance(
                        chat_completion, ChatCompletionChunk
                    ):
                        usage = chat_completion.usage

                        if isinstance(usage, CompletionUsage):
                            llm_step.generation.input_token_count = usage.prompt_tokens
                            llm_step.generation.output_token_count = (
                                usage.completion_tokens
                            )

                        if self._standalone_step_id:
                            llm_step.generation.message_completion = (
                                self._convert_message(response.message)
                            )

                            llm_step.end()
                            self._standalone_step_id = None

            if isinstance(event, SynthesizeEndEvent):
                llm_step = self.get_first_step_of_type(run_id=run_id, step_type="llm")
                run = self.get_first_step_of_type(run_id=run_id, step_type="run")

                if llm_step and run:
                    synthesized_response = event.response
                    text_response = ""

                    if isinstance(synthesized_response, StreamingResponse):
                        text_response = str(synthesized_response.get_response())
                    if isinstance(synthesized_response, Response):
                        text_response = str(synthesized_response)

                    llm_step.generation.message_completion = {
                        "role": "assistant",
                        "content": text_response,
                    }

                    llm_step.end()
                    run.end()

                    self._client.message(
                        type="assistant_message",
                        thread_id=thread_id,
                        content=text_response,
                    )

            if isinstance(event, QueryEndEvent):
                if run_id in self.runs:
                    del self.runs[run_id]

        except Exception as e:
            logging.error(
                "[Literal] Error in Llamaindex instrumentation : %s",
                str(e),
                exc_info=True,
            )

    def store_step(self, run_id: str, step: Step):
        if run_id not in self.runs:
            self.runs[run_id] = []

        self.runs[run_id].append(step)

    def get_first_step_of_type(
        self, run_id: Optional[str], step_type: StepType
    ) -> Optional[Step]:
        if not run_id:
            return None

        if run_id not in self.runs:
            return None

        for step in self.runs[run_id]:
            if step.type == step_type:
                return step

        return None

    @classmethod
    def class_name(cls) -> str:
        """Class name."""
        return "LiteralEventHandler"
