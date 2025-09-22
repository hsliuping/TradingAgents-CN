"""Schemas for the LangSmith API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    NamedTuple,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)
from uuid import UUID

from typing_extensions import NotRequired, TypedDict

try:
    from pydantic.v1 import (
        BaseModel,
        Field,  # type: ignore[import]
        PrivateAttr,
        StrictBool,
        StrictFloat,
        StrictInt,
    )
except ImportError:
    from pydantic import (  # type: ignore[assignment]
        BaseModel,
        Field,
        PrivateAttr,
        StrictBool,
        StrictFloat,
        StrictInt,
    )

from pathlib import Path

from typing_extensions import Literal

SCORE_TYPE = Union[StrictBool, StrictInt, StrictFloat, None]
VALUE_TYPE = Union[dict, str, None]


class Attachment(NamedTuple):
    """Annotated type that will be stored as an attachment if used.

    Examples:

        .. code-block:: python

            from langsmith import traceable
            from langsmith.schemas import Attachment


            @traceable
            def my_function(bar: int, my_val: Attachment):
                # my_val will be stored as an attachment
                # bar will be stored as inputs
                return bar
    """

    mime_type: str
    data: Union[bytes, Path]


Attachments = dict[str, Union[tuple[str, bytes], Attachment, tuple[str, Path]]]
"""Attachments associated with the run. 
Each entry is a tuple of (mime_type, bytes), or (mime_type, file_path)"""


@runtime_checkable
class BinaryIOLike(Protocol):
    """Protocol for binary IO-like objects."""

    def read(self, size: int = -1) -> bytes:
        """Read function."""
        ...

    def seek(self, offset: int, whence: int = 0) -> int:
        """Seek function."""
        ...

    def getvalue(self) -> bytes:
        """Get value function."""
        ...


class ExampleBase(BaseModel):
    """Example base model."""

    dataset_id: UUID
    inputs: Optional[dict[str, Any]] = Field(default=None)
    outputs: Optional[dict[str, Any]] = Field(default=None)
    metadata: Optional[dict[str, Any]] = Field(default=None)

    class Config:
        """Configuration class for the schema."""

        frozen = True
        arbitrary_types_allowed = True


class _AttachmentDict(TypedDict):
    mime_type: str
    data: Union[bytes, Path]


_AttachmentLike = Union[
    Attachment, _AttachmentDict, tuple[str, bytes], tuple[str, Path]
]


class ExampleCreate(BaseModel):
    """Example upload with attachments."""

    id: Optional[UUID]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    inputs: Optional[dict[str, Any]] = Field(default=None)
    outputs: Optional[dict[str, Any]] = Field(default=None)
    metadata: Optional[dict[str, Any]] = Field(default=None)
    split: Optional[Union[str, list[str]]] = None
    attachments: Optional[dict[str, _AttachmentLike]] = None
    use_source_run_io: bool = False
    use_source_run_attachments: Optional[list[str]] = None
    source_run_id: Optional[UUID] = None

    def __init__(self, **data):
        """Initialize from dict."""
        super().__init__(**data)


ExampleUploadWithAttachments = ExampleCreate


class ExampleUpsertWithAttachments(ExampleCreate):
    """Example create with attachments."""

    dataset_id: UUID


class AttachmentInfo(TypedDict):
    """Info for an attachment."""

    presigned_url: str
    reader: BinaryIOLike
    mime_type: Optional[str]


class Example(ExampleBase):
    """Example model."""

    id: UUID
    created_at: datetime = Field(
        default_factory=lambda: datetime.fromtimestamp(0, tz=timezone.utc)
    )
    dataset_id: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000000"))
    modified_at: Optional[datetime] = Field(default=None)
    runs: list[Run] = Field(default_factory=list)
    source_run_id: Optional[UUID] = None
    attachments: Optional[dict[str, AttachmentInfo]] = Field(default=None)
    """Dictionary with attachment names as keys and a tuple of the S3 url
    and a reader of the data for the file."""
    _host_url: Optional[str] = PrivateAttr(default=None)
    _tenant_id: Optional[UUID] = PrivateAttr(default=None)

    def __init__(
        self,
        _host_url: Optional[str] = None,
        _tenant_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a Dataset object."""
        super().__init__(**kwargs)
        self._host_url = _host_url
        self._tenant_id = _tenant_id

    @property
    def url(self) -> Optional[str]:
        """URL of this run within the app."""
        if self._host_url:
            path = f"/datasets/{self.dataset_id}/e/{self.id}"
            if self._tenant_id:
                return f"{self._host_url}/o/{str(self._tenant_id)}{path}"
            return f"{self._host_url}{path}"
        return None

    def __repr__(self):
        """Return a string representation of the RunBase object."""
        return f"{self.__class__}(id={self.id}, dataset_id={self.dataset_id}, link='{self.url}')"


