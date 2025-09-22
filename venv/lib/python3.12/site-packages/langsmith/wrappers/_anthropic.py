from __future__ import annotations

import functools
import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    TypeVar,
    Union,
)

from pydantic import TypeAdapter
from typing_extensions import Self, TypedDict

from langsmith import client as ls_client
from langsmith import run_helpers
from langsmith.schemas import InputTokenDetails, UsageMetadata

if TYPE_CHECKING:
    import httpx
    from anthropic import Anthropic, AsyncAnthropic
    from anthropic.types import Completion, Message, MessageStreamEvent

C = TypeVar("C", bound=Union["Anthropic", "AsyncAnthropic", Any])
logger = logging.getLogger(__name__)


@functools.lru_cache
def _get_not_given() -> Optional[type]:
    try:
        from anthropic._types import NotGiven

        return NotGiven
    except ImportError:
        return None


def _strip_not_given(d: dict) -> dict:
    try:
        if (not_given := _get_not_given()) is not None:
            d = {k: v for k, v in d.items() if not isinstance(v, not_given)}
    except Exception as e:
        logger.error(f"Error stripping NotGiven: {e}")

    if "system" in d:
        d["messages"] = [{"role": "system", "content": d["system"]}] + d.get(
            "messages", []
        )
        d.pop("system")
    return {k: v for k, v in d.items() if v is not None}


def _infer_ls_params(kwargs: dict):
    stripped = _strip_not_given(kwargs)

    stop = stripped.get("stop")
    if stop and isinstance(stop, str):
        stop = [stop]

    return {
        "ls_provider": "anthropic",
        "ls_model_type": "chat",
        "ls_model_name": stripped.get("model", None),
        "ls_temperature": stripped.get("temperature", None),
        "ls_max_tokens": stripped.get("max_tokens", None),
        "ls_stop": stop,
    }


def _accumulate_event(
    *, event: MessageStreamEvent, current_snapshot: Message | None
) -> Message | None:
    try:
        from anthropic.types import ContentBlock
    except ImportError:
        logger.debug("Error importing ContentBlock")
        return current_snapshot

    if current_snapshot is None:
        if event.type == "message_start":
            return event.message

        raise RuntimeError(
            f'Unexpected event order, got {event.type} before "message_start"'
        )

    if event.type == "content_block_start":
        # TODO: check index <-- from anthropic SDK :)
        adapter: TypeAdapter = TypeAdapter(ContentBlock)
        content_block_instance = adapter.validate_python(
            event.content_block.model_dump()
        )
        current_snapshot.content.append(
            content_block_instance,  # type: ignore[attr-defined]
        )
    elif event.type == "content_block_delta":
        content = current_snapshot.content[event.index]
        if content.type == "text" and event.delta.type == "text_delta":
            content.text += event.delta.text
    elif event.type == "message_delta":
        current_snapshot.stop_reason = event.delta.stop_reason
        current_snapshot.stop_sequence = event.delta.stop_sequence
        current_snapshot.usage.output_tokens = event.usage.output_tokens

    return current_snapshot


def _reduce_chat_chunks(all_chunks: Sequence) -> dict:
    full_message = None
    for chunk in all_chunks:
        try:
            full_message = _accumulate_event(event=chunk, current_snapshot=full_message)
        except RuntimeError as e:
            logger.debug(f"Error accumulating event in Anthropic Wrapper: {e}")
            return {"output": all_chunks}
    if full_message is None:
        return {"output": all_chunks}
    d = full_message.model_dump()
    d["usage_metadata"] = _create_usage_metadata(d.pop("usage", {}))
    d.pop("type", None)
    return {"message": d}


def _create_usage_metadata(anthropic_token_usage: dict) -> UsageMetadata:
    input_tokens = anthropic_token_usage.get("input_tokens") or 0
    output_tokens = anthropic_token_usage.get("output_tokens") or 0
    total_tokens = input_tokens + output_tokens
    input_token_details: dict = {
        "cache_read": anthropic_token_usage.get("cache_creation_input_tokens", 0)
        + anthropic_token_usage.get("cache_read_input_tokens", 0)
    }
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_token_details=InputTokenDetails(
            **{k: v for k, v in input_token_details.items() if v is not None}
        ),
    )


def _reduce_completions(all_chunks: list[Completion]) -> dict:
    all_content = []
    for chunk in all_chunks:
        content = chunk.completion
        if content is not None:
            all_content.append(content)
    content = "".join(all_content)
    if all_chunks:
        d = all_chunks[-1].model_dump()
        d["choices"] = [{"text": content}]
    else:
        d = {"choices": [{"text": content}]}

    return d


