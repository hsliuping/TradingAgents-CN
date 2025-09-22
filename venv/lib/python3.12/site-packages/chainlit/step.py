import asyncio
import inspect
import json
import time
import uuid
from copy import deepcopy
from functools import wraps
from typing import Callable, Dict, List, Optional, TypedDict, Union

from literalai import BaseGeneration
from literalai.observability.step import StepType, TrueStepType

from chainlit.config import config
from chainlit.context import CL_RUN_NAMES, context, local_steps
from chainlit.data import get_data_layer
from chainlit.element import Element
from chainlit.logger import logger
from chainlit.types import FeedbackDict
from chainlit.utils import utc_now


def check_add_step_in_cot(step: "Step"):
    is_message = step.type in [
        "user_message",
        "assistant_message",
    ]
    is_cl_run = step.name in CL_RUN_NAMES and step.type == "run"
    if config.ui.cot == "hidden" and not is_message and not is_cl_run:
        return False
    return True


def stub_step(step: "Step") -> "StepDict":
    return {
        "type": step.type,
        "name": step.name,
        "id": step.id,
        "parentId": step.parent_id,
        "threadId": step.thread_id,
        "input": "",
        "output": "",
    }


class StepDict(TypedDict, total=False):
    name: str
    type: StepType
    id: str
    threadId: str
    parentId: Optional[str]
    command: Optional[str]
    streaming: bool
    waitForAnswer: Optional[bool]
    isError: Optional[bool]
    metadata: Dict
    tags: Optional[List[str]]
    input: str
    output: str
    createdAt: Optional[str]
    start: Optional[str]
    end: Optional[str]
    generation: Optional[Dict]
    showInput: Optional[Union[bool, str]]
    defaultOpen: Optional[bool]
    language: Optional[str]
    feedback: Optional[FeedbackDict]


def flatten_args_kwargs(func, args, kwargs):
    signature = inspect.signature(func)
    bound_arguments = signature.bind(*args, **kwargs)
    bound_arguments.apply_defaults()
    return {k: deepcopy(v) for k, v in bound_arguments.arguments.items()}


def step(
    original_function: Optional[Callable] = None,
    *,
    name: Optional[str] = "",
    type: TrueStepType = "undefined",
    id: Optional[str] = None,
    parent_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict] = None,
    language: Optional[str] = None,
    show_input: Union[bool, str] = "json",
    default_open: bool = False,
):
    """Step decorator for async and sync functions."""

    def wrapper(func: Callable):
        nonlocal name
        if not name:
            name = func.__name__

        # Handle async decorator

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with Step(
                    type=type,
                    name=name,
                    id=id,
                    parent_id=parent_id,
                    tags=tags,
                    language=language,
                    show_input=show_input,
                    default_open=default_open,
                    metadata=metadata,
                ) as step:
                    try:
                        step.input = flatten_args_kwargs(func, args, kwargs)
                    except Exception as e:
                        logger.exception(e)
                    result = await func(*args, **kwargs)
                    try:
                        if result and not step.output:
                            step.output = result
                    except Exception as e:
                        step.is_error = True
                        step.output = str(e)
                    return result

            return async_wrapper
        else:
            # Handle sync decorator
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with Step(
                    type=type,
                    name=name,
                    id=id,
                    parent_id=parent_id,
                    tags=tags,
                    language=language,
                    show_input=show_input,
                    default_open=default_open,
                    metadata=metadata,
                ) as step:
                    try:
                        step.input = flatten_args_kwargs(func, args, kwargs)
                    except Exception as e:
                        logger.exception(e)
                    result = func(*args, **kwargs)
                    try:
                        if result and not step.output:
                            step.output = result
                    except Exception as e:
                        step.is_error = True
                        step.output = str(e)
                    return result

            return sync_wrapper

    func = original_function
    if not func:
        return wrapper
    else:
        return wrapper(func)


