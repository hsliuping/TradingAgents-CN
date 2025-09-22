from typing import Any, Generic, List, Literal, Optional, TypeVar, Union

from typing_extensions import TypedDict

Field = TypeVar("Field")
Operators = TypeVar("Operators")
Value = TypeVar("Value")

BOOLEAN_OPERATORS = Literal["is", "nis"]
STRING_OPERATORS = Literal["eq", "neq", "ilike", "nilike"]
NUMBER_OPERATORS = Literal["eq", "neq", "gt", "gte", "lt", "lte"]
STRING_LIST_OPERATORS = Literal["in", "nin"]
DATETIME_OPERATORS = Literal["gte", "lte", "gt", "lt"]

OPERATORS = Union[
    BOOLEAN_OPERATORS,
    STRING_OPERATORS,
    NUMBER_OPERATORS,
    STRING_LIST_OPERATORS,
    DATETIME_OPERATORS,
]


class Filter(Generic[Field], TypedDict, total=False):
    field: Field
    operator: OPERATORS
    value: Any
    path: Optional[str]


class OrderBy(Generic[Field], TypedDict):
    column: Field
    direction: Literal["ASC", "DESC"]


threads_filterable_fields = Literal[
    "id",
    "createdAt",
    "name",
    "stepType",
    "stepName",
    "stepOutput",
    "metadata",
    "tokenCount",
    "tags",
    "participantId",
    "participantIdentifiers",
    "scoreValue",
    "duration",
]
threads_orderable_fields = Literal["createdAt", "tokenCount"]
threads_filters = List[Filter[threads_filterable_fields]]
threads_order_by = OrderBy[threads_orderable_fields]

steps_filterable_fields = Literal[
    "id",
    "name",
    "input",
    "output",
    "participantIdentifier",
    "startTime",
    "endTime",
    "metadata",
    "parentId",
    "threadId",
    "error",
    "tags",
]
steps_orderable_fields = Literal["createdAt"]
steps_filters = List[Filter[steps_filterable_fields]]
steps_order_by = OrderBy[steps_orderable_fields]

users_filterable_fields = Literal[
    "id",
    "createdAt",
    "identifier",
    "lastEngaged",
    "threadCount",
    "tokenCount",
    "metadata",
]
users_filters = List[Filter[users_filterable_fields]]

scores_filterable_fields = Literal[
    "id",
    "createdAt",
    "participant",
    "name",
    "tags",
    "value",
    "type",
    "comment",
]
scores_orderable_fields = Literal["createdAt"]
scores_filters = List[Filter[scores_filterable_fields]]
scores_order_by = OrderBy[scores_orderable_fields]

generation_filterable_fields = Literal[
    "id",
    "createdAt",
    "model",
    "duration",
    "promptLineage",
    "promptVersion",
    "tags",
    "score",
    "participant",
    "tokenCount",
    "error",
]
generation_orderable_fields = Literal[
    "createdAt",
    "tokenCount",
    "model",
    "provider",
    "participant",
    "duration",
]
generations_filters = List[Filter[generation_filterable_fields]]
generations_order_by = OrderBy[generation_orderable_fields]