def _process_chat_completion(outputs: Any):
    try:
        rdict = outputs.model_dump()
        anthropic_token_usage = rdict.pop("usage", None)
        rdict["usage_metadata"] = (
            _create_usage_metadata(anthropic_token_usage)
            if anthropic_token_usage
            else None
        )
        rdict.pop("type", None)
        return {"message": rdict}
    except BaseException as e:
        logger.debug(f"Error processing chat completion: {e}")
        return {"output": outputs}


def _get_wrapper(
    original_create: Callable,
    name: str,
    reduce_fn: Callable,
    tracing_extra: TracingExtra,
) -> Callable:
    @functools.wraps(original_create)
    def create(*args, **kwargs):
        stream = kwargs.get("stream")
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=reduce_fn if stream else None,
            process_inputs=_strip_not_given,
            process_outputs=_process_chat_completion,
            _invocation_params_fn=_infer_ls_params,
            **tracing_extra,
        )

        result = decorator(original_create)(*args, **kwargs)
        return result

    @functools.wraps(original_create)
    async def acreate(*args, **kwargs):
        stream = kwargs.get("stream")
        decorator = run_helpers.traceable(
            name=name,
            run_type="llm",
            reduce_fn=reduce_fn if stream else None,
            process_inputs=_strip_not_given,
            process_outputs=_process_chat_completion,
            _invocation_params_fn=_infer_ls_params,
            **tracing_extra,
        )
        result = await decorator(original_create)(*args, **kwargs)
        return result

    return acreate if run_helpers.is_async(original_create) else create


def _get_stream_wrapper(
    original_stream: Callable,
    name: str,
    tracing_extra: TracingExtra,
) -> Callable:
    """Create a wrapper for Anthropic's streaming context manager."""
    import anthropic

    is_async = "async" in str(original_stream).lower()
    configured_traceable = run_helpers.traceable(
        name=name,
        reduce_fn=_reduce_chat_chunks,
        run_type="llm",
        process_inputs=_strip_not_given,
        _invocation_params_fn=_infer_ls_params,
        **tracing_extra,
    )
    configured_traceable_text = run_helpers.traceable(
        name=name,
        run_type="llm",
        process_inputs=_strip_not_given,
        process_outputs=_process_chat_completion,
        _invocation_params_fn=_infer_ls_params,
        **tracing_extra,
    )

    if is_async:

        class AsyncMessageStreamWrapper:
            def __init__(
                self,
                wrapped: anthropic.lib.streaming._messages.AsyncMessageStream,
                **kwargs,
            ) -> None:
                self._wrapped = wrapped
                self._kwargs = kwargs

            @property
            def text_stream(self):
                @configured_traceable_text
                async def _text_stream(**_):
                    async for chunk in self._wrapped.text_stream:
                        yield chunk
                    run_tree = run_helpers.get_current_run_tree()
                    final_message = await self._wrapped.get_final_message()
                    run_tree.outputs = _process_chat_completion(final_message)

                return _text_stream(**self._kwargs)

            @property
            def response(self) -> httpx.Response:
                return self._wrapped.response

            @property
            def request_id(self) -> str | None:
                return self._wrapped.request_id

            async def __anext__(self) -> MessageStreamEvent:
                aiter = self.__aiter__()
                return await aiter.__anext__()

            async def __aiter__(self) -> AsyncIterator[MessageStreamEvent]:
                @configured_traceable
                def traced_iter(**_):
                    return self._wrapped.__aiter__()

                async for chunk in traced_iter(**self._kwargs):
                    yield chunk

            async def __aenter__(self) -> Self:
                await self._wrapped.__aenter__()
                return self

            async def __aexit__(self, *exc) -> None:
                await self._wrapped.__aexit__(*exc)

            async def close(self) -> None:
                await self._wrapped.close()

            async def get_final_message(self) -> Message:
                return await self._wrapped.get_final_message()

            async def get_final_text(self) -> str:
                return await self._wrapped.get_final_text()

            async def until_done(self) -> None:
                await self._wrapped.until_done()

            @property
            def current_message_snapshot(self) -> Message:
                return self._wrapped.current_message_snapshot

        class AsyncMessagesStreamManagerWrapper:
            def __init__(self, **kwargs):
                self._kwargs = kwargs

            async def __aenter__(self):
                self._manager = original_stream(**self._kwargs)
                stream = await self._manager.__aenter__()
                return AsyncMessageStreamWrapper(stream, **self._kwargs)

            async def __aexit__(self, *exc):
                await self._manager.__aexit__(*exc)

        return AsyncMessagesStreamManagerWrapper
    else:

        class MessageStreamWrapper:
            def __init__(
                self,
                wrapped: anthropic.lib.streaming._messages.MessageStream,
                **kwargs,
            ) -> None:
                self._wrapped = wrapped
                self._kwargs = kwargs

            @property
            def response(self) -> Any:
                return self._wrapped.response

            @property
            def request_id(self) -> str | None:
                return self._wrapped.request_id  # type: ignore[no-any-return]

            @property
            def text_stream(self):
                @configured_traceable_text
                def _text_stream(**_):
                    yield from self._wrapped.text_stream
                    run_tree = run_helpers.get_current_run_tree()
                    final_message = self._wrapped.get_final_message()
                    run_tree.outputs = _process_chat_completion(final_message)

                return _text_stream(**self._kwargs)

            def __next__(self) -> MessageStreamEvent:
                return self.__iter__().__next__()

            def __iter__(self):
                @configured_traceable
                def traced_iter(**_):
                    return self._wrapped.__iter__()

                return traced_iter(**self._kwargs)

            def __enter__(self) -> Self:
                self._wrapped.__enter__()
                return self

            def __exit__(self, *exc) -> None:
                self._wrapped.__exit__(*exc)

            def close(self) -> None:
                self._wrapped.close()

            def get_final_message(self) -> Message:
                return self._wrapped.get_final_message()

            def get_final_text(self) -> str:
                return self._wrapped.get_final_text()

            def until_done(self) -> None:
                return self._wrapped.until_done()

            @property
            def current_message_snapshot(self) -> Message:
                return self._wrapped.current_message_snapshot

        class MessagesStreamManagerWrapper:
            def __init__(self, **kwargs):
                self._kwargs = kwargs

            def __enter__(self):
                self._manager = original_stream(**self._kwargs)
                return MessageStreamWrapper(self._manager.__enter__(), **self._kwargs)

            def __exit__(self, *exc):
                self._manager.__exit__(*exc)

        return MessagesStreamManagerWrapper