class ExampleSearch(ExampleBase):
    """Example returned via search."""

    id: UUID


class AttachmentsOperations(BaseModel):
    """Operations to perform on attachments."""

    rename: dict[str, str] = Field(
        default_factory=dict, description="Mapping of old attachment names to new names"
    )
    retain: list[str] = Field(
        default_factory=list, description="List of attachment names to keep"
    )


class ExampleUpdate(BaseModel):
    """Example update with attachments."""

    id: UUID
    dataset_id: Optional[UUID] = None
    inputs: Optional[dict[str, Any]] = Field(default=None)
    outputs: Optional[dict[str, Any]] = Field(default=None)
    metadata: Optional[dict[str, Any]] = Field(default=None)
    split: Optional[Union[str, list[str]]] = None
    attachments: Optional[Attachments] = None
    attachments_operations: Optional[AttachmentsOperations] = None

    class Config:
        """Configuration class for the schema."""

        frozen = True

    def __init__(self, **data):
        """Initialize from dict."""
        super().__init__(**data)


ExampleUpdateWithAttachments = ExampleUpdate


class DataType(str, Enum):
    """Enum for dataset data types."""

    kv = "kv"
    llm = "llm"
    chat = "chat"


class DatasetBase(BaseModel):
    """Dataset base model."""

    name: str
    description: Optional[str] = None
    data_type: Optional[DataType] = None

    class Config:
        """Configuration class for the schema."""

        frozen = True


DatasetTransformationType = Literal[
    "remove_system_messages",
    "convert_to_openai_message",
    "convert_to_openai_tool",
    "remove_extra_fields",
    "extract_tools_from_run",
]


class DatasetTransformation(TypedDict, total=False):
    """Schema for dataset transformations."""

    path: list[str]
    transformation_type: Union[DatasetTransformationType, str]


