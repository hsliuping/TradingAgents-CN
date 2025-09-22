from typing import TYPE_CHECKING, Dict, Optional

from literalai.api.helpers import gql
from literalai.evaluation.dataset import Dataset, DatasetType
from literalai.evaluation.dataset_experiment import (
    DatasetExperiment,
    DatasetExperimentItem,
)
from literalai.evaluation.dataset_item import DatasetItem

if TYPE_CHECKING:
    from literalai.api import LiteralAPI


def create_dataset_helper(
    api: "LiteralAPI",
    name: str,
    description: Optional[str] = None,
    metadata: Optional[Dict] = None,
    type: DatasetType = "key_value",
):
    variables = {
        "name": name,
        "description": description,
        "metadata": metadata,
        "type": type,
    }

    def process_response(response):
        return Dataset.from_dict(api, response["data"]["createDataset"])

    description = "create dataset"

    return gql.CREATE_DATASET, description, variables, process_response


def get_dataset_helper(
    api: "LiteralAPI", id: Optional[str] = None, name: Optional[str] = None
):
    if not id and not name:
        raise ValueError("id or name must be provided")

    body = {}

    if id:
        body["id"] = id
    if name:
        body["name"] = name

    def process_response(response) -> Optional[Dataset]:
        dataset_dict = response.get("data")
        if dataset_dict is None:
            return None
        return Dataset.from_dict(api, dataset_dict)

    description = "get dataset"

    # Assuming there's a placeholder or a constant for the subpath
    subpath = "/export/dataset"

    return subpath, description, body, process_response


def update_dataset_helper(
    api: "LiteralAPI",
    id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict] = None,
):
    variables: Dict = {"id": id}
    if name is not None:
        variables["name"] = name
    if description is not None:
        variables["description"] = description
    if metadata is not None:
        variables["metadata"] = metadata

    def process_response(response):
        return Dataset.from_dict(api, response["data"]["updateDataset"])

    description = "update dataset"

    return gql.UPDATE_DATASET, description, variables, process_response


def delete_dataset_helper(api: "LiteralAPI", id: str):
    variables = {"id": id}

    def process_response(response):
        return Dataset.from_dict(api, response["data"]["deleteDataset"])

    description = "delete dataset"

    return gql.DELETE_DATASET, description, variables, process_response


def create_experiment_helper(
    api: "LiteralAPI",
    name: str,
    dataset_id: Optional[str] = None,
    prompt_variant_id: Optional[str] = None,
    params: Optional[Dict] = None,
):
    variables = {
        "datasetId": dataset_id,
        "name": name,
        "promptExperimentId": prompt_variant_id,
        "params": params,
    }

    def process_response(response):
        return DatasetExperiment.from_dict(
            api, response["data"]["createDatasetExperiment"]
        )

    description = "create dataset experiment"

    return gql.CREATE_EXPERIMENT, description, variables, process_response


def create_experiment_item_helper(
    dataset_experiment_id: str,
    experiment_run_id: Optional[str] = None,
    dataset_item_id: Optional[str] = None,
    input: Optional[Dict] = None,
    output: Optional[Dict] = None,
):
    variables = {
        "experimentRunId": experiment_run_id,
        "datasetExperimentId": dataset_experiment_id,
        "datasetItemId": dataset_item_id,
        "input": input,
        "output": output,
    }

    def process_response(response):
        return DatasetExperimentItem.from_dict(
            response["data"]["createDatasetExperimentItem"]
        )

    description = "create dataset experiment item"

    return gql.CREATE_EXPERIMENT_ITEM, description, variables, process_response


def create_dataset_item_helper(
    dataset_id: str,
    input: Dict,
    expected_output: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
):
    variables = {
        "datasetId": dataset_id,
        "input": input,
        "expectedOutput": expected_output,
        "metadata": metadata,
    }

    def process_response(response):
        return DatasetItem.from_dict(response["data"]["createDatasetItem"])

    description = "create dataset item"

    return gql.CREATE_DATASET_ITEM, description, variables, process_response


def get_dataset_item_helper(id: str):
    variables = {"id": id}

    def process_response(response):
        return DatasetItem.from_dict(response["data"]["datasetItem"])

    description = "get dataset item"

    return gql.GET_DATASET_ITEM, description, variables, process_response


def delete_dataset_item_helper(id: str):
    variables = {"id": id}

    def process_response(response):
        return DatasetItem.from_dict(response["data"]["deleteDatasetItem"])

    description = "delete dataset item"

    return gql.DELETE_DATASET_ITEM, description, variables, process_response


def add_step_to_dataset_helper(
    dataset_id: str, step_id: str, metadata: Optional[Dict] = None
):
    variables = {
        "datasetId": dataset_id,
        "stepId": step_id,
        "metadata": metadata,
    }

    def process_response(response):
        return DatasetItem.from_dict(response["data"]["addStepToDataset"])

    description = "add step to dataset"

    return gql.ADD_STEP_TO_DATASET, description, variables, process_response


def add_generation_to_dataset_helper(
    dataset_id: str, generation_id: str, metadata: Optional[Dict] = None
):
    variables = {
        "datasetId": dataset_id,
        "generationId": generation_id,
        "metadata": metadata,
    }

    def process_response(response):
        return DatasetItem.from_dict(response["data"]["addGenerationToDataset"])

    description = "add generation to dataset"

    return gql.ADD_GENERATION_TO_DATASET, description, variables, process_response
