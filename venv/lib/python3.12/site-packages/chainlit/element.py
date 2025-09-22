import json
import mimetypes
import uuid
from enum import Enum
from io import BytesIO
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    TypeVar,
    Union,
)

import filetype
from pydantic import Field
from pydantic.dataclasses import dataclass
from syncer import asyncio

from chainlit.context import context
from chainlit.data import get_data_layer
from chainlit.logger import logger

mime_types = {
    "text": "text/plain",
    "tasklist": "application/json",
    "plotly": "application/json",
}

ElementType = Literal[
    "image",
    "text",
    "pdf",
    "tasklist",
    "audio",
    "video",
    "file",
    "plotly",
    "dataframe",
    "custom",
]
ElementDisplay = Literal["inline", "side", "page"]
ElementSize = Literal["small", "medium", "large"]


class ElementDict(TypedDict, total=False):
    id: str
    threadId: Optional[str]
    type: ElementType
    chainlitKey: Optional[str]
    path: Optional[str]
    url: Optional[str]
    objectKey: Optional[str]
    name: str
    display: ElementDisplay
    size: Optional[ElementSize]
    language: Optional[str]
    page: Optional[int]
    props: Optional[Dict]
    autoPlay: Optional[bool]
    playerConfig: Optional[dict]
    forId: Optional[str]
    mime: Optional[str]