class Dataset(DatasetBase):
    """Dataset ORM model."""

    id: UUID
    created_at: datetime
    modified_at: Optional[datetime] = Field(default=None)
    example_count: Optional[int] = None
    session_count: Optional[int] = None
    last_session_start_time: Optional[datetime] = None
    inputs_schema: Optional[dict[str, Any]] = None
    outputs_schema: Optional[dict[str, Any]] = None
    transformations: Optional[list[DatasetTransformation]] = None
    _host_url: Optional[str] = PrivateAttr(default=None)
    _tenant_id: Optional[UUID] = PrivateAttr(default=None)
    _public_path: Optional[str] = PrivateAttr(default=None)

    def __init__(
        self,
        _host_url: Optional[str] = None,
        _tenant_id: Optional[UUID] = None,
        _public_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a Dataset object."""
        if "inputs_schema_definition" in kwargs:
            kwargs["inputs_schema"] = kwargs.pop("inputs_schema_definition")

        if "outputs_schema_definition" in kwargs:
            kwargs["outputs_schema"] = kwargs.pop("outputs_schema_definition")

        super().__init__(**kwargs)
        self._host_url = _host_url
        self._tenant_id = _tenant_id
        self._public_path = _public_path

    @property
    def url(self) -> Optional[str]:
        """URL of this run within the app."""
        if self._host_url:
            if self._public_path:
                return f"{self._host_url}{self._public_path}"
            if self._tenant_id:
                return f"{self._host_url}/o/{str(self._tenant_id)}/datasets/{self.id}"
            return f"{self._host_url}/datasets/{self.id}"
        return None


class DatasetVersion(BaseModel):
    """Class representing a dataset version."""

    tags: Optional[list[str]] = None
    as_of: datetime


def _default_extra():
    return {"metadata": {}}


class RunBase(BaseModel):
    """Base Run schema.

    A Run is a span representing a single unit of work or operation within your LLM app.
    This could be a single call to an LLM or chain, to a prompt formatting call,
    to a runnable lambda invocation. If you are familiar with OpenTelemetry,
    you can think of a run as a span.
    """

    id: UUID
    """Unique identifier for the run."""

    name: str
    """Human-readable name for the run."""

    start_time: datetime
    """Start time of the run."""

    run_type: str
    """The type of run, such as tool, chain, llm, retriever,
    embedding, prompt, parser."""

    end_time: Optional[datetime] = None
    """End time of the run, if applicable."""

    extra: Optional[dict] = Field(default_factory=_default_extra)
    """Additional metadata or settings related to the run."""

    error: Optional[str] = None
    """Error message, if the run encountered any issues."""

    serialized: Optional[dict] = None
    """Serialized object that executed the run for potential reuse."""

    events: Optional[list[dict]] = None
    """List of events associated with the run, like
    start and end events."""

    inputs: dict = Field(default_factory=dict)
    """Inputs used for the run."""

    outputs: Optional[dict] = None
    """Outputs generated by the run, if any."""

    reference_example_id: Optional[UUID] = None
    """Reference to an example that this run may be based on."""

    parent_run_id: Optional[UUID] = None
    """Identifier for a parent run, if this run is a sub-run."""

    tags: Optional[list[str]] = None
    """Tags for categorizing or annotating the run."""

    attachments: Union[Attachments, dict[str, AttachmentInfo]] = Field(
        default_factory=dict
    )
    """Attachments associated with the run.
    Each entry is a tuple of (mime_type, bytes)."""

    @property
    def metadata(self) -> dict[str, Any]:
        """Retrieve the metadata (if any)."""
        if self.extra is None:
            self.extra = {}
        return self.extra.setdefault("metadata", {})

    @property
    def revision_id(self) -> Optional[UUID]:
        """Retrieve the revision ID (if any)."""
        return self.metadata.get("revision_id")

    def __repr__(self):
        """Return a string representation of the RunBase object."""
        return f"{self.__class__}(id={self.id}, name='{self.name}', run_type='{self.run_type}')"

    class Config:
        """Configuration class for the schema."""

        arbitrary_types_allowed = True


class Run(RunBase):
    """Run schema when loading from the DB."""

    session_id: Optional[UUID] = None
    """The project ID this run belongs to."""
    child_run_ids: Optional[list[UUID]] = None
    """The child run IDs of this run."""
    child_runs: Optional[list[Run]] = None
    """The child runs of this run, if instructed to load using the client
    These are not populated by default, as it is a heavier query to make."""
    feedback_stats: Optional[dict[str, Any]] = None
    """Feedback stats for this run."""
    app_path: Optional[str] = None
    """Relative URL path of this run within the app."""
    manifest_id: Optional[UUID] = None
    """Unique ID of the serialized object for this run."""
    status: Optional[str] = None
    """Status of the run (e.g., 'success')."""
    prompt_tokens: Optional[int] = None
    """Number of tokens used for the prompt."""
    completion_tokens: Optional[int] = None
    """Number of tokens generated as output."""
    total_tokens: Optional[int] = None
    """Total tokens for prompt and completion."""
    prompt_token_details: Optional[dict[str, int]] = None
    """Breakdown of prompt (input) token counts.

    Does *not* need to sum to full prompt token count.
    """
    completion_token_details: Optional[dict[str, int]] = None
    """Breakdown of completion (output) token counts.

    Does *not* need to sum to full completion token count.
    """
    first_token_time: Optional[datetime] = None
    """Time the first token was processed."""
    total_cost: Optional[Decimal] = None
    """The total estimated LLM cost associated with the completion tokens."""
    prompt_cost: Optional[Decimal] = None
    """The estimated cost associated with the prompt (input) tokens."""
    completion_cost: Optional[Decimal] = None
    """The estimated cost associated with the completion tokens."""
    prompt_cost_details: Optional[dict[str, Decimal]] = None
    """Breakdown of prompt (input) token costs.

    Does *not* need to sum to full prompt token cost.
    """
    completion_cost_details: Optional[dict[str, Decimal]] = None
    """Breakdown of completion (output) token costs.

    Does *not* need to sum to full completion token cost.
    """
    parent_run_ids: Optional[list[UUID]] = None
    """List of parent run IDs."""
    trace_id: UUID
    """Unique ID assigned to every run within this nested trace."""
    dotted_order: str = Field(default="")
    """Dotted order for the run.

    This is a string composed of {time}{run-uuid}.* so that a trace can be
    sorted in the order it was executed.

    Example:
        - Parent: 20230914T223155647Z1b64098b-4ab7-43f6-afee-992304f198d8
        - Children:
        - 20230914T223155647Z1b64098b-4ab7-43f6-afee-992304f198d8.20230914T223155649Z809ed3a2-0172-4f4d-8a02-a64e9b7a0f8a
        - 20230915T223155647Z1b64098b-4ab7-43f6-afee-992304f198d8.20230914T223155650Zc8d9f4c5-6c5a-4b2d-9b1c-3d9d7a7c5c7c
    """  # noqa: E501
    in_dataset: Optional[bool] = None
    """Whether this run is in a dataset."""
    _host_url: Optional[str] = PrivateAttr(default=None)

    def __init__(self, _host_url: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize a Run object."""
        if not kwargs.get("trace_id"):
            kwargs = {"trace_id": kwargs.get("id"), **kwargs}
        inputs = kwargs.pop("inputs", None) or {}
        super().__init__(**kwargs, inputs=inputs)
        self._host_url = _host_url
        if not self.dotted_order.strip() and not self.parent_run_id:
            self.dotted_order = f"{self.start_time.isoformat()}{self.id}"

    @property
    def url(self) -> Optional[str]:
        """URL of this run within the app."""
        if self._host_url and self.app_path:
            return f"{self._host_url}{self.app_path}"
        return None

    @property
    def input_tokens(self) -> int | None:
        """Alias for prompt_tokens."""
        return self.prompt_tokens

    @property
    def output_tokens(self) -> int | None:
        """Alias for completion_tokens."""
        return self.completion_tokens

    @property
    def input_cost(self) -> Decimal | None:
        """Alias for prompt_cost."""
        return self.prompt_cost

    @property
    def output_cost(self) -> Decimal | None:
        """Alias for completion_cost."""
        return self.completion_cost

    @property
    def input_token_details(self) -> dict[str, int] | None:
        """Alias for prompt_token_details."""
        return self.prompt_token_details

    @property
    def output_token_details(self) -> dict[str, int] | None:
        """Alias for output_token_details."""
        return self.completion_token_details

    @property
    def input_cost_details(self) -> dict[str, Decimal] | None:
        """Alias for prompt_cost_details."""
        return self.prompt_cost_details

    @property
    def output_cost_details(self) -> dict[str, Decimal] | None:
        """Alias for completion_cost_details."""
        return self.completion_cost_details


class RunTypeEnum(str, Enum):
    """(Deprecated) Enum for run types. Use string directly."""

    tool = "tool"
    chain = "chain"
    llm = "llm"
    retriever = "retriever"
    embedding = "embedding"
    prompt = "prompt"
    parser = "parser"


class RunLikeDict(TypedDict, total=False):
    """Run-like dictionary, for type-hinting."""

    name: str
    run_type: RunTypeEnum
    start_time: datetime
    inputs: Optional[dict]
    outputs: Optional[dict]
    end_time: Optional[datetime]
    extra: Optional[dict]
    error: Optional[str]
    serialized: Optional[dict]
    parent_run_id: Optional[UUID]
    manifest_id: Optional[UUID]
    events: Optional[list[dict]]
    tags: Optional[list[str]]
    inputs_s3_urls: Optional[dict]
    outputs_s3_urls: Optional[dict]
    id: Optional[UUID]
    session_id: Optional[UUID]
    session_name: Optional[str]
    reference_example_id: Optional[UUID]
    input_attachments: Optional[dict]
    output_attachments: Optional[dict]
    trace_id: UUID
    dotted_order: str
    attachments: Attachments


class RunWithAnnotationQueueInfo(RunBase):
    """Run schema with annotation queue info."""

    last_reviewed_time: Optional[datetime] = None
    """The last time this run was reviewed."""
    added_at: Optional[datetime] = None
    """The time this run was added to the queue."""


class FeedbackSourceBase(BaseModel):
    """Base class for feedback sources.

    This represents whether feedback is submitted from the API, model, human labeler,
        etc.
    """

    type: str
    """The type of the feedback source."""
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)
    """Additional metadata for the feedback source."""
    user_id: Optional[Union[UUID, str]] = None
    """The user ID associated with the feedback source."""
    user_name: Optional[str] = None
    """The user name associated with the feedback source."""


