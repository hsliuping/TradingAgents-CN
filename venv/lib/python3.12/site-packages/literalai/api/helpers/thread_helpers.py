from typing import Any, Dict, List, Optional

from literalai.api.helpers import gql
from literalai.my_types import PaginatedResponse
from literalai.observability.filter import threads_filters, threads_order_by
from literalai.observability.step import StepType
from literalai.observability.thread import Thread


def get_threads_helper(
    first: Optional[int] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filters: Optional[threads_filters] = None,
    order_by: Optional[threads_order_by] = None,
    step_types_to_keep: Optional[List[StepType]] = None,
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
    if step_types_to_keep:
        variables["stepTypesToKeep"] = step_types_to_keep

    def process_response(response):
        processed_response = response["data"]["threads"]
        processed_response["data"] = [
            edge["node"] for edge in processed_response["edges"]
        ]
        return PaginatedResponse[Thread].from_dict(processed_response, Thread)

    description = "get threads"

    return gql.GET_THREADS, description, variables, process_response


def list_threads_helper(
    first: Optional[int] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filters: Optional[threads_filters] = None,
    order_by: Optional[threads_order_by] = None,
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
        response_data = response["data"]["threads"]
        response_data["data"] = list(map(lambda x: x["node"], response_data["edges"]))
        return PaginatedResponse[Thread].from_dict(response_data, Thread)

    description = "get threads"

    return gql.LIST_THREADS, description, variables, process_response


def get_thread_helper(id: str):
    variables = {"id": id}

    def process_response(response):
        thread = response["data"]["threadDetail"]
        return Thread.from_dict(thread) if thread else None

    description = "get thread"

    return gql.GET_THREAD, description, variables, process_response


def create_thread_helper(
    name: Optional[str] = None,
    metadata: Optional[Dict] = None,
    participant_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    variables = {
        "name": name,
        "metadata": metadata,
        "participantId": participant_id,
        "tags": tags,
    }

    def process_response(response):
        return Thread.from_dict(response["data"]["createThread"])

    description = "create thread"

    return gql.CREATE_THREAD, description, variables, process_response


def upsert_thread_helper(
    id: str,
    name: Optional[str] = None,
    metadata: Optional[Dict] = None,
    participant_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    variables = {
        "id": id,
        "name": name,
        "metadata": metadata,
        "participantId": participant_id,
        "tags": tags,
    }

    # remove None values to prevent the API from removing existing values
    variables = {k: v for k, v in variables.items() if v is not None}

    def process_response(response):
        return Thread.from_dict(response["data"]["upsertThread"])

    description = "upsert thread"

    return gql.UPSERT_THREAD, description, variables, process_response


def update_thread_helper(
    id: str,
    name: Optional[str] = None,
    metadata: Optional[Dict] = None,
    participant_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    variables = {
        "id": id,
        "name": name,
        "metadata": metadata,
        "participantId": participant_id,
        "tags": tags,
    }

    # remove None values to prevent the API from removing existing values
    variables = {k: v for k, v in variables.items() if v is not None}

    def process_response(response):
        return Thread.from_dict(response["data"]["updateThread"])

    description = "update thread"

    return gql.UPDATE_THREAD, description, variables, process_response


def delete_thread_helper(id: str):
    variables = {"thread_id": id}

    def process_response(response):
        deleted = bool(response["data"]["deleteThread"])
        return deleted

    description = "delete thread"

    # Assuming DELETE_THREAD is a placeholder for the actual GraphQL mutation
    return gql.DELETE_THREAD, description, variables, process_response
