from typing import Dict, Literal, Optional, TypedDict

from dataclasses_json import DataClassJsonMixin
from pydantic import Field
from pydantic.dataclasses import dataclass

Provider = Literal[
    "credentials",
    "header",
    "github",
    "google",
    "azure-ad",
    "azure-ad-hybrid",
    "okta",
    "auth0",
    "descope",
]


class UserDict(TypedDict):
    id: str
    identifier: str
    display_name: Optional[str]
    metadata: Dict


# Used when logging-in a user
@dataclass
class User(DataClassJsonMixin):
    identifier: str
    display_name: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)


@dataclass
class PersistedUserFields:
    id: str
    createdAt: str


@dataclass
class PersistedUser(User, PersistedUserFields):
    pass