class APIFeedbackSource(FeedbackSourceBase):
    """API feedback source."""

    type: Literal["api"] = "api"


class ModelFeedbackSource(FeedbackSourceBase):
    """Model feedback source."""

    type: Literal["model"] = "model"


class FeedbackSourceType(Enum):
    """Feedback source type."""

    API = "api"
    """General feedback submitted from the API."""
    MODEL = "model"
    """Model-assisted feedback."""


class FeedbackBase(BaseModel):
    """Feedback schema."""

    id: UUID
    """The unique ID of the feedback."""
    created_at: Optional[datetime] = None
    """The time the feedback was created."""
    modified_at: Optional[datetime] = None
    """The time the feedback was last modified."""
    run_id: Optional[UUID]
    """The associated run ID this feedback is logged for."""
    trace_id: Optional[UUID]
    """The associated trace ID this feedback is logged for."""
    key: str
    """The metric name, tag, or aspect to provide feedback on."""
    score: SCORE_TYPE = None
    """Value or score to assign the run."""
    value: VALUE_TYPE = None
    """The display value, tag or other value for the feedback if not a metric."""
    comment: Optional[str] = None
    """Comment or explanation for the feedback."""
    correction: Union[str, dict, None] = None
    """Correction for the run."""
    feedback_source: Optional[FeedbackSourceBase] = None
    """The source of the feedback."""
    session_id: Optional[UUID] = None
    """The associated project ID (Session = Project) this feedback is logged for."""
    comparative_experiment_id: Optional[UUID] = None
    """If logged within a 'comparative experiment', this is the ID of the experiment."""
    feedback_group_id: Optional[UUID] = None
    """For preference scoring, this group ID is shared across feedbacks for each

    run in the group that was being compared."""
    extra: Optional[dict] = None
    """The metadata of the feedback."""

    class Config:
        """Configuration class for the schema."""

        frozen = True