class Step:
    # Constructor
    name: str
    type: TrueStepType
    id: str
    parent_id: Optional[str]

    streaming: bool
    persisted: bool

    show_input: Union[bool, str]

    is_error: Optional[bool]
    metadata: Dict
    tags: Optional[List[str]]
    thread_id: str
    created_at: Union[str, None]
    start: Union[str, None]
    end: Union[str, None]
    generation: Optional[BaseGeneration]
    language: Optional[str]
    default_open: Optional[bool]
    elements: Optional[List[Element]]
    fail_on_persist_error: bool

    def __init__(
        self,
        name: Optional[str] = config.ui.name,
        type: TrueStepType = "undefined",
        id: Optional[str] = None,
        parent_id: Optional[str] = None,
        elements: Optional[List[Element]] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        language: Optional[str] = None,
        default_open: Optional[bool] = False,
        show_input: Union[bool, str] = "json",
        thread_id: Optional[str] = None,
    ):
        time.sleep(0.001)
        self._input = ""
        self._output = ""
        self.thread_id = thread_id or context.session.thread_id
        self.name = name or ""
        self.type = type
        self.id = id or str(uuid.uuid4())
        self.metadata = metadata or {}
        self.tags = tags
        self.is_error = False
        self.show_input = show_input
        self.parent_id = parent_id

        self.language = language
        self.default_open = default_open
        self.generation = None
        self.elements = elements or []

        self.created_at = utc_now()
        self.start = None
        self.end = None

        self.streaming = False
        self.persisted = False
        self.fail_on_persist_error = False

    def _clean_content(self, content):
        """
        Recursively checks and converts bytes objects in content.
        """

        def handle_bytes(item):
            if isinstance(item, bytes):
                return "STRIPPED_BINARY_DATA"
            elif isinstance(item, dict):
                return {k: handle_bytes(v) for k, v in item.items()}
            elif isinstance(item, list):
                return [handle_bytes(i) for i in item]
            elif isinstance(item, tuple):
                return tuple(handle_bytes(i) for i in item)
            return item

        return handle_bytes(content)

    def _process_content(self, content, set_language=False):
        if content is None:
            return ""
        content = self._clean_content(content)

        if (
            isinstance(content, dict)
            or isinstance(content, list)
            or isinstance(content, tuple)
        ):
            try:
                processed_content = json.dumps(content, indent=4, ensure_ascii=False)
                if set_language:
                    self.language = "json"
            except TypeError:
                processed_content = str(content).replace("\\n", "\n")
                if set_language:
                    self.language = "text"
        elif isinstance(content, str):
            processed_content = content
        else:
            processed_content = str(content).replace("\\n", "\n")
            if set_language:
                self.language = "text"
        return processed_content

    @property
    def input(self):
        return self._input

    @input.setter
    def input(self, content: Union[Dict, str]):
        self._input = self._process_content(content, set_language=False)

    @property
    def output(self):
        return self._output

    @output.setter
    def output(self, content: Union[Dict, str]):
        self._output = self._process_content(content, set_language=True)

    def to_dict(self) -> StepDict:
        _dict: StepDict = {
            "name": self.name,
            "type": self.type,
            "id": self.id,
            "threadId": self.thread_id,
            "parentId": self.parent_id,
            "streaming": self.streaming,
            "metadata": self.metadata,
            "tags": self.tags,
            "input": self.input,
            "isError": self.is_error,
            "output": self.output,
            "createdAt": self.created_at,
            "start": self.start,
            "end": self.end,
            "language": self.language,
            "defaultOpen": self.default_open,
            "showInput": self.show_input,
            "generation": self.generation.to_dict() if self.generation else None,
        }
        return _dict

    async def update(self):
        """
        Update a step already sent to the UI.
        """
        if self.streaming:
            self.streaming = False

        step_dict = self.to_dict()
        data_layer = get_data_layer()

        if data_layer:
            try:
                asyncio.create_task(data_layer.update_step(step_dict.copy()))
            except Exception as e:
                if self.fail_on_persist_error:
                    raise e
                logger.error(f"Failed to persist step update: {e!s}")

        tasks = [el.send(for_id=self.id) for el in self.elements]
        await asyncio.gather(*tasks)

        if not check_add_step_in_cot(self):
            await context.emitter.update_step(stub_step(self))
        else:
            await context.emitter.update_step(step_dict)

        return True

    async def remove(self):
        """
        Remove a step already sent to the UI.
        """
        step_dict = self.to_dict()
        data_layer = get_data_layer()

        if data_layer:
            try:
                asyncio.create_task(data_layer.delete_step(self.id))
            except Exception as e:
                if self.fail_on_persist_error:
                    raise e
                logger.error(f"Failed to persist step deletion: {e!s}")

        await context.emitter.delete_step(step_dict)

        return True

    async def send(self):
        if self.persisted:
            return self

        if config.code.author_rename:
            self.name = await config.code.author_rename(self.name)

        if self.streaming:
            self.streaming = False

        step_dict = self.to_dict()

        data_layer = get_data_layer()

        if data_layer:
            try:
                asyncio.create_task(data_layer.create_step(step_dict.copy()))
                self.persisted = True
            except Exception as e:
                if self.fail_on_persist_error:
                    raise e
                logger.error(f"Failed to persist step creation: {e!s}")

        tasks = [el.send(for_id=self.id) for el in self.elements]
        await asyncio.gather(*tasks)

        if not check_add_step_in_cot(self):
            await context.emitter.send_step(stub_step(self))
        else:
            await context.emitter.send_step(step_dict)

        return self

    async def stream_token(self, token: str, is_sequence=False, is_input=False):
        """
        Sends a token to the UI.
        Once all tokens have been streamed, call .send() to end the stream and persist the step if persistence is enabled.
        """
        if not token:
            return

        if is_sequence:
            if is_input:
                self.input = token
            else:
                self.output = token
        else:
            if is_input:
                self.input += token
            else:
                self.output += token

        assert self.id

        if not check_add_step_in_cot(self):
            await context.emitter.send_step(stub_step(self))
            return

        if not self.streaming:
            self.streaming = True
            step_dict = self.to_dict()
            await context.emitter.stream_start(step_dict)
        else:
            await context.emitter.send_token(
                id=self.id, token=token, is_sequence=is_sequence, is_input=is_input
            )

    # Handle parameter less decorator
    def __call__(self, func):
        return step(
            original_function=func,
            type=self.type,
            name=self.name,
            id=self.id,
            parent_id=self.parent_id,
            thread_id=self.thread_id,
        )

    # Handle Context Manager Protocol
    async def __aenter__(self):
        self.start = utc_now()
        previous_steps = local_steps.get() or []
        parent_step = previous_steps[-1] if previous_steps else None

        if not self.parent_id:
            if parent_step:
                self.parent_id = parent_step.id
        local_steps.set(previous_steps + [self])
        await self.send()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end = utc_now()

        if exc_type:
            self.output = str(exc_val)
            self.is_error = True

        current_steps = local_steps.get()
        if current_steps and self in current_steps:
            current_steps.remove(self)
            local_steps.set(current_steps)

        await self.update()

    def __enter__(self):
        self.start = utc_now()

        previous_steps = local_steps.get() or []
        parent_step = previous_steps[-1] if previous_steps else None

        if not self.parent_id:
            if parent_step:
                self.parent_id = parent_step.id
        local_steps.set(previous_steps + [self])

        asyncio.create_task(self.send())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end = utc_now()

        if exc_type:
            self.output = str(exc_val)
            self.is_error = True

        current_steps = local_steps.get()
        if current_steps and self in current_steps:
            current_steps.remove(self)
            local_steps.set(current_steps)

        asyncio.create_task(self.update())
