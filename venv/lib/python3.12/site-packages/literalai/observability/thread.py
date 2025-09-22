import inspect
import logging
import traceback
import uuid
from functools import wraps
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, TypedDict

from traceloop.sdk import Traceloop

from literalai.context import active_thread_var
from literalai.my_types import UserDict, Utils
from literalai.observability.step import Step, StepDict

if TYPE_CHECKING:
    from literalai.client import BaseLiteralClient

logger = logging.getLogger(__name__)


class ThreadDict(TypedDict, total=False):
    id: Optional[str]
    name: Optional[str]
    metadata: Optional[Dict]
    tags: Optional[List[str]]
    createdAt: Optional[str]
    steps: Optional[List[StepDict]]
    participant: Optional[UserDict]


class Thread(Utils):
    """
    ## Using the `with` statement

    If you prefer to have more flexibility in logging Threads, you can use the `with` statement. You can create a thread and execute code within it using the `with` statement:

    <CodeGroup>
    ```python
    with literal_client.thread() as thread:
        # do something
    ```
    </CodeGroup>

    You can also continue a thread by passing the thread id to the `thread` method:

    <CodeGroup>
    ```python

    previous_thread_id = "UUID"

    with literal_client.thread(thread_id=previous_thread_id) as thread:
        # do something
    ```
    </CodeGroup>

    ## Using the Literal AI API client

    You can also create Threads using the `literal_client.api.create_thread()` method.

    <CodeGroup>
    ```python
    thread = literal_client.api.create_thread(
        participant_id="<PARTICIPANT_UUID>",
        environment="production",
        tags=["tag1", "tag2"],
        metadata={"key": "value"},
    )
    ```
    </CodeGroup>

    ## Using Chainlit

    If you built your LLM application with Chainlit, you don't need to specify Threads in your code. Chainlit logs Threads for you by default.
    """

    id: str
    name: Optional[str]
    metadata: Optional[Dict]
    tags: Optional[List[str]]
    steps: Optional[List[Step]]
    participant_id: Optional[str]
    participant_identifier: Optional[str] = None
    created_at: Optional[str]

    def __init__(
        self,
        id: str,
        steps: Optional[List[Step]] = [],
        name: Optional[str] = None,
        metadata: Optional[Dict] = {},
        tags: Optional[List[str]] = [],
        participant_id: Optional[str] = None,
    ):
        self.id = id
        self.steps = steps
        self.name = name
        self.metadata = metadata
        self.tags = tags
        self.participant_id = participant_id

    def to_dict(self) -> ThreadDict:
        return {
            "id": self.id,
            "metadata": self.metadata,
            "tags": self.tags,
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps] if self.steps else [],
            "participant": (
                UserDict(id=self.participant_id, identifier=self.participant_identifier)
                if self.participant_id
                else UserDict()
            ),
            "createdAt": getattr(self, "created_at", None),
        }

    @classmethod
    def from_dict(cls, thread_dict: ThreadDict) -> "Thread":
        step_dict_list = thread_dict.get("steps", None) or []
        id = thread_dict.get("id", None) or ""
        name = thread_dict.get("name", None)
        metadata = thread_dict.get("metadata", {})
        tags = thread_dict.get("tags", [])
        steps = [Step.from_dict(step_dict) for step_dict in step_dict_list]
        participant = thread_dict.get("participant", None)
        participant_id = participant.get("id", None) if participant else None
        participant_identifier = (
            participant.get("identifier", None) if participant else None
        )
        created_at = thread_dict.get("createdAt", None)

        thread = cls(
            id=id,
            steps=steps,
            name=name,
            metadata=metadata,
            tags=tags,
            participant_id=participant_id,
        )

        thread.created_at = created_at
        thread.participant_identifier = participant_identifier

        return thread


class ThreadContextManager:
    def __init__(
        self,
        client: "BaseLiteralClient",
        thread_id: "Optional[str]" = None,
        name: "Optional[str]" = None,
        **kwargs,
    ):
        self.client = client
        self.thread_id = thread_id
        self.name = name
        self.kwargs = kwargs

    def upsert(self):
        if self.client.disabled:
            return

        thread = active_thread_var.get()
        thread_data = thread.to_dict()
        thread_data_to_upsert = {
            "id": thread_data["id"],
            "name": thread_data["name"],
        }

        metadata = {
            **(self.client.global_metadata or {}),
            **(thread_data.get("metadata") or {}),
        }
        if metadata:
            thread_data_to_upsert["metadata"] = metadata
        if tags := thread_data.get("tags"):
            thread_data_to_upsert["tags"] = tags
        if participant_id := thread_data.get("participant", {}).get("id"):
            thread_data_to_upsert["participant_id"] = participant_id

        try:
            self.client.to_sync().api.upsert_thread(**thread_data_to_upsert)
        except Exception:
            logger.error(f"Failed to upsert thread: {traceback.format_exc()}")

    def __call__(self, func):
        return thread_decorator(
            self.client, func=func, name=self.name, ctx_manager=self
        )

    def __enter__(self) -> "Optional[Thread]":
        thread_id = self.thread_id if self.thread_id else str(uuid.uuid4())
        active_thread_var.set(Thread(id=thread_id, name=self.name, **self.kwargs))
        Traceloop.set_association_properties(
            {
                "literal.thread_id": thread_id,
            }
        )
        return active_thread_var.get()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if active_thread_var.get():
            self.upsert()
        active_thread_var.set(None)

    async def __aenter__(self):
        thread_id = self.thread_id if self.thread_id else str(uuid.uuid4())
        active_thread_var.set(Thread(id=thread_id, name=self.name, **self.kwargs))
        Traceloop.set_association_properties(
            {
                "literal.thread_id": thread_id,
            }
        )
        return active_thread_var.get()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if active_thread_var.get():
            self.upsert()
        active_thread_var.set(None)


def thread_decorator(
    client: "BaseLiteralClient",
    func: Callable,
    thread_id: Optional[str] = None,
    name: Optional[str] = None,
    ctx_manager: Optional[ThreadContextManager] = None,
    **decorator_kwargs,
):
    if not ctx_manager:
        ctx_manager = ThreadContextManager(
            client, thread_id=thread_id, name=name, **decorator_kwargs
        )
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with ctx_manager:
                result = await func(*args, **kwargs)
                return result

        return async_wrapper
    else:

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with ctx_manager:
                return func(*args, **kwargs)

        return sync_wrapper
