import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypedDict, Union
from uuid import UUID

import pydantic
from langchain.callbacks.tracers.schemas import Run
from langchain.schema import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk
from langchain_core.tracers.base import AsyncBaseTracer
from literalai import ChatGeneration, CompletionGeneration, GenerationMessage
from literalai.observability.step import TrueStepType

from chainlit.context import context_var
from chainlit.message import Message
from chainlit.step import Step
from chainlit.utils import utc_now

DEFAULT_ANSWER_PREFIX_TOKENS = ["Final", "Answer", ":"]


class FinalStreamHelper:
    # The stream we can use to stream the final answer from a chain
    final_stream: Union[Message, None]
    # Should we stream the final answer?
    stream_final_answer: bool = False
    # Token sequence that prefixes the answer
    answer_prefix_tokens: List[str]
    # Ignore white spaces and new lines when comparing answer_prefix_tokens to last tokens? (to determine if answer has been reached)
    strip_tokens: bool

    answer_reached: bool

    def __init__(
        self,
        answer_prefix_tokens: Optional[List[str]] = None,
        stream_final_answer: bool = False,
        force_stream_final_answer: bool = False,
        strip_tokens: bool = True,
    ) -> None:
        # Langchain final answer streaming logic
        if answer_prefix_tokens is None:
            self.answer_prefix_tokens = DEFAULT_ANSWER_PREFIX_TOKENS
        else:
            self.answer_prefix_tokens = answer_prefix_tokens
        if strip_tokens:
            self.answer_prefix_tokens_stripped = [
                token.strip() for token in self.answer_prefix_tokens
            ]
        else:
            self.answer_prefix_tokens_stripped = self.answer_prefix_tokens

        self.last_tokens = [""] * len(self.answer_prefix_tokens)
        self.last_tokens_stripped = [""] * len(self.answer_prefix_tokens)
        self.strip_tokens = strip_tokens
        self.answer_reached = force_stream_final_answer

        # Our own final answer streaming logic
        self.stream_final_answer = stream_final_answer
        self.final_stream = None
        self.has_streamed_final_answer = False

    def _check_if_answer_reached(self) -> bool:
        if self.strip_tokens:
            return self._compare_last_tokens(self.last_tokens_stripped)
        else:
            return self._compare_last_tokens(self.last_tokens)

    def _compare_last_tokens(self, last_tokens: List[str]):
        if last_tokens == self.answer_prefix_tokens_stripped:
            # If tokens match perfectly we are done
            return True
        else:
            # Some LLMs will consider all the tokens of the final answer as one token
            # so we check if any last token contains all answer tokens
            return any(
                [
                    all(
                        answer_token in last_token
                        for answer_token in self.answer_prefix_tokens_stripped
                    )
                    for last_token in last_tokens
                ]
            )

    def _append_to_last_tokens(self, token: str) -> None:
        self.last_tokens.append(token)
        self.last_tokens_stripped.append(token.strip())
        if len(self.last_tokens) > len(self.answer_prefix_tokens):
            self.last_tokens.pop(0)
            self.last_tokens_stripped.pop(0)


class ChatGenerationStart(TypedDict):
    input_messages: List[BaseMessage]
    start: float
    token_count: int
    tt_first_token: Optional[float]


class CompletionGenerationStart(TypedDict):
    prompt: str
    start: float
    token_count: int
    tt_first_token: Optional[float]


