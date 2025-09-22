from typing import Any, Dict, Optional, Union

from literalai.api.helpers import gql
from literalai.my_types import PaginatedResponse
from literalai.observability.filter import generations_filters, generations_order_by
from literalai.observability.generation import (
    BaseGeneration,
    ChatGeneration,
    CompletionGeneration,
)


def get_generations_helper(
    first: Optional[int] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filters: Optional[generations_filters] = None,
    order_by: Optional[generations_order_by] = None,
):
    variables: Dict[str, Any] = {}

    if first:
        variables["first"] = first
    if after:
        variables["after"] = after
    if before:
        variables["before"] = before
    if filters:
        variables["filters"] = filters
    if order_by:
        variables["orderBy"] = order_by

    def process_response(response):
        processed_response = response["data"]["generations"]
        processed_response["data"] = list(
            map(lambda x: x["node"], processed_response["edges"])
        )
        return PaginatedResponse[BaseGeneration].from_dict(
            processed_response, BaseGeneration
        )

    description = "get generations"

    return gql.GET_GENERATIONS, description, variables, process_response


def create_generation_helper(generation: Union[ChatGeneration, CompletionGeneration]):
    variables = {"generation": generation.to_dict()}

    def process_response(response):
        return BaseGeneration.from_dict(response["data"]["createGeneration"])

    description = "create generation"

    return gql.CREATE_GENERATION, description, variables, process_response
