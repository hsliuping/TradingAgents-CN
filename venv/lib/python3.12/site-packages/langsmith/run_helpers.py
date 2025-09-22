"""Decorator for creating a run tree from functions."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import datetime
import functools
import inspect
import logging
import uuid
import warnings
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Generator,
    Iterator,
    Mapping,
    Sequence,
)
from contextvars import copy_context
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Generic,
    Literal,
    Optional,
    Protocol,
    TypedDict,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from typing_extensions import ParamSpec, TypeGuard, get_args, get_origin

from langsmith import client as ls_client
from langsmith import run_trees, schemas, utils
from langsmith._internal import _aiter as aitertools
from langsmith.env import _runtime_env

if TYPE_CHECKING:
    from types import TracebackType

    from langchain_core.runnables import Runnable

LOGGER = logging.getLogger(__name__)
_PARENT_RUN_TREE = contextvars.ContextVar[Optional[run_trees.RunTree]](
    "_PARENT_RUN_TREE", default=None
)
_PROJECT_NAME = contextvars.ContextVar[Optional[str]]("_PROJECT_NAME", default=None)
_TAGS = contextvars.ContextVar[Optional[list[str]]]("_TAGS", default=None)
_METADATA = contextvars.ContextVar[Optional[dict[str, Any]]]("_METADATA", default=None)


_TRACING_ENABLED = contextvars.ContextVar[Optional[Union[bool, Literal["local"]]]](
    "_TRACING_ENABLED", default=None
)
_CLIENT = contextvars.ContextVar[Optional[ls_client.Client]]("_CLIENT", default=None)
_CONTEXT_KEYS: dict[str, contextvars.ContextVar] = {
    "parent": _PARENT_RUN_TREE,
    "project_name": _PROJECT_NAME,
    "tags": _TAGS,
    "metadata": _METADATA,
    "enabled": _TRACING_ENABLED,
    "client": _CLIENT,
    "replicas": run_trees._REPLICAS,
}

_EXCLUDED_FRAME_FNAME = "langsmith/run_helpers.py"

_OTEL_AVAILABLE: Optional[bool] = None


def get_current_run_tree() -> Optional[run_trees.RunTree]:
    """Get the current run tree."""
    return _PARENT_RUN_TREE.get()


def get_tracing_context(
    context: Optional[contextvars.Context] = None,
) -> dict[str, Any]:
    """Get the current tracing context."""
    if context is None:
        return {
            "parent": _PARENT_RUN_TREE.get(),
            "project_name": _PROJECT_NAME.get(),
            "tags": _TAGS.get(),
            "metadata": _METADATA.get(),
            "enabled": _TRACING_ENABLED.get(),
            "client": _CLIENT.get(),
        }
    return {k: context.get(v) for k, v in _CONTEXT_KEYS.items()}


@contextlib.contextmanager
def tracing_context(
    *,
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    parent: Optional[Union[run_trees.RunTree, Mapping, str, Literal[False]]] = None,
    enabled: Optional[Union[bool, Literal["local"]]] = None,
    client: Optional[ls_client.Client] = None,
    replicas: Optional[Sequence[tuple[str, Optional[dict]]]] = None,
    **kwargs: Any,
) -> Generator[None, None, None]:
    """Set the tracing context for a block of code.

    Args:
        project_name: The name of the project to log the run to. Defaults to None.
        tags: The tags to add to the run. Defaults to None.
        metadata: The metadata to add to the run. Defaults to None.
        parent: The parent run to use for the context. Can be a Run/RunTree object,
            request headers (for distributed tracing), or the dotted order string.
            Defaults to None.
        client: The client to use for logging the run to LangSmith. Defaults to None,
        enabled: Whether tracing is enabled. Defaults to None, meaning it will use the
            current context value or environment variables.
        replicas: A sequence of tuples containing project names and optional updates for each replica.
            Example: [("my_experiment", {"reference_example_id": None}), ("my_project", None)]
    """
    if kwargs:
        # warn
        warnings.warn(
            f"Unrecognized keyword arguments: {kwargs}.",
            DeprecationWarning,
        )
    current_context = get_tracing_context()
    parent_run = (
        _get_parent_run({"parent": parent or kwargs.get("parent_run")})
        if parent is not False
        else None
    )
    if parent_run is not None:
        tags = sorted(set(tags or []) | set(parent_run.tags or []))
        metadata = {**parent_run.metadata, **(metadata or {})}
    enabled = enabled if enabled is not None else current_context.get("enabled")
    _set_tracing_context(
        {
            "parent": parent_run,
            "project_name": project_name,
            "tags": tags,
            "metadata": metadata,
            "enabled": enabled,
            "client": client,
            "replicas": replicas,
        }
    )
    try:
        yield
    finally:
        _set_tracing_context(current_context)


# Alias for backwards compatibility
get_run_tree_context = get_current_run_tree


def is_traceable_function(func: Any) -> TypeGuard[SupportsLangsmithExtra[P, R]]:
    """Check if a function is @traceable decorated."""
    return (
        _is_traceable_function(func)
        or (isinstance(func, functools.partial) and _is_traceable_function(func.func))
        or (hasattr(func, "__call__") and _is_traceable_function(func.__call__))
    )


def ensure_traceable(
    func: Callable[P, R],
    *,
    name: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    tags: Optional[list[str]] = None,
    client: Optional[ls_client.Client] = None,
    reduce_fn: Optional[Callable[[Sequence], dict]] = None,
    project_name: Optional[str] = None,
    process_inputs: Optional[Callable[[dict], dict]] = None,
    process_outputs: Optional[Callable[..., dict]] = None,
    process_chunk: Optional[Callable] = None,
) -> SupportsLangsmithExtra[P, R]:
    """Ensure that a function is traceable."""
    if is_traceable_function(func):
        return func
    return traceable(
        name=name,
        metadata=metadata,
        tags=tags,
        client=client,
        reduce_fn=reduce_fn,
        project_name=project_name,
        process_inputs=process_inputs,
        process_outputs=process_outputs,
        process_chunk=process_chunk,
    )(func)


def is_async(func: Callable) -> bool:
    """Inspect function or wrapped function to see if it is async."""
    return inspect.iscoroutinefunction(func) or (
        hasattr(func, "__wrapped__") and inspect.iscoroutinefunction(func.__wrapped__)
    )


class LangSmithExtra(TypedDict, total=False):
    """Any additional info to be injected into the run dynamically."""

    name: Optional[str]
    """Optional name for the run."""
    reference_example_id: Optional[ls_client.ID_TYPE]
    """Optional ID of a reference example."""
    run_extra: Optional[dict]
    """Optional additional run information."""
    parent: Optional[Union[run_trees.RunTree, str, Mapping]]
    """Optional parent run, can be a RunTree, string, or mapping."""
    run_tree: Optional[run_trees.RunTree]  # TODO: Deprecate
    """Optional run tree (deprecated)."""
    project_name: Optional[str]
    """Optional name of the project."""
    metadata: Optional[dict[str, Any]]
    """Optional metadata for the run."""
    tags: Optional[list[str]]
    """Optional list of tags for the run."""
    run_id: Optional[ls_client.ID_TYPE]
    """Optional ID for the run."""
    client: Optional[ls_client.Client]
    """Optional LangSmith client."""
    # Optional callback function to be called if the run succeeds and before it is sent.
    _on_success: Optional[Callable[[run_trees.RunTree], None]]
    on_end: Optional[Callable[[run_trees.RunTree], Any]]
    """Optional callback function to be called after the run ends and is sent."""


R = TypeVar("R", covariant=True)
P = ParamSpec("P")


@runtime_checkable
class SupportsLangsmithExtra(Protocol, Generic[P, R]):
    """Implementations of this Protocol accept an optional langsmith_extra parameter.

    Args:
        *args: Variable length arguments.
        langsmith_extra (Optional[LangSmithExtra): Optional dictionary of
            additional parameters for Langsmith.
        **kwargs: Keyword arguments.

    Returns:
        R: The return type of the callable.
    """

    def __call__(  # type: ignore[valid-type]
        self,
        *args: P.args,
        langsmith_extra: Optional[LangSmithExtra] = None,
        **kwargs: P.kwargs,
    ) -> R:
        """Call the instance when it is called as a function.

        Args:
            *args: Variable length argument list.
            langsmith_extra: Optional dictionary containing additional
                parameters specific to Langsmith.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            R: The return value of the method.

        """
        ...


def _extract_usage(
    *,
    run_tree: run_trees.RunTree,
    outputs: Optional[dict] = None,
    **kwargs: Any,
) -> Optional[schemas.ExtractedUsageMetadata]:
    from_metadata = (run_tree.metadata or {}).get("usage_metadata")
    return (outputs or {}).get("usage_metadata") or from_metadata


@overload
def traceable(
    func: Callable[P, R],
) -> SupportsLangsmithExtra[P, R]: ...


@overload
def traceable(
    run_type: ls_client.RUN_TYPE_T = "chain",
    *,
    name: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    tags: Optional[list[str]] = None,
    client: Optional[ls_client.Client] = None,
    reduce_fn: Optional[Callable[[Sequence], dict]] = None,
    project_name: Optional[str] = None,
    process_inputs: Optional[Callable[[dict], dict]] = None,
    process_outputs: Optional[Callable[..., dict]] = None,
    process_chunk: Optional[Callable] = None,
    _invocation_params_fn: Optional[Callable[[dict], dict]] = None,
    dangerously_allow_filesystem: bool = False,
) -> Callable[[Callable[P, R]], SupportsLangsmithExtra[P, R]]: ...


def traceable(
    *args: Any,
    **kwargs: Any,
) -> Union[Callable, Callable[[Callable], Callable]]:
    """Trace a function with langsmith.

    Args:
        run_type: The type of run (span) to create. Examples: llm, chain, tool, prompt,
            retriever, etc. Defaults to "chain".
        name: The name of the run. Defaults to the function name.
        metadata: The metadata to add to the run. Defaults to None.
        tags: The tags to add to the run. Defaults to None.
        client: The client to use for logging the run to LangSmith. Defaults to
            None, which will use the default client.
        reduce_fn: A function to reduce the output of the function if the function
            returns a generator. Defaults to None, which means the values will be
            logged as a list. Note: if the iterator is never exhausted (e.g.
            the function returns an infinite generator), this will never be
            called, and the run itself will be stuck in a pending state.
        project_name: The name of the project to log the run to. Defaults to None,
            which will use the default project.
        process_inputs: Custom serialization / processing function for inputs.
            Defaults to None.
        process_outputs: Custom serialization / processing function for outputs.
            Defaults to None.
        dangerously_allow_filesystem: Whether to allow filesystem access for attachments.
            Defaults to False.

            Traces that reference local filepaths will be uploaded to LangSmith.
            In general, network-hosted applications should not be using this because
            referenced files are usually on the user's machine, not the host machine.

    Returns:
            Union[Callable, Callable[[Callable], Callable]]: The decorated function.

    Note:
            - Requires that LANGSMITH_TRACING_V2 be set to 'true' in the environment.

    Examples:
        Basic usage:

        .. code-block:: python

            @traceable
            def my_function(x: float, y: float) -> float:
                return x + y


            my_function(5, 6)


            @traceable
            async def my_async_function(query_params: dict) -> dict:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(
                        "https://api.example.com/data",
                        params=query_params,
                    )
                    return response.json()


            asyncio.run(my_async_function({"param": "value"}))

        Streaming data with a generator:

        .. code-block:: python

            @traceable
            def my_generator(n: int) -> Iterable:
                for i in range(n):
                    yield i


            for item in my_generator(5):
                print(item)

        Async streaming data:

        .. code-block:: python

            @traceable
            async def my_async_generator(query_params: dict) -> Iterable:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(
                        "https://api.example.com/data",
                        params=query_params,
                    )
                    for item in response.json():
                        yield item


            async def async_code():
                async for item in my_async_generator({"param": "value"}):
                    print(item)


            asyncio.run(async_code())

        Specifying a run type and name:

        .. code-block:: python

            @traceable(name="CustomName", run_type="tool")
            def another_function(a: float, b: float) -> float:
                return a * b


            another_function(5, 6)

        Logging with custom metadata and tags:

        .. code-block:: python

            @traceable(
                metadata={"version": "1.0", "author": "John Doe"}, tags=["beta", "test"]
            )
            def tagged_function(x):
                return x**2


            tagged_function(5)

        Specifying a custom client and project name:

        .. code-block:: python

            custom_client = Client(api_key="your_api_key")


            @traceable(client=custom_client, project_name="My Special Project")
            def project_specific_function(data):
                return data


            project_specific_function({"data": "to process"})

        Manually passing langsmith_extra:

        .. code-block:: python

            @traceable
            def manual_extra_function(x):
                return x**2


            manual_extra_function(5, langsmith_extra={"metadata": {"version": "1.0"}})
    """
    run_type = cast(
        ls_client.RUN_TYPE_T,
        (
            args[0]
            if args and isinstance(args[0], str)
            else (kwargs.pop("run_type", None) or "chain")
        ),
    )
    if run_type not in _VALID_RUN_TYPES:
        warnings.warn(
            f"Unrecognized run_type: {run_type}. Must be one of: {_VALID_RUN_TYPES}."
            f" Did you mean @traceable(name='{run_type}')?"
        )
    if len(args) > 1:
        warnings.warn(
            "The `traceable()` decorator only accepts one positional argument, "
            "which should be the run_type. All other arguments should be passed "
            "as keyword arguments."
        )
    if "extra" in kwargs:
        warnings.warn(
            "The `extra` keyword argument is deprecated. Please use `metadata` "
            "instead.",
            DeprecationWarning,
        )
    reduce_fn = kwargs.pop("reduce_fn", None)
    container_input = _ContainerInput(
        # TODO: Deprecate raw extra
        extra_outer=kwargs.pop("extra", None),
        name=kwargs.pop("name", None),
        metadata=kwargs.pop("metadata", None),
        tags=kwargs.pop("tags", None),
        client=kwargs.pop("client", None),
        project_name=kwargs.pop("project_name", None),
        run_type=run_type,
        process_inputs=kwargs.pop("process_inputs", None),
        process_chunk=kwargs.pop("process_chunk", None),
        invocation_params_fn=kwargs.pop("_invocation_params_fn", None),
        dangerously_allow_filesystem=kwargs.pop("dangerously_allow_filesystem", False),
    )
    outputs_processor = kwargs.pop("process_outputs", None)
    _on_run_end = functools.partial(
        _handle_container_end,
        outputs_processor=outputs_processor,
    )

    if kwargs:
        warnings.warn(
            f"The following keyword arguments are not recognized and will be ignored: "
            f"{sorted(kwargs.keys())}.",
            DeprecationWarning,
        )

    def decorator(func: Callable):
        func_sig = inspect.signature(func)
        func_accepts_parent_run = func_sig.parameters.get("run_tree", None) is not None
        func_accepts_config = func_sig.parameters.get("config", None) is not None

        @functools.wraps(func)
        async def async_wrapper(
            *args: Any,
            langsmith_extra: Optional[LangSmithExtra] = None,
            **kwargs: Any,
        ) -> Any:
            """Async version of wrapper function."""
            if not func_accepts_config:
                kwargs.pop("config", None)
            run_container = await aitertools.aio_to_thread(
                _setup_run,
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )

            try:
                accepts_context = aitertools.asyncio_accepts_context()
                if func_accepts_parent_run:
                    kwargs["run_tree"] = run_container["new_run"]

                otel_context_manager = _maybe_create_otel_context(
                    run_container["new_run"]
                )
                if otel_context_manager:

                    async def run_with_otel_context():
                        with otel_context_manager:
                            return await func(*args, **kwargs)

                    if accepts_context:
                        function_result = await asyncio.create_task(  # type: ignore[call-arg]
                            run_with_otel_context(), context=run_container["context"]
                        )
                    else:
                        # Python < 3.11
                        with tracing_context(
                            **get_tracing_context(run_container["context"])
                        ):
                            function_result = await run_with_otel_context()
                else:
                    fr_coro = func(*args, **kwargs)
                    if accepts_context:
                        function_result = await asyncio.create_task(  # type: ignore[call-arg]
                            fr_coro, context=run_container["context"]
                        )
                    else:
                        # Python < 3.11
                        with tracing_context(
                            **get_tracing_context(run_container["context"])
                        ):
                            function_result = await fr_coro
            except BaseException as e:
                # shield from cancellation, given we're catching all exceptions
                _cleanup_traceback(e)
                await asyncio.shield(
                    aitertools.aio_to_thread(_on_run_end, run_container, error=e)
                )
                raise
            await aitertools.aio_to_thread(
                _on_run_end, run_container, outputs=function_result
            )
            return function_result

        @functools.wraps(func)
        async def async_generator_wrapper(
            *args: Any, langsmith_extra: Optional[LangSmithExtra] = None, **kwargs: Any
        ) -> AsyncGenerator:
            if not func_accepts_config:
                kwargs.pop("config", None)
            run_container = await aitertools.aio_to_thread(
                _setup_run,
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )
            results: list[Any] = []
            try:
                if func_accepts_parent_run:
                    kwargs["run_tree"] = run_container["new_run"]
                    # TODO: Nesting is ambiguous if a nested traceable function is only
                    # called mid-generation. Need to explicitly accept run_tree to get
                    # around this.

                otel_context_manager = _maybe_create_otel_context(
                    run_container["new_run"]
                )

                async_gen_result = func(*args, **kwargs)
                # Can't iterate through if it's a coroutine
                accepts_context = aitertools.asyncio_accepts_context()
                if inspect.iscoroutine(async_gen_result):
                    if accepts_context:
                        async_gen_result = await asyncio.create_task(
                            async_gen_result, context=run_container["context"]
                        )  # type: ignore
                    else:
                        # Python < 3.11
                        with tracing_context(
                            **get_tracing_context(run_container["context"])
                        ):
                            async_gen_result = await async_gen_result

                async for item in _process_async_iterator(
                    generator=async_gen_result,
                    run_container=run_container,
                    is_llm_run=(
                        run_container["new_run"].run_type == "llm"
                        if run_container["new_run"]
                        else False
                    ),
                    accepts_context=accepts_context,
                    results=results,
                    process_chunk=container_input.get("process_chunk"),
                    otel_context_manager=otel_context_manager,
                ):
                    yield item
            except BaseException as e:
                _cleanup_traceback(e)
                await asyncio.shield(
                    aitertools.aio_to_thread(
                        _on_run_end,
                        run_container,
                        error=e,
                        outputs=_get_function_result(results, reduce_fn),
                    )
                )
                raise
            await aitertools.aio_to_thread(
                _on_run_end,
                run_container,
                outputs=_get_function_result(results, reduce_fn),
            )

        @functools.wraps(func)
        def wrapper(
            *args: Any,
            langsmith_extra: Optional[LangSmithExtra] = None,
            **kwargs: Any,
        ) -> Any:
            """Create a new run or create_child() if run is passed in kwargs."""
            if not func_accepts_config:
                kwargs.pop("config", None)
            run_container = _setup_run(
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            try:
                if func_accepts_parent_run:
                    kwargs["run_tree"] = run_container["new_run"]

                otel_context_manager = _maybe_create_otel_context(
                    run_container["new_run"]
                )
                if otel_context_manager:

                    def run_with_otel_context():
                        with otel_context_manager:
                            return func(*args, **kwargs)

                    function_result = run_container["context"].run(
                        run_with_otel_context
                    )
                else:
                    function_result = run_container["context"].run(
                        func, *args, **kwargs
                    )
            except BaseException as e:
                _cleanup_traceback(e)
                _on_run_end(run_container, error=e)
                raise
            _on_run_end(run_container, outputs=function_result)
            return function_result

        @functools.wraps(func)
        def generator_wrapper(
            *args: Any, langsmith_extra: Optional[LangSmithExtra] = None, **kwargs: Any
        ) -> Any:
            if not func_accepts_config:
                kwargs.pop("config", None)
            run_container = _setup_run(
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            results: list[Any] = []
            function_return: Any = None

            try:
                if func_accepts_parent_run:
                    kwargs["run_tree"] = run_container["new_run"]

                generator_result = run_container["context"].run(func, *args, **kwargs)

                otel_context_manager = _maybe_create_otel_context(
                    run_container["new_run"]
                )

                function_return = yield from _process_iterator(
                    generator_result,
                    run_container,
                    is_llm_run=run_type == "llm",
                    results=results,
                    process_chunk=container_input.get("process_chunk"),
                    otel_context_manager=otel_context_manager,
                )

                if function_return is not None:
                    results.append(function_return)

            except BaseException as e:
                _cleanup_traceback(e)
                _on_run_end(
                    run_container,
                    error=e,
                    outputs=_get_function_result(results, reduce_fn),
                )
                raise
            _on_run_end(run_container, outputs=_get_function_result(results, reduce_fn))

            return function_return

        # "Stream" functions (used in methods like OpenAI/Anthropic's SDKs)
        # are functions that return iterable responses and should not be
        # considered complete until the streaming is completed
        @functools.wraps(func)
        def stream_wrapper(
            *args: Any, langsmith_extra: Optional[LangSmithExtra] = None, **kwargs: Any
        ) -> Any:
            if not func_accepts_config:
                kwargs.pop("config", None)
            trace_container = _setup_run(
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )

            try:
                if func_accepts_parent_run:
                    kwargs["run_tree"] = trace_container["new_run"]
                stream = trace_container["context"].run(func, *args, **kwargs)
            except Exception as e:
                _cleanup_traceback(e)
                _on_run_end(trace_container, error=e)
                raise

            if hasattr(stream, "__iter__"):
                return _TracedStream(stream, trace_container, reduce_fn)
            elif hasattr(stream, "__aiter__"):
                # sync function -> async iterable (unexpected)
                return _TracedAsyncStream(stream, trace_container, reduce_fn)

            # If it's not iterable, end the trace immediately
            _on_run_end(trace_container, outputs=stream)
            return stream

        @functools.wraps(func)
        async def async_stream_wrapper(
            *args: Any, langsmith_extra: Optional[LangSmithExtra] = None, **kwargs: Any
        ) -> Any:
            if not func_accepts_config:
                kwargs.pop("config", None)
            trace_container = await aitertools.aio_to_thread(
                _setup_run,
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )

            try:
                if func_accepts_parent_run:
                    kwargs["run_tree"] = trace_container["new_run"]
                stream = await func(*args, **kwargs)
            except Exception as e:
                await aitertools.aio_to_thread(_on_run_end, trace_container, error=e)
                raise

            if hasattr(stream, "__aiter__"):
                return _TracedAsyncStream(stream, trace_container, reduce_fn)
            elif hasattr(stream, "__iter__"):
                # Async function -> sync iterable
                return _TracedStream(stream, trace_container, reduce_fn)

            # If it's not iterable, end the trace immediately
            await aitertools.aio_to_thread(_on_run_end, trace_container, outputs=stream)
            return stream

        if inspect.isasyncgenfunction(func):
            selected_wrapper: Callable = async_generator_wrapper
        elif inspect.isgeneratorfunction(func):
            selected_wrapper = generator_wrapper
        elif is_async(func):
            if reduce_fn:
                selected_wrapper = async_stream_wrapper
            else:
                selected_wrapper = async_wrapper
        else:
            if reduce_fn:
                selected_wrapper = stream_wrapper
            else:
                selected_wrapper = wrapper
        setattr(selected_wrapper, "__langsmith_traceable__", True)
        sig = inspect.signature(selected_wrapper)
        if not sig.parameters.get("config"):
            sig = sig.replace(
                parameters=[
                    *(
                        param
                        for param in sig.parameters.values()
                        if param.kind != inspect.Parameter.VAR_KEYWORD
                    ),
                    inspect.Parameter(
                        "config", inspect.Parameter.KEYWORD_ONLY, default=None
                    ),
                    *(
                        param
                        for param in sig.parameters.values()
                        if param.kind == inspect.Parameter.VAR_KEYWORD
                    ),
                ]
            )
            selected_wrapper.__signature__ = sig  # type: ignore[attr-defined]
        return selected_wrapper

    # If the decorator is called with no arguments, then it's being used as a
    # decorator, so we return the decorator function
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return decorator(args[0])
    # Else it's being used as a decorator factory, so we return the decorator
    return decorator


class trace:
    """Manage a LangSmith run in context.

    This class can be used as both a synchronous and asynchronous context manager.

    Args:
        name (str): Name of the run.
        run_type (ls_client.RUN_TYPE_T, optional): Type of run (e.g., "chain", "llm", "tool"). Defaults to "chain".
        inputs (Optional[Dict], optional): Initial input data for the run. Defaults to None.
        project_name (Optional[str], optional): Project name to associate the run with. Defaults to None.
        parent (Optional[Union[run_trees.RunTree, str, Mapping]], optional): Parent run. Can be a RunTree, dotted order string, or tracing headers. Defaults to None.
        tags (Optional[List[str]], optional): List of tags for the run. Defaults to None.
        metadata (Optional[Mapping[str, Any]], optional): Additional metadata for the run. Defaults to None.
        client (Optional[ls_client.Client], optional): LangSmith client for custom settings. Defaults to None.
        run_id (Optional[ls_client.ID_TYPE], optional): Preset identifier for the run. Defaults to None.
        reference_example_id (Optional[ls_client.ID_TYPE], optional): Associates run with a dataset example. Only for root runs in evaluation. Defaults to None.
        exceptions_to_handle (Optional[Tuple[Type[BaseException], ...]], optional): Exception types to ignore. Defaults to None.
        extra (Optional[Dict], optional): Extra data to send to LangSmith. Use 'metadata' instead. Defaults to None.

    Examples:
        Synchronous usage:

        .. code-block:: python

            >>> with trace("My Operation", run_type="tool", tags=["important"]) as run:
            ...     result = "foo"  # Perform operation
            ...     run.metadata["some-key"] = "some-value"
            ...     run.end(outputs={"result": result})

        Asynchronous usage:

        .. code-block:: python

            >>> async def main():
            ...     async with trace("Async Operation", run_type="tool", tags=["async"]) as run:
            ...         result = "foo"  # Await async operation
            ...         run.metadata["some-key"] = "some-value"
            ...         # "end" just adds the outputs and sets error to None
            ...         # The actual patching of the run happens when the context exits
            ...         run.end(outputs={"result": result})
            >>> asyncio.run(main())

        Handling specific exceptions:

        .. code-block:: python

            >>> import pytest
            >>> import sys
            >>> with trace("Test", exceptions_to_handle=(pytest.skip.Exception,)):
            ...     if sys.platform == "win32": # Just an example
            ...         pytest.skip("Skipping test for windows")
            ...     result = "foo"  # Perform test operation
    """

    def __init__(
        self,
        name: str,
        run_type: ls_client.RUN_TYPE_T = "chain",
        *,
        inputs: Optional[dict] = None,
        extra: Optional[dict] = None,
        project_name: Optional[str] = None,
        parent: Optional[
            Union[run_trees.RunTree, str, Mapping, Literal["ignore"]]
        ] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        client: Optional[ls_client.Client] = None,
        run_id: Optional[ls_client.ID_TYPE] = None,
        reference_example_id: Optional[ls_client.ID_TYPE] = None,
        exceptions_to_handle: Optional[tuple[type[BaseException], ...]] = None,
        attachments: Optional[schemas.Attachments] = None,
        **kwargs: Any,
    ):
        """Initialize the trace context manager.

        Warns if unsupported kwargs are passed.
        """
        self._end_on_exit = kwargs.pop("_end_on_exit", True)
        if kwargs:
            warnings.warn(
                "The `trace` context manager no longer supports the following kwargs: "
                f"{sorted(kwargs.keys())}.",
                DeprecationWarning,
            )
        self.name = name
        self.run_type = run_type
        self.inputs = inputs
        self.attachments = attachments
        self.extra = extra
        self.project_name = project_name
        self.parent = parent
        # The run tree is deprecated. Keeping for backwards compat.
        # Will fully merge within parent later.
        self.run_tree = kwargs.get("run_tree")
        self.tags = tags
        self.metadata = metadata
        self.client = client
        self.run_id = run_id
        self.reference_example_id = reference_example_id
        self.exceptions_to_handle = exceptions_to_handle
        self.new_run: Optional[run_trees.RunTree] = None
        self.old_ctx: Optional[dict] = None

    def _setup(self) -> run_trees.RunTree:
        """Set up the tracing context and create a new run.

        This method initializes the tracing context, merges tags and metadata,
        creates a new run (either as a child of an existing run or as a new root run),
        and sets up the necessary context variables.

        Returns:
            run_trees.RunTree: The newly created run.
        """
        self.old_ctx = get_tracing_context()
        enabled = utils.tracing_is_enabled(self.old_ctx)

        outer_tags = _TAGS.get()
        outer_metadata = _METADATA.get()
        client_ = self.client or self.old_ctx.get("client")
        parent_run_ = _get_parent_run(
            {
                "parent": self.parent,
                "run_tree": self.run_tree,
                "client": client_,
            }
        )

        tags_ = sorted(set((self.tags or []) + (outer_tags or [])))
        metadata = {
            **(self.metadata or {}),
            **(outer_metadata or {}),
            "ls_method": "trace",
        }

        extra_outer = self.extra or {}
        extra_outer["metadata"] = metadata

        project_name_ = _get_project_name(self.project_name)

        if parent_run_ is not None and enabled:
            self.new_run = parent_run_.create_child(
                name=self.name,
                run_id=self.run_id,
                run_type=self.run_type,
                extra=extra_outer,
                inputs=self.inputs,
                tags=tags_,
                attachments=self.attachments,
            )
        else:
            self.new_run = run_trees.RunTree(
                name=self.name,
                id=ls_client._ensure_uuid(self.run_id),
                reference_example_id=ls_client._ensure_uuid(
                    self.reference_example_id, accept_null=True
                ),
                run_type=self.run_type,
                extra=extra_outer,
                project_name=project_name_ or "default",
                replicas=run_trees._REPLICAS.get(),
                inputs=self.inputs or {},
                tags=tags_,
                client=client_,  # type: ignore
                attachments=self.attachments or {},  # type: ignore
            )

        if enabled is True:
            self.new_run.post()
        if enabled:
            _TAGS.set(tags_)
            _METADATA.set(metadata)
            _PARENT_RUN_TREE.set(self.new_run)
            _PROJECT_NAME.set(project_name_)
            _CLIENT.set(client_)

        return self.new_run

    def _teardown(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Clean up the tracing context and finalize the run.

        This method handles exceptions, ends the run if necessary,
        patches the run if it's not disabled, and resets the tracing context.

        Args:
            exc_type: The type of the exception that occurred, if any.
            exc_value: The exception instance that occurred, if any.
            traceback: The traceback object associated with the exception, if any.
        """
        if self.new_run is None:
            return
        if exc_type is not None:
            if self.exceptions_to_handle and issubclass(
                exc_type, self.exceptions_to_handle
            ):
                tb = None
            else:
                tb = utils._format_exc()
                tb = f"{exc_type.__name__}: {exc_value}\n\n{tb}"
            self.new_run.end(error=tb)
        if self.old_ctx is not None:
            enabled = utils.tracing_is_enabled(self.old_ctx)
            if enabled is True and self._end_on_exit:
                self.new_run.patch()

            _set_tracing_context(self.old_ctx)
        else:
            warnings.warn("Tracing context was not set up properly.", RuntimeWarning)

    def __enter__(self) -> run_trees.RunTree:
        """Enter the context manager synchronously.

        Returns:
            run_trees.RunTree: The newly created run.
        """
        return self._setup()

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        """Exit the context manager synchronously.

        Args:
            exc_type: The type of the exception that occurred, if any.
            exc_value: The exception instance that occurred, if any.
            traceback: The traceback object associated with the exception, if any.
        """
        self._teardown(exc_type, exc_value, traceback)

    async def __aenter__(self) -> run_trees.RunTree:
        """Enter the context manager asynchronously.

        Returns:
            run_trees.RunTree: The newly created run.
        """
        ctx = copy_context()
        result = await aitertools.aio_to_thread(self._setup, __ctx=ctx)
        # Set the context for the current thread
        _set_tracing_context(get_tracing_context(ctx))
        return result

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        """Exit the context manager asynchronously.

        Args:
            exc_type: The type of the exception that occurred, if any.
            exc_value: The exception instance that occurred, if any.
            traceback: The traceback object associated with the exception, if any.
        """
        ctx = copy_context()
        if exc_type is not None:
            await asyncio.shield(
                aitertools.aio_to_thread(
                    self._teardown, exc_type, exc_value, traceback, __ctx=ctx
                )
            )
        else:
            await aitertools.aio_to_thread(
                self._teardown, exc_type, exc_value, traceback, __ctx=ctx
            )
        _set_tracing_context(get_tracing_context(ctx))


def _get_project_name(project_name: Optional[str]) -> Optional[str]:
    if project_name:
        return project_name
    prt = _PARENT_RUN_TREE.get()
    return (
        # Maintain tree consistency first
        _PROJECT_NAME.get()
        or (prt.session_name if prt else None)
        # fallback to the default for the environment
        or utils.get_tracer_project()
    )


def as_runnable(traceable_fn: Callable) -> Runnable:
    """Convert a function wrapped by the LangSmith @traceable decorator to a Runnable.

    Args:
        traceable_fn (Callable): The function wrapped by the @traceable decorator.

    Returns:
        Runnable: A Runnable object that maintains a consistent LangSmith
            tracing context.

    Raises:
        ImportError: If langchain module is not installed.
        ValueError: If the provided function is not wrapped by the @traceable decorator.

    Example:
        >>> @traceable
        ... def my_function(input_data):
        ...     # Function implementation
        ...     pass
        >>> runnable = as_runnable(my_function)
    """
    try:
        from langchain_core.runnables import RunnableConfig, RunnableLambda
        from langchain_core.runnables.utils import Input, Output
    except ImportError as e:
        raise ImportError(
            "as_runnable requires langchain-core to be installed. "
            "You can install it with `pip install langchain-core`."
        ) from e
    if not is_traceable_function(traceable_fn):
        try:
            fn_src = inspect.getsource(traceable_fn)
        except Exception:
            fn_src = "<source unavailable>"
        raise ValueError(
            f"as_runnable expects a function wrapped by the LangSmith"
            f" @traceable decorator. Got {traceable_fn} defined as:\n{fn_src}"
        )

    class RunnableTraceable(RunnableLambda):
        """Converts a @traceable decorated function to a Runnable.

        This helps maintain a consistent LangSmith tracing context.
        """

        def __init__(
            self,
            func: Callable,
            afunc: Optional[Callable[..., Awaitable[Output]]] = None,
        ) -> None:
            wrapped: Optional[Callable[[Input], Output]] = None
            awrapped = self._wrap_async(afunc)
            if is_async(func):
                if awrapped is not None:
                    raise TypeError(
                        "Func was provided as a coroutine function, but afunc was "
                        "also provided. If providing both, func should be a regular "
                        "function to avoid ambiguity."
                    )
                wrapped = cast(Callable[[Input], Output], self._wrap_async(func))
            elif is_traceable_function(func):
                wrapped = cast(Callable[[Input], Output], self._wrap_sync(func))
            if wrapped is None:
                raise ValueError(
                    f"{self.__class__.__name__} expects a function wrapped by"
                    " the LangSmith"
                    f" @traceable decorator. Got {func}"
                )

            super().__init__(
                wrapped,
                cast(
                    Optional[Callable[[Input], Awaitable[Output]]],
                    awrapped,
                ),
            )

        @staticmethod
        def _wrap_sync(
            func: Callable[..., Output],
        ) -> Callable[[Input, RunnableConfig], Output]:
            """Wrap a synchronous function to make it asynchronous."""

            def wrap_traceable(inputs: dict, config: RunnableConfig) -> Any:
                run_tree = run_trees.RunTree.from_runnable_config(cast(dict, config))
                return func(**inputs, langsmith_extra={"run_tree": run_tree})

            return cast(Callable[[Input, RunnableConfig], Output], wrap_traceable)

        @staticmethod
        def _wrap_async(
            afunc: Optional[Callable[..., Awaitable[Output]]],
        ) -> Optional[Callable[[Input, RunnableConfig], Awaitable[Output]]]:
            """Wrap an async function to make it synchronous."""
            if afunc is None:
                return None

            if not is_traceable_function(afunc):
                raise ValueError(
                    "RunnableTraceable expects a function wrapped by the LangSmith"
                    f" @traceable decorator. Got {afunc}"
                )
            afunc_ = cast(Callable[..., Awaitable[Output]], afunc)

            async def awrap_traceable(inputs: dict, config: RunnableConfig) -> Any:
                run_tree = run_trees.RunTree.from_runnable_config(cast(dict, config))
                return await afunc_(**inputs, langsmith_extra={"run_tree": run_tree})

            return cast(
                Callable[[Input, RunnableConfig], Awaitable[Output]], awrap_traceable
            )

    return RunnableTraceable(traceable_fn)


## Private Methods and Objects
_VALID_RUN_TYPES = {
    "tool",
    "chain",
    "llm",
    "retriever",
    "embedding",
    "prompt",
    "parser",
}


class _TraceableContainer(TypedDict, total=False):
    """Typed response when initializing a run a traceable."""

    new_run: Optional[run_trees.RunTree]
    project_name: Optional[str]
    outer_project: Optional[str]
    outer_metadata: Optional[dict[str, Any]]
    outer_tags: Optional[list[str]]
    _on_success: Optional[Callable[[run_trees.RunTree], Any]]
    on_end: Optional[Callable[[run_trees.RunTree], Any]]
    context: contextvars.Context
    _token_event_logged: Optional[bool]


class _ContainerInput(TypedDict, total=False):
    """Typed response when initializing a run a traceable."""

    extra_outer: Optional[dict]
    name: Optional[str]
    metadata: Optional[dict[str, Any]]
    tags: Optional[list[str]]
    client: Optional[ls_client.Client]
    reduce_fn: Optional[Callable]
    project_name: Optional[str]
    run_type: ls_client.RUN_TYPE_T
    process_inputs: Optional[Callable[[dict], dict]]
    process_chunk: Optional[Callable]
    invocation_params_fn: Optional[Callable[[dict], dict]]
    dangerously_allow_filesystem: Optional[bool]


def _container_end(
    container: _TraceableContainer,
    outputs: Optional[Any] = None,
    error: Optional[BaseException] = None,
) -> None:
    """End the run."""
    run_tree = container.get("new_run")
    if run_tree is None:
        # Tracing not enabled
        return
    if isinstance(outputs, dict):
        dict_outputs = outputs
    elif (
        outputs is not None
        and hasattr(outputs, "model_dump")
        and callable(outputs.model_dump)
        and not isinstance(outputs, type)
    ):
        try:
            dict_outputs = outputs.model_dump(exclude_none=True, mode="json")
        except Exception as e:
            LOGGER.debug(
                f"Failed to use model_dump to serialize {type(outputs)} to JSON: {e}"
            )
            dict_outputs = {"output": outputs}
    else:
        dict_outputs = {"output": outputs}
    if (usage := _extract_usage(run_tree=run_tree, outputs=dict_outputs)) is not None:
        run_tree.metadata["usage_metadata"] = usage
    if error:
        stacktrace = utils._format_exc()
        error_repr = f"{repr(error)}\n\n{stacktrace}"
    else:
        error_repr = None
        if (_on_success := container.get("_on_success")) and callable(_on_success):
            try:
                _on_success(run_tree)
            except BaseException as e:
                warnings.warn(f"Failed to run _on_success function: {e}")

    run_tree.end(outputs=dict_outputs, error=error_repr)
    if utils.tracing_is_enabled() is True:
        run_tree.patch()
    if (on_end := container.get("on_end")) and callable(on_end):
        try:
            on_end(run_tree)
        except BaseException as e:
            warnings.warn(f"Failed to run on_end function: {e}")


def _collect_extra(extra_outer: dict, langsmith_extra: LangSmithExtra) -> dict:
    run_extra = langsmith_extra.get("run_extra", None)
    if run_extra:
        extra_inner = {**extra_outer, **run_extra}
    else:
        extra_inner = extra_outer
    return extra_inner


def _get_parent_run(
    langsmith_extra: LangSmithExtra,
    config: Optional[dict] = None,
) -> Optional[run_trees.RunTree]:
    parent = langsmith_extra.get("parent")
    if parent == "ignore":
        return None
    if isinstance(parent, run_trees.RunTree):
        return parent
    if isinstance(parent, dict):
        return run_trees.RunTree.from_headers(
            parent,
            client=langsmith_extra.get("client"),
            # Precedence: headers -> cvar -> explicit -> env var
            project_name=_get_project_name(langsmith_extra.get("project_name")),
        )
    if isinstance(parent, str):
        dort = run_trees.RunTree.from_dotted_order(
            parent,
            client=langsmith_extra.get("client"),
            # Precedence: cvar -> explicit ->  env var
            project_name=_get_project_name(langsmith_extra.get("project_name")),
        )
        return dort
    run_tree = langsmith_extra.get("run_tree")
    if run_tree:
        return run_tree
    crt = get_current_run_tree()
    if _runtime_env.get_langchain_core_version() is not None:
        if rt := run_trees.RunTree.from_runnable_config(
            config, client=langsmith_extra.get("client")
        ):
            # Still need to break ties when alternating between traceable and
            # LanChain code.
            # Nesting: LC -> LS -> LS, we want to still use LS as the parent
            # Otherwise would look like LC -> {LS, LS} (siblings)
            if (
                not crt  # Simple LC -> LS
                # Let user override if manually passed in or invoked in a
                # RunnableSequence. This is a naive check.
                or (config is not None and config.get("callbacks"))
                # If the LangChain dotted order is more nested than the LangSmith
                # dotted order, use the LangChain run as the parent.
                # Note that this condition shouldn't be triggered in later
                # versions of core, since we also update the run_tree context
                # vars when updating the RunnableConfig context var.
                or rt.dotted_order > crt.dotted_order
            ):
                return rt
    return crt


def _setup_run(
    func: Callable,
    container_input: _ContainerInput,
    langsmith_extra: Optional[LangSmithExtra] = None,
    args: Any = None,
    kwargs: Any = None,
) -> _TraceableContainer:
    """Create a new run or create_child() if run is passed in kwargs."""
    extra_outer = container_input.get("extra_outer") or {}
    metadata = container_input.get("metadata")
    tags = container_input.get("tags")
    client = container_input.get("client")
    run_type = container_input.get("run_type") or "chain"
    dangerously_allow_filesystem = container_input.get(
        "dangerously_allow_filesystem", False
    )
    outer_project = _PROJECT_NAME.get()
    langsmith_extra = langsmith_extra or LangSmithExtra()
    name = langsmith_extra.get("name") or container_input.get("name")
    client_ = langsmith_extra.get("client", client) or _CLIENT.get()
    parent_run_ = _get_parent_run(
        {**langsmith_extra, "client": client_}, kwargs.get("config")
    )
    project_cv = _PROJECT_NAME.get()
    selected_project = (
        project_cv  # From parent trace
        or (
            parent_run_.session_name if parent_run_ else None
        )  # from parent run attempt 2 (not managed by traceable)
        or langsmith_extra.get("project_name")  # at invocation time
        or container_input["project_name"]  # at decorator time
        or utils.get_tracer_project()  # default
    )
    reference_example_id = langsmith_extra.get("reference_example_id")
    id_ = langsmith_extra.get("run_id")
    if not parent_run_ and not utils.tracing_is_enabled():
        utils.log_once(
            logging.DEBUG,
            "LangSmith tracing is not enabled, returning original function.",
        )
        return _TraceableContainer(
            new_run=None,
            project_name=selected_project,
            outer_project=outer_project,
            outer_metadata=None,
            outer_tags=None,
            _on_success=langsmith_extra.get("_on_success"),
            on_end=langsmith_extra.get("on_end"),
            context=copy_context(),
            _token_event_logged=False,
        )
    id_ = id_ or str(uuid.uuid4())
    signature = inspect.signature(func)
    name_ = name or utils._get_function_name(func)
    extra_inner = _collect_extra(extra_outer, langsmith_extra)
    outer_metadata = _METADATA.get()
    outer_tags = _TAGS.get()
    context = copy_context()
    metadata_ = {
        **(langsmith_extra.get("metadata") or {}),
        **(outer_metadata or {}),
    }
    context.run(_METADATA.set, metadata_)
    metadata_.update(metadata or {})
    metadata_["ls_method"] = "traceable"
    extra_inner["metadata"] = metadata_
    inputs, attachments = _get_inputs_and_attachments_safe(signature, *args, **kwargs)
    invocation_params_fn = container_input.get("invocation_params_fn")
    if invocation_params_fn:
        try:
            invocation_params = {
                k: v for k, v in invocation_params_fn(inputs).items() if v is not None
            }
            if invocation_params and isinstance(invocation_params, dict):
                metadata_.update(invocation_params)
        except BaseException as e:
            LOGGER.error(f"Failed to infer invocation params for {name_}: {e}")
    process_inputs = container_input.get("process_inputs")
    if process_inputs:
        try:
            inputs = process_inputs(inputs)
        except BaseException as e:
            LOGGER.error(f"Failed to filter inputs for {name_}: {e}")
    tags_ = (langsmith_extra.get("tags") or []) + (outer_tags or [])
    context.run(_TAGS.set, tags_)
    tags_ += tags or []
    if parent_run_ is not None:
        new_run = parent_run_.create_child(
            name=name_,
            run_type=run_type,
            inputs=inputs,
            tags=tags_,
            extra=extra_inner,
            run_id=id_,
            attachments=attachments,
        )
    else:
        new_run = run_trees.RunTree(
            id=ls_client._ensure_uuid(id_),
            name=name_,
            inputs=inputs,
            run_type=run_type,
            reference_example_id=ls_client._ensure_uuid(
                reference_example_id, accept_null=True
            ),
            project_name=selected_project,  # type: ignore[arg-type]
            replicas=run_trees._REPLICAS.get(),
            extra=extra_inner,
            tags=tags_,
            client=client_,  # type: ignore
            attachments=attachments,  # type: ignore
            dangerously_allow_filesystem=dangerously_allow_filesystem,
        )
    if utils.tracing_is_enabled() is True:
        try:
            new_run.post()
        except BaseException as e:
            LOGGER.error(f"Failed to post run {new_run.id}: {e}")
    response_container = _TraceableContainer(
        new_run=new_run,
        project_name=selected_project,
        outer_project=outer_project,
        outer_metadata=outer_metadata,
        outer_tags=outer_tags,
        on_end=langsmith_extra.get("on_end"),
        _on_success=langsmith_extra.get("_on_success"),
        context=context,
        _token_event_logged=False,
    )
    context.run(_PROJECT_NAME.set, response_container["project_name"])
    context.run(_PARENT_RUN_TREE.set, response_container["new_run"])
    return response_container


def _handle_container_end(
    container: _TraceableContainer,
    outputs: Optional[Any] = None,
    error: Optional[BaseException] = None,
    outputs_processor: Optional[Callable[..., dict]] = None,
) -> None:
    """Handle the end of run."""
    try:
        if outputs_processor is not None:
            outputs = outputs_processor(outputs)
        _container_end(container, outputs=outputs, error=error)
    except BaseException as e:
        LOGGER.warning(f"Unable to process trace outputs: {repr(e)}")


def _is_traceable_function(func: Any) -> bool:
    return getattr(func, "__langsmith_traceable__", False)


def _get_inputs(
    signature: inspect.Signature, *args: Any, **kwargs: Any
) -> dict[str, Any]:
    """Return a dictionary of inputs from the function signature."""
    bound = signature.bind_partial(*args, **kwargs)
    bound.apply_defaults()
    arguments = dict(bound.arguments)
    arguments.pop("self", None)
    arguments.pop("cls", None)
    for param_name, param in signature.parameters.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            # Update with the **kwargs, and remove the original entry
            # This is to help flatten out keyword arguments
            if param_name in arguments:
                arguments.update(arguments[param_name])
                arguments.pop(param_name)

    return arguments


def _get_inputs_safe(
    signature: inspect.Signature, *args: Any, **kwargs: Any
) -> dict[str, Any]:
    try:
        return _get_inputs(signature, *args, **kwargs)
    except BaseException as e:
        LOGGER.debug(f"Failed to get inputs for {signature}: {e}")
        return {"args": args, "kwargs": kwargs}


def _is_attachment(param: inspect.Parameter) -> bool:
    return param.annotation == schemas.Attachment or (
        get_origin(param.annotation) == Annotated
        and any(arg == schemas.Attachment for arg in get_args(param.annotation))
    )


def _attachment_args_helper(signature: inspect.Signature) -> set[str]:
    return {
        name for name, param in signature.parameters.items() if _is_attachment(param)
    }


@functools.lru_cache(maxsize=1000)
def _cached_attachment_args(signature: inspect.Signature) -> set[str]:
    return _attachment_args_helper(signature)


def _attachment_args(signature: inspect.Signature) -> set[str]:
    # Caching signatures fails if there's unhashable default values.
    try:
        return _cached_attachment_args(signature)
    except TypeError:
        return _attachment_args_helper(signature)


def _get_inputs_and_attachments_safe(
    signature: inspect.Signature, *args: Any, **kwargs: Any
) -> tuple[dict, schemas.Attachments]:
    try:
        inferred = _get_inputs(signature, *args, **kwargs)
        attachment_args = _attachment_args(signature)
        if attachment_args:
            inputs, attachments = {}, {}
            for k, v in inferred.items():
                if k in attachment_args:
                    attachments[k] = v
                else:
                    inputs[k] = v
            return inputs, attachments
        return inferred, {}
    except BaseException as e:
        LOGGER.warning(f"Failed to get inputs for {signature}: {e}")
        return {"args": args, "kwargs": kwargs}, {}


def _set_tracing_context(context: Optional[dict[str, Any]] = None):
    """Set the tracing context."""
    if context is None:
        for k, v in _CONTEXT_KEYS.items():
            v.set(None)
        return
    for k, v in context.items():
        var = _CONTEXT_KEYS[k]
        var.set(v)


def _process_iterator(
    generator: Iterator[T],
    run_container: _TraceableContainer,
    is_llm_run: bool,
    # Results is mutated
    results: list[Any],
    process_chunk: Optional[Callable],
    otel_context_manager: Optional[Any] = None,
) -> Generator[T, None, Any]:
    try:
        while True:
            if otel_context_manager:
                # Create a fresh context manager for each iteration
                def next_with_otel_context():
                    # Get the run_tree from run_container to create a fresh context
                    run_tree = run_container.get("new_run")
                    if run_tree:
                        fresh_otel_context = _maybe_create_otel_context(run_tree)
                        if fresh_otel_context:
                            with fresh_otel_context:
                                return next(generator)
                    return next(generator)

                item: T = run_container["context"].run(next_with_otel_context)  # type: ignore[arg-type]
            else:
                item = run_container["context"].run(next, generator)  # type: ignore[arg-type]
            if process_chunk:
                traced_item = process_chunk(item)
            else:
                traced_item = item
            if (
                is_llm_run
                and run_container["new_run"]
                and not run_container.get("_token_event_logged")
            ):
                run_container["new_run"].add_event(
                    {
                        "name": "new_token",
                        "time": datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat(),
                        "kwargs": {"token": traced_item},
                    }
                )
                run_container["_token_event_logged"] = True
            results.append(traced_item)
            yield item
    except StopIteration as e:
        return e.value


async def _process_async_iterator(
    generator: AsyncIterator[T],
    run_container: _TraceableContainer,
    *,
    is_llm_run: bool,
    accepts_context: bool,
    results: list[Any],
    process_chunk: Optional[Callable],
    otel_context_manager: Optional[Any] = None,
) -> AsyncGenerator[T, None]:
    try:
        while True:
            if otel_context_manager:
                # Create a fresh context manager for each iteration
                async def anext_with_otel_context():
                    # Get the run_tree from run_container to create a fresh context
                    run_tree = run_container.get("new_run")
                    if run_tree:
                        fresh_otel_context = _maybe_create_otel_context(run_tree)
                        if fresh_otel_context:
                            with fresh_otel_context:
                                return await aitertools.py_anext(generator)
                    return await aitertools.py_anext(generator)

                if accepts_context:
                    item = await asyncio.create_task(  # type: ignore[call-arg, var-annotated]
                        anext_with_otel_context(),
                        context=run_container["context"],
                    )
                else:
                    # Python < 3.11
                    with tracing_context(
                        **get_tracing_context(run_container["context"])
                    ):
                        item = await anext_with_otel_context()
            else:
                if accepts_context:
                    item = await asyncio.create_task(  # type: ignore[call-arg, var-annotated]
                        aitertools.py_anext(generator),  # type: ignore[arg-type]
                        context=run_container["context"],
                    )
                else:
                    # Python < 3.11
                    with tracing_context(
                        **get_tracing_context(run_container["context"])
                    ):
                        item = await aitertools.py_anext(generator)
            if process_chunk:
                traced_item = process_chunk(item)
            else:
                traced_item = item
            if (
                is_llm_run
                and run_container["new_run"]
                and not run_container.get("_token_event_logged")
            ):
                run_container["new_run"].add_event(
                    {
                        "name": "new_token",
                        "time": datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat(),
                        "kwargs": {"token": traced_item},
                    }
                )
                run_container["_token_event_logged"] = True
            results.append(traced_item)
            yield item
    except StopAsyncIteration:
        pass


T = TypeVar("T")


class _TracedStreamBase(Generic[T]):
    """Base class for traced stream objects."""

    def __init__(
        self,
        stream: Union[Iterator[T], AsyncIterator[T]],
        trace_container: _TraceableContainer,
        reduce_fn: Optional[Callable] = None,
    ):
        self.__ls_stream__ = stream
        self.__ls_trace_container__ = trace_container
        self.__ls_completed__ = False
        self.__ls_reduce_fn__ = reduce_fn
        self.__ls_accumulated_output__: list[T] = []
        self.__is_llm_run__ = (
            trace_container["new_run"].run_type == "llm"
            if trace_container["new_run"]
            else False
        )

    def __getattr__(self, name: str):
        return getattr(self.__ls_stream__, name)

    def __dir__(self):
        return list(set(dir(self.__class__) + dir(self.__ls_stream__)))

    def __repr__(self):
        return f"Traceable({self.__ls_stream__!r})"

    def __str__(self):
        return str(self.__ls_stream__)

    def __del__(self):
        try:
            if not self.__ls_completed__:
                self._end_trace()
        except BaseException:
            pass
        try:
            self.__ls_stream__.__del__()
        except BaseException:
            pass

    def _end_trace(self, error: Optional[BaseException] = None):
        if self.__ls_completed__:
            return
        try:
            if self.__ls_reduce_fn__:
                reduced_output = self.__ls_reduce_fn__(self.__ls_accumulated_output__)
            else:
                reduced_output = self.__ls_accumulated_output__
            _container_end(
                self.__ls_trace_container__,
                outputs=reduced_output,
                error=error,
            )
        finally:
            self.__ls_completed__ = True


class _TracedStream(_TracedStreamBase, Generic[T]):
    """A wrapper for synchronous stream objects that handles tracing."""

    def __init__(
        self,
        stream: Iterator[T],
        trace_container: _TraceableContainer,
        reduce_fn: Optional[Callable] = None,
        process_chunk: Optional[Callable] = None,
    ):
        super().__init__(
            stream=stream,
            trace_container=trace_container,
            reduce_fn=reduce_fn,
        )
        self.__ls_stream__ = stream
        self.__ls__gen__ = _process_iterator(
            self.__ls_stream__,
            self.__ls_trace_container__,
            is_llm_run=self.__is_llm_run__,
            results=self.__ls_accumulated_output__,
            process_chunk=process_chunk,
        )

    def __next__(self) -> T:
        try:
            return next(self.__ls__gen__)
        except StopIteration:
            self._end_trace()
            raise

    def __iter__(self) -> Iterator[T]:
        try:
            yield from self.__ls__gen__
        except BaseException as e:
            _cleanup_traceback(e)
            self._end_trace(error=e)
            raise
        else:
            self._end_trace()

    def __enter__(self):
        return self.__ls_stream__.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return self.__ls_stream__.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self._end_trace(error=exc_val if exc_type else None)


class _TracedAsyncStream(_TracedStreamBase, Generic[T]):
    """A wrapper for asynchronous stream objects that handles tracing."""

    def __init__(
        self,
        stream: AsyncIterator[T],
        trace_container: _TraceableContainer,
        reduce_fn: Optional[Callable] = None,
        process_chunk: Optional[Callable] = None,
    ):
        super().__init__(
            stream=stream,
            trace_container=trace_container,
            reduce_fn=reduce_fn,
        )
        self.__ls_stream__ = stream
        self.__ls_gen = _process_async_iterator(
            generator=self.__ls_stream__,
            run_container=self.__ls_trace_container__,
            is_llm_run=self.__is_llm_run__,
            accepts_context=aitertools.asyncio_accepts_context(),
            results=self.__ls_accumulated_output__,
            process_chunk=process_chunk,
        )

    async def _aend_trace(self, error: Optional[BaseException] = None):
        ctx = copy_context()
        await asyncio.shield(
            aitertools.aio_to_thread(self._end_trace, error, __ctx=ctx)
        )
        _set_tracing_context(get_tracing_context(ctx))

    async def __anext__(self) -> T:
        try:
            return cast(T, await aitertools.py_anext(self.__ls_gen))
        except StopAsyncIteration:
            await self._aend_trace()
            raise

    async def __aiter__(self) -> AsyncIterator[T]:
        try:
            async for item in self.__ls_gen:
                yield item
        except BaseException:
            await self._aend_trace()
            raise
        else:
            await self._aend_trace()

    async def __aenter__(self):
        return await self.__ls_stream__.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            return await self.__ls_stream__.__aexit__(exc_type, exc_val, exc_tb)
        finally:
            await self._aend_trace()


def _get_function_result(results: list, reduce_fn: Callable) -> Any:
    if results:
        if reduce_fn is not None:
            try:
                return reduce_fn(results)
            except BaseException as e:
                LOGGER.error(e)
                return results
        else:
            return results


def _cleanup_traceback(e: BaseException):
    tb_ = e.__traceback__
    if tb_:
        while tb_.tb_next is not None and tb_.tb_frame.f_code.co_filename.endswith(
            _EXCLUDED_FRAME_FNAME
        ):
            tb_ = tb_.tb_next
        e.__traceback__ = tb_


def _is_otel_available() -> bool:
    """Cache for otel import check."""
    global _OTEL_AVAILABLE
    if _OTEL_AVAILABLE is None:
        try:
            import opentelemetry.trace  # noqa: F401

            _OTEL_AVAILABLE = True
        except ImportError:
            _OTEL_AVAILABLE = False
    return _OTEL_AVAILABLE


def _maybe_create_otel_context(run_tree: Optional[run_trees.RunTree]):
    """Create OpenTelemetry context manager if OTEL is enabled and available.

    Args:
        run_tree: The current run tree.

    Returns:
        Context manager for use_span or None if not available.
    """
    if not run_tree or not utils.is_truish(utils.get_env_var("OTEL_ENABLED")):
        return None
    if not _is_otel_available():
        return None

    from opentelemetry.trace import (  # type: ignore[import]
        NonRecordingSpan,
        SpanContext,
        TraceFlags,
        TraceState,
        use_span,
    )

    from langsmith._internal._otel_utils import (
        get_otel_span_id_from_uuid,
        get_otel_trace_id_from_uuid,
    )

    trace_id = get_otel_trace_id_from_uuid(run_tree.trace_id)
    span_id = get_otel_span_id_from_uuid(run_tree.id)

    span_context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )

    non_recording_span = NonRecordingSpan(span_context)
    return use_span(non_recording_span)