@dataclass
class Element:
    # Thread id
    thread_id: str = Field(default_factory=lambda: context.session.thread_id)
    # The type of the element. This will be used to determine how to display the element in the UI.
    type: ClassVar[ElementType]
    # Name of the element, this will be used to reference the element in the UI.
    name: str = ""
    # The ID of the element. This is set automatically when the element is sent to the UI.
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # The key of the element hosted on Chainlit.
    chainlit_key: Optional[str] = None
    # The URL of the element if already hosted somewhere else.
    url: Optional[str] = None
    # The S3 object key.
    object_key: Optional[str] = None
    # The local path of the element.
    path: Optional[str] = None
    # The byte content of the element.
    content: Optional[Union[bytes, str]] = None
    # Controls how the image element should be displayed in the UI. Choices are “side” (default), “inline”, or “page”.
    display: ElementDisplay = Field(default="inline")
    # Controls element size
    size: Optional[ElementSize] = None
    # The ID of the message this element is associated with.
    for_id: Optional[str] = None
    # The language, if relevant
    language: Optional[str] = None
    # Mime type, inferred based on content if not provided
    mime: Optional[str] = None

    def __post_init__(self) -> None:
        self.persisted = False
        self.updatable = False

        if not self.url and not self.path and not self.content:
            raise ValueError("Must provide url, path or content to instantiate element")

    def to_dict(self) -> ElementDict:
        _dict = ElementDict(
            {
                "id": self.id,
                "threadId": self.thread_id,
                "type": self.type,
                "url": self.url,
                "chainlitKey": self.chainlit_key,
                "name": self.name,
                "display": self.display,
                "objectKey": getattr(self, "object_key", None),
                "size": getattr(self, "size", None),
                "props": getattr(self, "props", None),
                "page": getattr(self, "page", None),
                "autoPlay": getattr(self, "auto_play", None),
                "playerConfig": getattr(self, "player_config", None),
                "language": getattr(self, "language", None),
                "forId": getattr(self, "for_id", None),
                "mime": getattr(self, "mime", None),
            }
        )
        return _dict

    @classmethod
    def from_dict(cls, e_dict: ElementDict):
        """
        Create an Element instance from a dictionary representation.

        Args:
            _dict (ElementDict): Dictionary containing element data

        Returns:
            Element: An instance of the appropriate Element subclass
        """
        element_id = e_dict.get("id", str(uuid.uuid4()))
        for_id = e_dict.get("forId")
        name = e_dict.get("name", "")
        type = e_dict.get("type", "file")
        path = str(e_dict.get("path")) if e_dict.get("path") else None
        url = str(e_dict.get("url")) if e_dict.get("url") else None
        content = str(e_dict.get("content")) if e_dict.get("content") else None
        object_key = e_dict.get("objectKey")
        chainlit_key = e_dict.get("chainlitKey")
        display = e_dict.get("display", "inline")
        mime_type = e_dict.get("mime", "")

        # Common parameters for all element types
        common_params = {
            "id": element_id,
            "for_id": for_id,
            "name": name,
            "content": content,
            "path": path,
            "url": url,
            "object_key": object_key,
            "chainlit_key": chainlit_key,
            "display": display,
            "mime": mime_type,
        }

        if type == "image":
            return Image(size="medium", **common_params)  # type: ignore[arg-type]

        elif type == "audio":
            return Audio(auto_play=e_dict.get("autoPlay", False), **common_params)  # type: ignore[arg-type]

        elif type == "video":
            return Video(
                player_config=e_dict.get("playerConfig"),
                **common_params,  # type: ignore[arg-type]
            )

        elif type == "plotly":
            return Plotly(size=e_dict.get("size", "medium"), **common_params)  # type: ignore[arg-type]

        elif type == "custom":
            return CustomElement(props=e_dict.get("props", {}), **common_params)  # type: ignore[arg-type]
        else:
            # Default to File for any other type
            return File(**common_params)  # type: ignore[arg-type]

    @classmethod
    def infer_type_from_mime(cls, mime_type: str):
        """Infer the element type from a mime type. Useful to know which element to instantiate from a file upload."""
        if "image" in mime_type:
            return "image"

        elif mime_type == "application/pdf":
            return "pdf"

        elif "audio" in mime_type:
            return "audio"

        elif "video" in mime_type:
            return "video"

        else:
            return "file"

    async def _create(self, persist=True) -> bool:
        if self.persisted and not self.updatable:
            return True

        if (data_layer := get_data_layer()) and persist:
            try:
                asyncio.create_task(data_layer.create_element(self))
            except Exception as e:
                logger.error(f"Failed to create element: {e!s}")
        if not self.url and (not self.chainlit_key or self.updatable):
            file_dict = await context.session.persist_file(
                name=self.name,
                path=self.path,
                content=self.content,
                mime=self.mime or "",
            )
            self.chainlit_key = file_dict["id"]

        self.persisted = True

        return True

    async def remove(self):
        data_layer = get_data_layer()
        if data_layer:
            await data_layer.delete_element(self.id, self.thread_id)
        await context.emitter.emit("remove_element", {"id": self.id})

    async def send(self, for_id: str, persist=True):
        self.for_id = for_id

        if not self.mime:
            if self.type in mime_types:
                self.mime = mime_types[self.type]
            elif self.path or isinstance(self.content, (bytes, bytearray)):
                file_type = filetype.guess(self.path or self.content)
                if file_type:
                    self.mime = file_type.mime
            elif self.url:
                self.mime = mimetypes.guess_type(self.url)[0]

        await self._create(persist=persist)

        if not self.url and not self.chainlit_key:
            raise ValueError("Must provide url or chainlit key to send element")

        await context.emitter.send_element(self.to_dict())


ElementBased = TypeVar("ElementBased", bound=Element)


@dataclass
class Image(Element):
    type: ClassVar[ElementType] = "image"

    size: ElementSize = "medium"


@dataclass
class Text(Element):
    """Useful to send a text (not a message) to the UI."""

    type: ClassVar[ElementType] = "text"
    language: Optional[str] = None


@dataclass
class Pdf(Element):
    """Useful to send a pdf to the UI."""

    mime: str = "application/pdf"
    page: Optional[int] = None
    type: ClassVar[ElementType] = "pdf"