class FeedbackCategory(TypedDict, total=False):
    """Specific value and label pair for feedback."""

    value: float
    """The numeric value associated with this feedback category."""
    label: Optional[str]
    """An optional label to interpret the value for this feedback category."""


class FeedbackConfig(TypedDict, total=False):
    """Represents _how_ a feedback value ought to be interpreted."""

    type: Literal["continuous", "categorical", "freeform"]
    """The type of feedback."""
    min: Optional[float]
    """The minimum value for continuous feedback."""
    max: Optional[float]
    """The maximum value for continuous feedback."""
    categories: Optional[list[FeedbackCategory]]
    """If feedback is categorical, this defines the valid categories the server will accept.
    Not applicable to continuous or freeform feedback types."""  # noqa


class FeedbackCreate(FeedbackBase):
    """Schema used for creating feedback."""

    feedback_source: FeedbackSourceBase
    """The source of the feedback."""
    feedback_config: Optional[FeedbackConfig] = None
    """The config for the feedback"""
    error: Optional[bool] = None


class Feedback(FeedbackBase):
    """Schema for getting feedback."""

    id: UUID
    created_at: datetime
    """The time the feedback was created."""
    modified_at: datetime
    """The time the feedback was last modified."""
    feedback_source: Optional[FeedbackSourceBase] = None
    """The source of the feedback. In this case"""


