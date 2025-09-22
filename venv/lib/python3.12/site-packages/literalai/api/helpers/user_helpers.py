from typing import Any, Dict, Optional

from literalai.api.helpers import gql
from literalai.my_types import PaginatedResponse, User
from literalai.observability.filter import users_filters


def get_users_helper(
    first: Optional[int] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filters: Optional[users_filters] = None,
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

    def process_response(response):
        response = response["data"]["participants"]
        response["data"] = list(map(lambda x: x["node"], response["edges"]))
        return PaginatedResponse[User].from_dict(response, User)

    description = "get users"

    return gql.GET_PARTICIPANTS, description, variables, process_response


def create_user_helper(identifier: str, metadata: Optional[Dict] = None):
    variables = {"identifier": identifier, "metadata": metadata}

    def process_response(response) -> User:
        return User.from_dict(response["data"]["createParticipant"])

    description = "create user"

    return gql.CREATE_PARTICIPANT, description, variables, process_response


def update_user_helper(
    id: str, identifier: Optional[str] = None, metadata: Optional[Dict] = None
):
    variables = {"id": id, "identifier": identifier, "metadata": metadata}

    # remove None values to prevent the API from removing existing values
    variables = {k: v for k, v in variables.items() if v is not None}

    def process_response(response):
        return User.from_dict(response["data"]["updateParticipant"])

    description = "update user"

    return gql.UPDATE_PARTICIPANT, description, variables, process_response


def get_user_helper(id: Optional[str] = None, identifier: Optional[str] = None):
    if id is None and identifier is None:
        raise Exception("Either id or identifier must be provided")

    if id is not None and identifier is not None:
        raise Exception("Only one of id or identifier must be provided")

    variables = {"id": id, "identifier": identifier}

    def process_response(response):
        user = response["data"]["participant"]
        return User.from_dict(user) if user else None

    description = "get user"

    return gql.GET_PARTICIPANT, description, variables, process_response


def delete_user_helper(id: str):
    variables = {"id": id}

    def process_response(response):
        return response["data"]["deleteParticipant"]["id"]

    description = "delete user"

    return gql.DELETE_PARTICIPANT, description, variables, process_response