@dataclass
class Pyplot(Element):
    """Useful to send a pyplot to the UI."""

    # We reuse the frontend image element to display the chart
    type: ClassVar[ElementType] = "image"

    size: ElementSize = "medium"
    # The type is set to Any because the figure is not serializable
    # and its actual type is checked in __post_init__.
    figure: Any = None

    def __post_init__(self) -> None:
        from matplotlib.figure import Figure

        if not isinstance(self.figure, Figure):
            raise TypeError("figure must be a matplotlib.figure.Figure")

        image = BytesIO()
        self.figure.savefig(
            image, dpi=200, bbox_inches="tight", backend="Agg", format="png"
        )
        self.content = image.getvalue()

        super().__post_init__()


class TaskStatus(Enum):
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"


@dataclass
class Task:
    title: str
    status: TaskStatus = TaskStatus.READY
    forId: Optional[str] = None

    def __init__(
        self,
        title: str,
        status: TaskStatus = TaskStatus.READY,
        forId: Optional[str] = None,
    ):
        self.title = title
        self.status = status
        self.forId = forId


@dataclass
class TaskList(Element):
    type: ClassVar[ElementType] = "tasklist"
    tasks: List[Task] = Field(default_factory=list, exclude=True)
    status: str = "Ready"
    name: str = "tasklist"
    content: str = "dummy content to pass validation"

    def __post_init__(self) -> None:
        super().__post_init__()
        self.updatable = True

    async def add_task(self, task: Task):
        self.tasks.append(task)

    async def update(self):
        await self.send()

    async def send(self):
        await self.preprocess_content()
        await super().send(for_id="")

    async def preprocess_content(self):
        # serialize enum
        tasks = [
            {"title": task.title, "status": task.status.value, "forId": task.forId}
            for task in self.tasks
        ]

        # store stringified json in content so that it's correctly stored in the database
        self.content = json.dumps(
            {
                "status": self.status,
                "tasks": tasks,
            },
            indent=4,
            ensure_ascii=False,
        )


@dataclass
class Audio(Element):
    type: ClassVar[ElementType] = "audio"
    auto_play: bool = False


@dataclass
class Video(Element):
    type: ClassVar[ElementType] = "video"

    size: ElementSize = "medium"
    # Override settings for each type of player in ReactPlayer
    # https://github.com/cookpete/react-player?tab=readme-ov-file#config-prop
    player_config: Optional[dict] = None


@dataclass
class File(Element):
    type: ClassVar[ElementType] = "file"


@dataclass
class Plotly(Element):
    """Useful to send a plotly to the UI."""

    type: ClassVar[ElementType] = "plotly"

    size: ElementSize = "medium"
    # The type is set to Any because the figure is not serializable
    # and its actual type is checked in __post_init__.
    figure: Any = None
    content: str = ""

    def __post_init__(self) -> None:
        from plotly import graph_objects as go, io as pio

        if not isinstance(self.figure, go.Figure):
            raise TypeError("figure must be a plotly.graph_objects.Figure")

        self.figure.layout.autosize = True
        self.figure.layout.width = None
        self.figure.layout.height = None
        self.content = pio.to_json(self.figure, validate=True)
        self.mime = "application/json"

        super().__post_init__()


@dataclass
class Dataframe(Element):
    """Useful to send a pandas DataFrame to the UI."""

    type: ClassVar[ElementType] = "dataframe"
    size: ElementSize = "large"
    data: Any = None  # The type is Any because it is checked in __post_init__.

    def __post_init__(self) -> None:
        """Ensures the data is a pandas DataFrame and converts it to JSON."""
        from pandas import DataFrame

        if not isinstance(self.data, DataFrame):
            raise TypeError("data must be a pandas.DataFrame")

        self.content = self.data.to_json(orient="split", date_format="iso")
        super().__post_init__()


@dataclass
class CustomElement(Element):
    """Useful to send a custom element to the UI."""

    type: ClassVar[ElementType] = "custom"
    mime: str = "application/json"
    props: Dict = Field(default_factory=dict)

    def __post_init__(self) -> None:
        self.content = json.dumps(self.props)
        super().__post_init__()
        self.updatable = True

    async def update(self):
        await super().send(self.for_id)