class TracingExtra(TypedDict, total=False):
    metadata: Optional[Mapping[str, Any]]
    tags: Optional[list[str]]
    client: Optional[ls_client.Client]


def wrap_anthropic(client: C, *, tracing_extra: Optional[TracingExtra] = None) -> C:
    """Patch the Anthropic client to make it traceable.

    Args:
        client (Union[Anthropic, AsyncAnthropic]): The client to patch.
        tracing_extra (Optional[TracingExtra], optional): Extra tracing information.
            Defaults to None.

    Returns:
        Union[Anthropic, AsyncAnthropic]: The patched client.

    Example:

        .. code-block:: python

            import anthropic
            from langsmith import wrappers

            client = wrappers.wrap_anthropic(anthropic.Anthropic())

            # Use Anthropic client same as you normally would:
            system = "You are a helpful assistant."
            messages = [
                {
                    "role": "user",
                    "content": "What physics breakthroughs do you predict will happen by 2300?",
                }
            ]
            completion = client.messages.create(
                model="claude-3-5-sonnet-latest",
                messages=messages,
                max_tokens=1000,
                system=system,
            )
            print(completion.content)

            # You can also use the streaming context manager:
            with client.messages.stream(
                model="claude-3-5-sonnet-latest",
                messages=messages,
                max_tokens=1000,
                system=system,
            ) as stream:
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                message = stream.get_final_message()

    """  # noqa: E501
    tracing_extra = tracing_extra or {}
    client.messages.create = _get_wrapper(  # type: ignore[method-assign]
        client.messages.create,
        "ChatAnthropic",
        _reduce_chat_chunks,
        tracing_extra,
    )
    client.messages.stream = _get_stream_wrapper(  # type: ignore[method-assign]
        client.messages.stream,
        "ChatAnthropic",
        tracing_extra,
    )
    client.completions.create = _get_wrapper(  # type: ignore[method-assign]
        client.completions.create,
        "Anthropic",
        _reduce_completions,
        tracing_extra,
    )

    if (
        hasattr(client, "beta")
        and hasattr(client.beta, "messages")
        and hasattr(client.beta.messages, "create")
    ):
        client.beta.messages.create = _get_wrapper(  # type: ignore[method-assign]
            client.beta.messages.create,  # type: ignore
            "ChatAnthropic",
            _reduce_chat_chunks,
            tracing_extra,
        )
    return client
