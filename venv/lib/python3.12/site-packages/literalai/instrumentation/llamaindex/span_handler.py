import uuid
from typing import Any, Dict, Optional

from llama_index.core.instrumentation.span import SimpleSpan
from llama_index.core.instrumentation.span_handlers.base import BaseSpanHandler
from llama_index.core.query_engine import RetrieverQueryEngine
from typing_extensions import TypedDict

from literalai.context import active_thread_var

literalai_uuid_namespace = uuid.UUID("05f6b2b5-a912-47bd-958f-98a9c4496322")


class SpanEntry(TypedDict):
    id: str
    parent_id: Optional[str]
    root_id: Optional[str]
    is_run_root: bool


class LiteralSpanHandler(BaseSpanHandler[SimpleSpan]):
    """This class handles spans coming from LlamaIndex."""

    spans: Dict[str, SpanEntry] = {}

    def __init__(self):
        super().__init__()

    def new_span(
        self,
        id_: str,
        bound_args: Any,
        instance: Optional[Any] = None,
        parent_span_id: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        self.spans[id_] = {
            "id": id_,
            "parent_id": parent_span_id,
            "root_id": None,
            "is_run_root": self.is_run_root(instance, parent_span_id),
        }

        if parent_span_id is not None:
            self.spans[id_]["root_id"] = self.get_root_span_id(parent_span_id)
        else:
            self.spans[id_]["root_id"] = id_

    def prepare_to_exit_span(
        self,
        id_: str,
        bound_args: Any,
        instance: Optional[Any] = None,
        result: Optional[Any] = None,
        **kwargs: Any,
    ):
        """Logic for preparing to exit a span."""
        if id_ in self.spans:
            del self.spans[id_]

    def prepare_to_drop_span(
        self,
        id_: str,
        bound_args: Any,
        instance: Optional[Any] = None,
        err: Optional[BaseException] = None,
        **kwargs: Any,
    ):
        """Logic for preparing to drop a span."""
        if id_ in self.spans:
            del self.spans[id_]

    def is_run_root(
        self, instance: Optional[Any], parent_span_id: Optional[str]
    ) -> bool:
        """Returns True if the span is of type RetrieverQueryEngine, and it has no run root in its parent chain"""
        if not isinstance(instance, RetrieverQueryEngine):
            return False

        # Span is of correct type, we check that it doesn't have a run root in its parent chain
        while parent_span_id:
            parent_span = self.spans.get(parent_span_id)

            if not parent_span:
                parent_span_id = None
                continue

            if parent_span["is_run_root"]:
                return False

            parent_span_id = parent_span["parent_id"]

        return True

    def get_root_span_id(self, span_id: Optional[str]):
        """Finds the root span and returns its ID"""
        if not span_id:
            return None

        current_span = self.spans.get(span_id)

        if current_span is None:
            return None

        while current_span["parent_id"] is not None:
            current_span = self.spans.get(current_span["parent_id"])
            if current_span is None:
                return None

        return current_span["id"]

    def get_run_id(self, span_id: Optional[str]):
        """Go up the span chain to find a run_root, return its ID (or None)"""
        if not span_id:
            return None

        current_span = self.spans.get(span_id)

        if current_span is None:
            return None

        while current_span:
            if current_span["is_run_root"]:
                return str(uuid.uuid5(literalai_uuid_namespace, current_span["id"]))

            parent_id = current_span["parent_id"]

            if parent_id:
                current_span = self.spans.get(parent_id)
            else:
                current_span = None

        return None

    def get_thread_id(self, span_id: Optional[str]):
        """Returns the root span ID as a thread ID"""
        active_thread = active_thread_var.get()

        if active_thread:
            return active_thread.id

        if span_id is None:
            return None

        current_span = self.spans.get(span_id)

        if current_span is None:
            return None

        root_id = current_span["root_id"]

        if not root_id:
            return None

        root_span = self.spans.get(root_id)

        if root_span is None:
            # span is already the root, uuid its own id
            return str(uuid.uuid5(literalai_uuid_namespace, span_id))
        else:
            # uuid the id of the root span
            return str(uuid.uuid5(literalai_uuid_namespace, root_span["id"]))

    @classmethod
    def class_name(cls) -> str:
        """Class name."""
        return "LiteralSpanHandler"
