import json
import uuid
from abc import abstractmethod
from typing import Any, Dict, Generic, List, Literal, Optional, Protocol, TypeVar

from pydantic.dataclasses import Field, dataclass
from typing_extensions import TypedDict

Environment = Literal["dev", "staging", "prod", "experiment"]


class Utils:
    def __str__(self):
        return json.dumps(self.to_dict(), sort_keys=True, indent=4)

    def __repr__(self):
        return json.dumps(self.to_dict(), sort_keys=True, indent=4)

    @abstractmethod
    def to_dict(self):
        pass


@dataclass(repr=False)
class PageInfo(Utils):
    has_next_page: bool
    start_cursor: Optional[str]
    end_cursor: Optional[str]

    def to_dict(self):
        return {
            "hasNextPage": self.has_next_page,
            "startCursor": self.start_cursor,
            "endCursor": self.end_cursor,
        }

    @classmethod
    def from_dict(cls, page_info_dict: Dict) -> "PageInfo":
        has_next_page = page_info_dict.get("hasNextPage", False)
        start_cursor = page_info_dict.get("startCursor", None)
        end_cursor = page_info_dict.get("endCursor", None)
        return cls(
            has_next_page=has_next_page,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
        )


T = TypeVar("T", covariant=True)


class HasFromDict(Protocol[T]):
    @classmethod
    def from_dict(cls, obj_dict: Any) -> T:
        raise NotImplementedError()


@dataclass(repr=False)
class PaginatedResponse(Generic[T], Utils):
    page_info: PageInfo
    data: List[T]
    total_count: Optional[int] = None

    def to_dict(self):
        return {
            "pageInfo": self.page_info.to_dict(),
            "totalCount": self.total_count,
            "data": [
                (d.to_dict() if hasattr(d, "to_dict") and callable(d.to_dict) else d)
                for d in self.data
            ],
        }

    @classmethod
    def from_dict(
        cls, paginated_response_dict: Dict, the_class: HasFromDict[T]
    ) -> "PaginatedResponse[T]":
        page_info = PageInfo.from_dict(paginated_response_dict.get("pageInfo", {}))
        data = [the_class.from_dict(d) for d in paginated_response_dict.get("data", [])]
        total_count = paginated_response_dict.get("totalCount", None)
        return cls(page_info=page_info, data=data, total_count=total_count)


class TextContent(TypedDict, total=False):
    type: Literal["text"]
    text: str


class ImageUrlContent(TypedDict, total=False):
    type: Literal["image_url"]
    image_url: Dict


class UserDict(TypedDict, total=False):
    id: Optional[str]
    metadata: Optional[Dict]
    identifier: Optional[str]
    createdAt: Optional[str]


@dataclass(repr=False)
class User(Utils):
    id: Optional[str] = None
    created_at: Optional[str] = None
    identifier: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict = Field(default_factory=lambda: {})

    def to_dict(self) -> UserDict:
        return {
            "id": self.id,
            "identifier": self.identifier,
            "metadata": self.metadata,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, user_dict: Dict) -> "User":
        id_ = user_dict.get("id", "")
        identifier = user_dict.get("identifier", "")
        metadata = user_dict.get("metadata", {})
        created_at = user_dict.get("createdAt", "")

        user = cls(
            id=id_, identifier=identifier, metadata=metadata, created_at=created_at
        )

        return user
