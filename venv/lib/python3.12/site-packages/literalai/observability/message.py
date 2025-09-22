import uuid
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from literalai.event_processor import EventProcessor

from literalai.context import active_root_run_var, active_steps_var, active_thread_var
from literalai.helper import utc_now
from literalai.my_types import Utils
from literalai.observability.step import Attachment, MessageStepType, Score, StepDict


class Message(Utils):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[MessageStepType] = None
    metadata: Optional[Dict] = {}
    parent_id: Optional[str] = None
    timestamp: Optional[str] = None
    content: str
    thread_id: Optional[str] = None
    root_run_id: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: Optional[str] = None

    scores: List[Score] = []
    attachments: List[Attachment] = []

    def __init__(
        self,
        content: str,
        id: Optional[str] = None,
        type: Optional[MessageStepType] = "assistant_message",
        name: Optional[str] = None,
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        scores: List[Score] = [],
        attachments: List[Attachment] = [],
        metadata: Optional[Dict] = {},
        timestamp: Optional[str] = None,
        tags: Optional[List[str]] = [],
        processor: Optional["EventProcessor"] = None,
        root_run_id: Optional[str] = None,
    ):
        from time import sleep

        sleep(0.001)

        self.id = id or str(uuid.uuid4())
        if not timestamp:
            self.timestamp = utc_now()
        else:
            self.timestamp = timestamp
        self.name = name
        self.type = type
        self.content = content
        self.scores = scores
        self.attachments = attachments
        self.metadata = metadata
        self.tags = tags

        self.processor = processor

        # priority for thread_id: thread_id > parent_step.thread_id > active_thread
        self.thread_id = thread_id

        # priority for root_run_id: root_run_id > parent_step.root_run_id > active_root_run
        self.root_run_id = root_run_id

        # priority for parent_id: parent_id > parent_step.id
        self.parent_id = parent_id

    def end(self):
        active_steps = active_steps_var.get()

        if active_steps:
            parent_step = active_steps[-1]
            if not self.parent_id:
                self.parent_id = parent_step.id
            if not self.thread_id:
                self.thread_id = parent_step.thread_id
            if not self.root_run_id:
                self.root_run_id = parent_step.root_run_id

        if not self.thread_id:
            if active_thread := active_thread_var.get():
                self.thread_id = active_thread.id

        if not self.root_run_id:
            if active_root_run := active_root_run_var.get():
                self.root_run_id = active_root_run.id

        if not self.thread_id and not self.parent_id:
            raise Exception(
                "Message must be initialized with a thread_id or a parent id."
            )

        if self.processor is None:
            raise Exception(
                "Message must be initialized with a processor to allow finalization."
            )
        self.processor.add_event(self.to_dict())

    def to_dict(self) -> "StepDict":
        # Create a correct step Dict from a message
        return {
            "id": self.id,
            "metadata": self.metadata,
            "parentId": self.parent_id,
            "startTime": self.timestamp,
            "endTime": self.timestamp,  # startTime = endTime in Message
            "type": self.type,
            "threadId": self.thread_id,
            "output": {
                "content": self.content
            },  # no input, output = content in Message
            "name": self.name,
            "tags": self.tags,
            "scores": [score.to_dict() for score in self.scores],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "rootRunId": self.root_run_id,
        }

    @classmethod
    def from_dict(cls, message_dict: Dict) -> "Message":
        id = message_dict.get("id", None)
        type = message_dict.get("type", None)
        thread_id = message_dict.get("threadId", None)
        root_run_id = message_dict.get("rootRunId", None)

        metadata = message_dict.get("metadata", None)
        parent_id = message_dict.get("parentId", None)
        timestamp = message_dict.get("startTime", None)
        content = message_dict.get("output", {}).get("content", "")
        name = message_dict.get("name", None)
        scores = message_dict.get("scores", [])
        attachments = message_dict.get("attachments", [])

        message = cls(
            id=id,
            metadata=metadata,
            parent_id=parent_id,
            timestamp=timestamp,
            type=type,
            thread_id=thread_id,
            content=content,
            name=name,
            scores=scores,
            attachments=attachments,
            root_run_id=root_run_id,
        )

        message.created_at = message_dict.get("createdAt", None)

        return message
