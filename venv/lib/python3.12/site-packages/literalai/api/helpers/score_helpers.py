import math
from typing import Any, Dict, List, Optional, TypedDict

from literalai.api.helpers import gql
from literalai.my_types import PaginatedResponse
from literalai.observability.filter import scores_filters, scores_order_by
from literalai.observability.step import Score, ScoreDict, ScoreType


def get_scores_helper(
    first: Optional[int] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filters: Optional[scores_filters] = None,
    order_by: Optional[scores_order_by] = None,
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
        response_data = response["data"]["scores"]
        response_data["data"] = list(map(lambda x: x["node"], response_data["edges"]))
        return PaginatedResponse[Score].from_dict(response_data, Score)  # type: ignore

    description = "get scores"

    return gql.GET_SCORES, description, variables, process_response


def create_score_helper(
    name: str,
    value: float,
    type: ScoreType,
    step_id: Optional[str] = None,
    dataset_experiment_item_id: Optional[str] = None,
    comment: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    variables = {
        "name": name,
        "type": type,
        "value": value,
        "stepId": step_id,
        "datasetExperimentItemId": dataset_experiment_item_id,
        "comment": comment,
        "tags": tags,
    }

    def process_response(response):
        return Score.from_dict(response["data"]["createScore"])

    description = "create score"

    return gql.CREATE_SCORE, description, variables, process_response


def create_scores_fields_builder(scores: List[ScoreDict]):
    generated = ""
    for id in range(len(scores)):
        generated += f"""$name_{id}: String!
        $type_{id}: ScoreType!
        $value_{id}: Float!
        $label_{id}: String
        $stepId_{id}: String
        $datasetExperimentItemId_{id}: String
        $scorer_{id}: String
        $comment_{id}: String
        $tags_{id}: [String!]
        """
    return generated


def create_scores_args_builder(scores: List[ScoreDict]):
    generated = ""
    for id in range(len(scores)):
        generated += f"""
            score_{id}: createScore(
                name: $name_{id}
                type: $type_{id}
                value: $value_{id}
                label: $label_{id}
                stepId: $stepId_{id}
                datasetExperimentItemId: $datasetExperimentItemId_{id}
                scorer: $scorer_{id}
                comment: $comment_{id}
                tags: $tags_{id}
            ) {{
                id
                name
                type
                value
                label
                comment
                scorer
            }}
        """
    return generated


def create_scores_query_builder(scores: List[ScoreDict]):
    return f"""
        mutation CreateScores({create_scores_fields_builder(scores)}) {{
            {create_scores_args_builder(scores)}
        }}
    """


class ScoreUpdate(TypedDict, total=False):
    comment: Optional[str]
    value: float


def update_score_helper(
    id: str,
    update_params: ScoreUpdate,
):
    variables = {"id": id, **update_params}

    def process_response(response):
        return Score.from_dict(response["data"]["updateScore"])

    description = "update score"

    return gql.UPDATE_SCORE, description, variables, process_response


def delete_score_helper(id: str):
    variables = {"id": id}

    def process_response(response):
        return response["data"]["deleteScore"]

    description = "delete score"

    return gql.DELETE_SCORE, description, variables, process_response


def check_scores_finite(scores: List[ScoreDict]):
    for score in scores:
        if not math.isfinite(score["value"]):
            raise ValueError(
                f"Value {score['value']} for score {score['name']} is not finite"
            )
    return True