class GenerationHelper:
    chat_generations: Dict[str, ChatGenerationStart]
    completion_generations: Dict[str, CompletionGenerationStart]
    generation_inputs: Dict[str, Dict]

    def __init__(self) -> None:
        self.chat_generations = {}
        self.completion_generations = {}
        self.generation_inputs = {}

    def ensure_values_serializable(self, data):
        """
        Recursively ensures that all values in the input (dict or list) are JSON serializable.
        """
        if isinstance(data, dict):
            return {
                key: self.ensure_values_serializable(value)
                for key, value in data.items()
            }
        elif isinstance(data, pydantic.BaseModel):
            # Fallback to support pydantic v1
            # https://docs.pydantic.dev/latest/migration/#changes-to-pydanticbasemodel
            if pydantic.VERSION.startswith("1"):
                return data.dict()

            # pydantic v2
            return data.model_dump()  # pyright: ignore reportAttributeAccessIssue
        elif isinstance(data, list):
            return [self.ensure_values_serializable(item) for item in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        elif isinstance(data, (tuple, set)):
            return list(data)  # Convert tuples and sets to lists
        else:
            return str(data)  # Fallback: convert other types to string

    def _convert_message_role(self, role: str):
        if "human" in role.lower():
            return "user"
        elif "system" in role.lower():
            return "system"
        elif "function" in role.lower():
            return "function"
        elif "tool" in role.lower():
            return "tool"
        else:
            return "assistant"

    def _convert_message_dict(
        self,
        message: Dict,
    ):
        class_name = message["id"][-1]
        kwargs = message.get("kwargs", {})
        function_call = kwargs.get("additional_kwargs", {}).get("function_call")

        msg = GenerationMessage(
            role=self._convert_message_role(class_name),
            content="",
        )
        if name := kwargs.get("name"):
            msg["name"] = name
        if function_call:
            msg["function_call"] = function_call
        else:
            content = kwargs.get("content")
            if isinstance(content, list):
                tool_calls = []
                content_parts = []
                for item in content:
                    if item.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "id": item.get("id"),
                                "type": "function",
                                "function": {
                                    "name": item.get("name"),
                                    "arguments": item.get("input"),
                                },
                            }
                        )
                    elif item.get("type") == "text":
                        content_parts.append({"type": "text", "text": item.get("text")})

                if tool_calls:
                    msg["tool_calls"] = tool_calls
                if content_parts:
                    msg["content"] = content_parts  # type: ignore
            else:
                msg["content"] = content  # type: ignore

        return msg

    def _convert_message(
        self,
        message: Union[Dict, BaseMessage],
    ):
        if isinstance(message, dict):
            return self._convert_message_dict(
                message,
            )

        function_call = message.additional_kwargs.get("function_call")

        msg = GenerationMessage(
            role=self._convert_message_role(message.type),
            content="",
        )

        if literal_uuid := message.additional_kwargs.get("uuid"):
            msg["uuid"] = literal_uuid
            msg["templated"] = True

        if name := getattr(message, "name", None):
            msg["name"] = name

        if function_call:
            msg["function_call"] = function_call
        else:
            if isinstance(message.content, list):
                tool_calls = []
                content_parts = []
                for item in message.content:
                    if isinstance(item, str):
                        continue
                    if item.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "id": item.get("id"),
                                "type": "function",
                                "function": {
                                    "name": item.get("name"),
                                    "arguments": item.get("input"),
                                },
                            }
                        )
                    elif item.get("type") == "text":
                        content_parts.append({"type": "text", "text": item.get("text")})

                if tool_calls:
                    msg["tool_calls"] = tool_calls
                if content_parts:
                    msg["content"] = content_parts  # type: ignore
            else:
                msg["content"] = message.content  # type: ignore

        return msg

    def _build_llm_settings(
        self,
        serialized: Dict,
        invocation_params: Optional[Dict] = None,
    ):
        # invocation_params = run.extra.get("invocation_params")
        if invocation_params is None:
            return None, None

        provider = invocation_params.pop("_type", "")  # type: str

        model_kwargs = invocation_params.pop("model_kwargs", {})

        if model_kwargs is None:
            model_kwargs = {}

        merged = {
            **invocation_params,
            **model_kwargs,
            **serialized.get("kwargs", {}),
        }

        # make sure there is no api key specification
        settings = {k: v for k, v in merged.items() if not k.endswith("_api_key")}

        model_keys = ["azure_deployment", "deployment_name", "model", "model_name"]
        model = next((settings[k] for k in model_keys if k in settings), None)
        if isinstance(model, str):
            model = model.replace("models/", "")
        tools = None
        if "functions" in settings:
            tools = [{"type": "function", "function": f} for f in settings["functions"]]
        if "tools" in settings:
            tools = [
                {"type": "function", "function": t}
                if t.get("type") != "function"
                else t
                for t in settings["tools"]
            ]
        return provider, model, tools, settings


def process_content(content: Any) -> Tuple[Dict, Optional[str]]:
    if content is None:
        return {}, None
    if isinstance(content, dict):
        return content, "json"
    elif isinstance(content, str):
        return {"content": content}, "text"
    else:
        return {"content": str(content)}, "text"


DEFAULT_TO_IGNORE = [
    "RunnableSequence",
    "RunnableParallel",
    "RunnableAssign",
    "RunnableLambda",
    "<lambda>",
]
DEFAULT_TO_KEEP = ["retriever", "llm", "agent", "chain", "tool"]