class TracerSession(BaseModel):
    """TracerSession schema for the API.

    Sessions are also referred to as "Projects" in the UI.
    """

    id: UUID
    """The ID of the project."""
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """The time the project was created."""
    end_time: Optional[datetime] = None
    """The time the project was ended."""
    description: Optional[str] = None
    """The description of the project."""
    name: Optional[str] = None
    """The name of the session."""
    extra: Optional[dict[str, Any]] = None
    """Extra metadata for the project."""
    tenant_id: UUID
    """The tenant ID this project belongs to."""
    reference_dataset_id: Optional[UUID]
    """The reference dataset IDs this project's runs were generated on."""

    _host_url: Optional[str] = PrivateAttr(default=None)

    def __init__(self, _host_url: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize a Run object."""
        super().__init__(**kwargs)
        self._host_url = _host_url
        if self.start_time.tzinfo is None:
            self.start_time = self.start_time.replace(tzinfo=timezone.utc)

    @property
    def url(self) -> Optional[str]:
        """URL of this run within the app."""
        if self._host_url:
            return f"{self._host_url}/o/{self.tenant_id}/projects/p/{self.id}"
        return None

    @property
    def metadata(self) -> dict[str, Any]:
        """Retrieve the metadata (if any)."""
        if self.extra is None or "metadata" not in self.extra:
            return {}
        return self.extra["metadata"]

    @property
    def tags(self) -> list[str]:
        """Retrieve the tags (if any)."""
        if self.extra is None or "tags" not in self.extra:
            return []
        return self.extra["tags"]


class TracerSessionResult(TracerSession):
    """A project, hydrated with additional information.

    Sessions are also referred to as "Projects" in the UI.
    """

    run_count: Optional[int]
    """The number of runs in the project."""
    latency_p50: Optional[timedelta]
    """The median (50th percentile) latency for the project."""
    latency_p99: Optional[timedelta]
    """The 99th percentile latency for the project."""
    total_tokens: Optional[int]
    """The total number of tokens consumed in the project."""
    prompt_tokens: Optional[int]
    """The total number of prompt tokens consumed in the project."""
    completion_tokens: Optional[int]
    """The total number of completion tokens consumed in the project."""
    last_run_start_time: Optional[datetime]
    """The start time of the last run in the project."""
    feedback_stats: Optional[dict[str, Any]]
    """Feedback stats for the project."""
    run_facets: Optional[list[dict[str, Any]]]
    """Facets for the runs in the project."""
    total_cost: Optional[Decimal]
    """The total estimated LLM cost associated with the completion tokens."""
    prompt_cost: Optional[Decimal]
    """The estimated cost associated with the prompt (input) tokens."""
    completion_cost: Optional[Decimal]
    """The estimated cost associated with the completion tokens."""
    first_token_p50: Optional[timedelta]
    """The median (50th percentile) time to process the first token."""
    first_token_p99: Optional[timedelta]
    """The 99th percentile time to process the first token."""
    error_rate: Optional[float]
    """The error rate for the project."""


@runtime_checkable
class BaseMessageLike(Protocol):
    """A protocol representing objects similar to BaseMessage."""

    content: str
    """The content of the message."""
    additional_kwargs: dict[Any, Any]
    """Additional keyword arguments associated with the message."""

    @property
    def type(self) -> str:
        """Type of the Message, used for serialization."""


class DatasetShareSchema(TypedDict, total=False):
    """Represents the schema for a dataset share."""

    dataset_id: UUID
    """The ID of the dataset."""
    share_token: UUID
    """The token for sharing the dataset."""
    url: str
    """The URL of the shared dataset."""


class AnnotationQueue(BaseModel):
    """Represents an annotation queue."""

    id: UUID
    """The unique identifier of the annotation queue."""
    name: str
    """The name of the annotation queue."""
    description: Optional[str] = None
    """An optional description of the annotation queue."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """The timestamp when the annotation queue was created."""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """The timestamp when the annotation queue was last updated."""
    tenant_id: UUID
    """The ID of the tenant associated with the annotation queue."""


class AnnotationQueueWithDetails(AnnotationQueue):
    """Represents an annotation queue with details."""

    rubric_instructions: Optional[str] = None
    """The rubric instructions for the annotation queue."""


class BatchIngestConfig(TypedDict, total=False):
    """Configuration for batch ingestion."""

    use_multipart_endpoint: bool
    """Whether to use the multipart endpoint for batch ingestion."""
    scale_up_qsize_trigger: int
    """The queue size threshold that triggers scaling up."""
    scale_up_nthreads_limit: int
    """The maximum number of threads to scale up to."""
    scale_down_nempty_trigger: int
    """The number of empty threads that triggers scaling down."""
    size_limit: int
    """The maximum size limit for the batch."""
    size_limit_bytes: Optional[int]
    """The maximum size limit in bytes for the batch."""


class LangSmithInfo(BaseModel):
    """Information about the LangSmith server."""

    version: str = ""
    """The version of the LangSmith server."""
    license_expiration_time: Optional[datetime] = None
    """The time the license will expire."""
    batch_ingest_config: Optional[BatchIngestConfig] = None
    """The instance flags."""
    instance_flags: Optional[dict[str, Any]] = None


Example.update_forward_refs()


class LangSmithSettings(BaseModel):
    """Settings for the LangSmith tenant."""

    id: str
    """The ID of the tenant."""
    display_name: str
    """The display name of the tenant."""
    created_at: datetime
    """The creation time of the tenant."""
    tenant_handle: Optional[str] = None


class FeedbackIngestToken(BaseModel):
    """Represents the schema for a feedback ingest token."""

    id: UUID
    """The ID of the feedback ingest token."""
    url: str
    """The URL to GET when logging the feedback."""
    expires_at: datetime
    """The expiration time of the token."""


class RunEvent(TypedDict, total=False):
    """Run event schema."""

    name: str
    """Type of event."""
    time: Union[datetime, str]
    """Time of the event."""
    kwargs: Optional[dict[str, Any]]
    """Additional metadata for the event."""


class TimeDeltaInput(TypedDict, total=False):
    """Timedelta input schema."""

    days: int
    """Number of days."""
    hours: int
    """Number of hours."""
    minutes: int
    """Number of minutes."""


class DatasetDiffInfo(BaseModel):
    """Represents the difference information between two datasets."""

    examples_modified: list[UUID]
    """A list of UUIDs representing the modified examples."""
    examples_added: list[UUID]
    """A list of UUIDs representing the added examples."""
    examples_removed: list[UUID]
    """A list of UUIDs representing the removed examples."""


class ComparativeExperiment(BaseModel):
    """Represents a comparative experiment.

    This information summarizes evaluation results comparing
    two or more models on a given dataset.
    """

    id: UUID
    """The unique identifier for the comparative experiment."""
    name: Optional[str] = None
    """The optional name of the comparative experiment."""
    description: Optional[str] = None
    """An optional description of the comparative experiment."""
    tenant_id: UUID
    """The identifier of the tenant associated with this experiment."""
    created_at: datetime
    """The timestamp when the comparative experiment was created."""
    modified_at: datetime
    """The timestamp when the comparative experiment was last modified."""
    reference_dataset_id: UUID
    """The identifier of the reference dataset used in this experiment."""
    extra: Optional[dict[str, Any]] = None
    """Optional additional information about the experiment."""
    experiments_info: Optional[list[dict]] = None
    """Optional list of dictionaries containing information about individual experiments."""
    feedback_stats: Optional[dict[str, Any]] = None
    """Optional dictionary containing feedback statistics for the experiment."""

    @property
    def metadata(self) -> dict[str, Any]:
        """Retrieve the metadata (if any)."""
        if self.extra is None or "metadata" not in self.extra:
            return {}
        return self.extra["metadata"]


class PromptCommit(BaseModel):
    """Represents a Prompt with a manifest."""

    owner: str
    """The handle of the owner of the prompt."""
    repo: str
    """The name of the prompt."""
    commit_hash: str
    """The commit hash of the prompt."""
    manifest: dict[str, Any]
    """The manifest of the prompt."""
    examples: list[dict]
    """The list of examples."""


class ListedPromptCommit(BaseModel):
    """Represents a listed prompt commit with associated metadata."""

    id: UUID
    """The unique identifier for the prompt commit."""

    owner: str
    """The owner of the prompt commit."""

    repo: str
    """The repository name of the prompt commit."""

    manifest_id: Optional[UUID] = None
    """The optional identifier for the manifest associated with this commit."""

    repo_id: Optional[UUID] = None
    """The optional identifier for the repository."""

    parent_id: Optional[UUID] = None
    """The optional identifier for the parent commit."""

    commit_hash: Optional[str] = None
    """The optional hash of the commit."""

    created_at: Optional[datetime] = None
    """The optional timestamp when the commit was created."""

    updated_at: Optional[datetime] = None
    """The optional timestamp when the commit was last updated."""

    example_run_ids: Optional[list[UUID]] = Field(default_factory=list)
    """A list of example run identifiers associated with this commit."""

    num_downloads: Optional[int] = 0
    """The number of times this commit has been downloaded."""

    num_views: Optional[int] = 0
    """The number of times this commit has been viewed."""

    parent_commit_hash: Optional[str] = None
    """The optional hash of the parent commit."""


class Prompt(BaseModel):
    """Represents a Prompt with metadata."""

    repo_handle: str
    """The name of the prompt."""
    description: Optional[str] = None
    """The description of the prompt."""
    readme: Optional[str] = None
    """The README of the prompt."""
    id: str
    """The ID of the prompt."""
    tenant_id: str
    """The tenant ID of the prompt owner."""
    created_at: datetime
    """The creation time of the prompt."""
    updated_at: datetime
    """The last update time of the prompt."""
    is_public: bool
    """Whether the prompt is public."""
    is_archived: bool
    """Whether the prompt is archived."""
    tags: list[str]
    """The tags associated with the prompt."""
    original_repo_id: Optional[str] = None
    """The ID of the original prompt, if forked."""
    upstream_repo_id: Optional[str] = None
    """The ID of the upstream prompt, if forked."""
    owner: Optional[str]
    """The handle of the owner of the prompt."""
    full_name: str
    """The full name of the prompt. (owner + repo_handle)"""
    num_likes: int
    """The number of likes."""
    num_downloads: int
    """The number of downloads."""
    num_views: int
    """The number of views."""
    liked_by_auth_user: Optional[bool] = None
    """Whether the prompt is liked by the authenticated user."""
    last_commit_hash: Optional[str] = None
    """The hash of the last commit."""
    num_commits: int
    """The number of commits."""
    original_repo_full_name: Optional[str] = None
    """The full name of the original prompt, if forked."""
    upstream_repo_full_name: Optional[str] = None
    """The full name of the upstream prompt, if forked."""


class ListPromptsResponse(BaseModel):
    """A list of prompts with metadata."""

    repos: list[Prompt]
    """The list of prompts."""
    total: int
    """The total number of prompts."""


class PromptSortField(str, Enum):
    """Enum for sorting fields for prompts."""

    num_downloads = "num_downloads"
    """Number of downloads."""
    num_views = "num_views"
    """Number of views."""
    updated_at = "updated_at"
    """Last updated time."""
    num_likes = "num_likes"
    """Number of likes."""


class InputTokenDetails(TypedDict, total=False):
    """Breakdown of input token counts.

    Does *not* need to sum to full input token count. Does *not* need to have all keys.
    """

    audio: int
    """Audio input tokens."""
    cache_creation: int
    """Input tokens that were cached and there was a cache miss.

    Since there was a cache miss, the cache was created from these tokens.
    """
    cache_read: int
    """Input tokens that were cached and there was a cache hit.

    Since there was a cache hit, the tokens were read from the cache. More precisely,
    the model state given these tokens was read from the cache.
    """


class OutputTokenDetails(TypedDict, total=False):
    """Breakdown of output token counts.

    Does *not* need to sum to full output token count. Does *not* need to have all keys.
    """

    audio: int
    """Audio output tokens."""
    reasoning: int
    """Reasoning output tokens.

    Tokens generated by the model in a chain of thought process (i.e. by OpenAI's o1
    models) that are not returned as part of model output.
    """


class InputCostDetails(TypedDict, total=False):
    """Breakdown of input token costs.

    Does *not* need to sum to full input cost. Does *not* need to have all keys.
    """

    audio: float
    """Cost of audio input tokens."""
    cache_creation: float
    """Cost of input tokens that were cached and there was a cache miss.

    Since there was a cache miss, the cache was created from these tokens.
    """
    cache_read: float
    """Cost of input tokens that were cached and there was a cache hit.

    Since there was a cache hit, the tokens were read from the cache. More precisely,
    the model state given these tokens was read from the cache.
    """


class OutputCostDetails(TypedDict, total=False):
    """Breakdown of output token costs.

    Does *not* need to sum to full output cost. Does *not* need to have all keys.
    """

    audio: float
    """Cost of audio output tokens."""
    reasoning: float
    """Cost of reasoning output tokens.

    Tokens generated by the model in a chain of thought process (i.e. by OpenAI's o1
    models) that are not returned as part of model output.
    """


class UsageMetadata(TypedDict):
    """Usage metadata for a message, such as token counts.

    This is a standard representation of token usage that is consistent across models.
    """

    input_tokens: int
    """Count of input (or prompt) tokens. Sum of all input token types."""
    output_tokens: int
    """Count of output (or completion) tokens. Sum of all output token types."""
    total_tokens: int
    """Total token count. Sum of input_tokens + output_tokens."""
    input_token_details: NotRequired[InputTokenDetails]
    """Breakdown of input token counts.

    Does *not* need to sum to full input token count. Does *not* need to have all keys.
    """
    output_token_details: NotRequired[OutputTokenDetails]
    """Breakdown of output token counts.

    Does *not* need to sum to full output token count. Does *not* need to have all keys.
    """
    input_cost: NotRequired[float]
    """The cost of the input tokens."""
    output_cost: NotRequired[float]
    """The cost of the output tokens."""
    total_cost: NotRequired[float]
    """The total cost of the tokens."""
    input_cost_details: NotRequired[InputCostDetails]
    """The cost details of the input tokens."""
    output_cost_details: NotRequired[OutputCostDetails]
    """The cost details of the output tokens."""


class ExtractedUsageMetadata(TypedDict, total=False):
    """Usage metadata dictionary extracted from a run.

    Should be the same as UsageMetadata, but does not require all
    keys to be present.
    """

    input_tokens: int
    """The number of tokens used for the prompt."""
    output_tokens: int
    """The number of tokens generated as output."""
    total_tokens: int
    """The total number of tokens used."""
    input_token_details: InputTokenDetails
    """The details of the input tokens."""
    output_token_details: OutputTokenDetails
    """The details of the output tokens."""
    input_cost: float
    """The cost of the input tokens."""
    output_cost: float
    """The cost of the output tokens."""
    total_cost: float
    """The total cost of the tokens."""
    input_cost_details: InputCostDetails
    """The cost details of the input tokens."""
    output_cost_details: OutputCostDetails
    """The cost details of the output tokens."""


class UpsertExamplesResponse(TypedDict):
    """Response object returned from the upsert_examples_multipart method."""

    count: int
    """The number of examples that were upserted."""
    example_ids: list[str]
    """The ids of the examples that were upserted."""