class LangchainTracer(AsyncBaseTracer, GenerationHelper, FinalStreamHelper):
    steps: Dict[str, Step]
    parent_id_map: Dict[str, str]
    ignored_runs: set

    def __init__(
        self,
        # Token sequence that prefixes the answer
        answer_prefix_tokens: Optional[List[str]] = None,
        # Should we stream the final answer?
        stream_final_answer: bool = False,
        # Should force stream the first response?
        force_stream_final_answer: bool = False,
        # Runs to ignore to enhance readability
        to_ignore: Optional[List[str]] = None,
        # Runs to keep within ignored runs
        to_keep: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        AsyncBaseTracer.__init__(self, **kwargs)
        GenerationHelper.__init__(self)
        FinalStreamHelper.__init__(
            self,
            answer_prefix_tokens=answer_prefix_tokens,
            stream_final_answer=stream_final_answer,
            force_stream_final_answer=force_stream_final_answer,
        )
        self.context = context_var.get()
        self.steps = {}
        self.parent_id_map = {}
        self.ignored_runs = set()

        if self.context.current_step:
            self.root_parent_id = self.context.current_step.id
        else:
            self.root_parent_id = None

        if to_ignore is None:
            self.to_ignore = DEFAULT_TO_IGNORE
        else:
            self.to_ignore = to_ignore

        if to_keep is None:
            self.to_keep = DEFAULT_TO_KEEP
        else:
            self.to_keep = to_keep

    async def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: "UUID",
        parent_run_id: Optional["UUID"] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> Run:
        lc_messages = messages[0]
        self.chat_generations[str(run_id)] = {
            "input_messages": lc_messages,
            "start": time.time(),
            "token_count": 0,
            "tt_first_token": None,
        }

        return await super().on_chat_model_start(
            serialized,
            messages,
            run_id=run_id,
            parent_run_id=parent_run_id,
            tags=tags,
            metadata=metadata,
            name=name,
            **kwargs,
        )

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: "UUID",
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        await super().on_llm_start(
            serialized,
            prompts,
            run_id=run_id,
            parent_run_id=parent_run_id,
            tags=tags,
            metadata=metadata,
            **kwargs,
        )

        self.completion_generations[str(run_id)] = {
            "prompt": prompts[0],
            "start": time.time(),
            "token_count": 0,
            "tt_first_token": None,
        }

        return None

    async def on_llm_new_token(
        self,
        token: str,
        *,
        chunk: Optional[Union[GenerationChunk, ChatGenerationChunk]] = None,
        run_id: "UUID",
        parent_run_id: Optional["UUID"] = None,
        **kwargs: Any,
    ) -> None:
        await super().on_llm_new_token(
            token=token,
            chunk=chunk,
            run_id=run_id,
            parent_run_id=parent_run_id,
            **kwargs,
        )
        if isinstance(chunk, ChatGenerationChunk):
            start = self.chat_generations[str(run_id)]
        else:
            start = self.completion_generations[str(run_id)]  # type: ignore
        start["token_count"] += 1
        if start["tt_first_token"] is None:
            start["tt_first_token"] = (time.time() - start["start"]) * 1000

        # Process token to ensure it's a string, as strip() will be called on it.
        processed_token: str
        # Handle case where token is a list (can occur with some model outputs).
        # Join all elements into a single string to maintain compatibility with downstream processing.
        if isinstance(token, list):
            # If token is a list, join its elements (converted to strings) into a single string.
            processed_token = "".join(map(str, token))
        elif not isinstance(token, str):
            # If token is neither a list nor a string, convert it to a string.
            processed_token = str(token)
        else:
            # If token is already a string, use it as is.
            processed_token = token

        if self.stream_final_answer:
            self._append_to_last_tokens(processed_token)

            if self.answer_reached:
                if not self.final_stream:
                    self.final_stream = Message(content="")
                    await self.final_stream.send()
                await self.final_stream.stream_token(processed_token)
                self.has_streamed_final_answer = True
            else:
                self.answer_reached = self._check_if_answer_reached()

    async def _persist_run(self, run: Run) -> None:
        pass

    def _get_run_parent_id(self, run: Run):
        parent_id = str(run.parent_run_id) if run.parent_run_id else self.root_parent_id

        return parent_id

    def _get_non_ignored_parent_id(self, current_parent_id: Optional[str] = None):
        if not current_parent_id:
            return self.root_parent_id

        if current_parent_id not in self.parent_id_map:
            return None

        while current_parent_id in self.parent_id_map:
            # If the parent id is in the ignored runs, we need to get the parent id of the ignored run
            if current_parent_id in self.ignored_runs:
                current_parent_id = self.parent_id_map[current_parent_id]
            else:
                return current_parent_id

        return self.root_parent_id

    def _should_ignore_run(self, run: Run):
        parent_id = self._get_run_parent_id(run)

        if parent_id:
            # Add the parent id of the ignored run in the mapping
            # so we can re-attach a kept child to the right parent id
            self.parent_id_map[str(run.id)] = parent_id

        ignore_by_name = False
        ignore_by_parent = parent_id in self.ignored_runs

        for filter in self.to_ignore:
            if filter in run.name:
                ignore_by_name = True
                break

        ignore = ignore_by_name or ignore_by_parent

        # If the ignore cause is the parent being ignored, check if we should nonetheless keep the child
        if ignore_by_parent and not ignore_by_name and run.run_type in self.to_keep:
            return False, self._get_non_ignored_parent_id(parent_id)
        else:
            if ignore:
                # Tag the run as ignored
                self.ignored_runs.add(str(run.id))
            return ignore, parent_id

    async def _start_trace(self, run: Run) -> None:
        await super()._start_trace(run)
        context_var.set(self.context)

        ignore, parent_id = self._should_ignore_run(run)

        if run.run_type in ["chain", "prompt"]:
            self.generation_inputs[str(run.id)] = self.ensure_values_serializable(
                run.inputs
            )

        if ignore:
            return

        step_type: TrueStepType = "undefined"
        if run.run_type == "agent":
            step_type = "run"
        elif run.run_type == "chain":
            if not self.steps:
                step_type = "run"
        elif run.run_type == "llm":
            step_type = "llm"
        elif run.run_type == "retriever":
            step_type = "tool"
        elif run.run_type == "tool":
            step_type = "tool"
        elif run.run_type == "embedding":
            step_type = "embedding"

        step = Step(
            id=str(run.id),
            name=run.name,
            type=step_type,
            parent_id=parent_id,
        )
        step.start = utc_now()
        if step.metadata is None:
            step.metadata = {}
        if step_type != "llm":
            step.input, language = process_content(run.inputs)
            if language is not None:
                step.metadata["language"] = language

        step.tags = run.tags
        self.steps[str(run.id)] = step

        await step.send()

    async def _on_run_update(self, run: Run) -> None:
        """Process a run upon update."""
        context_var.set(self.context)

        ignore, parent_id = self._should_ignore_run(run)

        if ignore:
            return

        current_step = self.steps.get(str(run.id), None)

        if run.run_type == "llm" and current_step:
            provider, model, tools, llm_settings = self._build_llm_settings(
                (run.serialized or {}), (run.extra or {}).get("invocation_params")
            )
            generations = (run.outputs or {}).get("generations", [])
            generation = generations[0][0]
            variables = self.generation_inputs.get(str(run.parent_run_id), {})
            variables = {k: str(v) for k, v in variables.items() if v is not None}
            if message := generation.get("message"):
                chat_start = self.chat_generations[str(run.id)]
                duration = time.time() - chat_start["start"]
                if duration and chat_start["token_count"]:
                    throughput = chat_start["token_count"] / duration
                else:
                    throughput = None
                message_completion = self._convert_message(message)
                current_step.generation = ChatGeneration(
                    provider=provider,
                    model=model,
                    tools=tools,
                    variables=variables,
                    settings=llm_settings,
                    duration=duration,
                    token_throughput_in_s=throughput,
                    tt_first_token=chat_start.get("tt_first_token"),
                    messages=[
                        self._convert_message(m) for m in chat_start["input_messages"]
                    ],
                    message_completion=message_completion,
                )

                # find first message with prompt_id
                for m in chat_start["input_messages"]:
                    if m.additional_kwargs.get("prompt_id"):
                        current_step.generation.prompt_id = m.additional_kwargs[
                            "prompt_id"
                        ]
                        if custom_variables := m.additional_kwargs.get("variables"):
                            current_step.generation.variables = {
                                k: str(v)
                                for k, v in custom_variables.items()
                                if v is not None
                            }
                    break

                current_step.language = "json"
            else:
                completion_start = self.completion_generations[str(run.id)]
                completion = generation.get("text", "")
                duration = time.time() - completion_start["start"]
                if duration and completion_start["token_count"]:
                    throughput = completion_start["token_count"] / duration
                else:
                    throughput = None
                current_step.generation = CompletionGeneration(
                    provider=provider,
                    model=model,
                    settings=llm_settings,
                    variables=variables,
                    duration=duration,
                    token_throughput_in_s=throughput,
                    tt_first_token=completion_start.get("tt_first_token"),
                    prompt=completion_start["prompt"],
                    completion=completion,
                )
                current_step.output = completion

            if current_step:
                current_step.end = utc_now()
                await current_step.update()

            if self.final_stream and self.has_streamed_final_answer:
                await self.final_stream.update()

            return

        outputs = run.outputs or {}
        output_keys = list(outputs.keys())
        output = outputs

        if output_keys:
            output = outputs.get(output_keys[0], outputs)

        if current_step:
            if current_step.type != "llm":
                current_step.output = (
                    output[0]
                    if isinstance(output, Sequence)
                    and not isinstance(output, str)
                    and len(output)
                    else output
                )
            current_step.end = utc_now()
            await current_step.update()

    async def _on_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any):
        context_var.set(self.context)

        if current_step := self.steps.get(str(run_id), None):
            current_step.is_error = True
            current_step.output = str(error)
            current_step.end = utc_now()
            await current_step.update()

    on_llm_error = _on_error
    on_chain_error = _on_error
    on_tool_error = _on_error
    on_retriever_error = _on_error


LangchainCallbackHandler = LangchainTracer
AsyncLangchainCallbackHandler = LangchainTracer
