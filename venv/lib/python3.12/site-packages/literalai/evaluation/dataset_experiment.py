from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, TypedDict

from literalai.context import active_experiment_item_run_id_var
from literalai.my_types import Utils
from literalai.observability.step import ScoreDict

if TYPE_CHECKING:
    from literalai.api import LiteralAPI


class DatasetExperimentItemDict(TypedDict, total=False):
    id: str
    datasetExperimentId: str
    datasetItemId: Optional[str]
    scores: List[ScoreDict]
    input: Optional[Dict]
    output: Optional[Dict]
    experimentRunId: Optional[str]


@dataclass(repr=False)
class DatasetExperimentItem(Utils):
    """
    An item of a `DatasetExperiment`: it may be linked to a `DatasetItem`.
    """

    id: str
    dataset_experiment_id: str
    dataset_item_id: Optional[str]
    scores: List[ScoreDict]
    input: Optional[Dict]
    output: Optional[Dict]
    experiment_run_id: Optional[str]

    def to_dict(self):
        return {
            "id": self.id,
            "datasetExperimentId": self.dataset_experiment_id,
            "datasetItemId": self.dataset_item_id,
            "experimentRunId": self.experiment_run_id,
            "scores": self.scores,
            "input": self.input,
            "output": self.output,
        }

    @classmethod
    def from_dict(cls, item: DatasetExperimentItemDict) -> "DatasetExperimentItem":
        return cls(
            id=item.get("id", ""),
            experiment_run_id=item.get("experimentRunId"),
            dataset_experiment_id=item.get("datasetExperimentId", ""),
            dataset_item_id=item.get("datasetItemId"),
            scores=item.get("scores", []),
            input=item.get("input"),
            output=item.get("output"),
        )


class DatasetExperimentDict(TypedDict, total=False):
    id: str
    createdAt: str
    name: str
    datasetId: str
    params: Dict
    promptExperimentId: Optional[str]
    items: Optional[List[DatasetExperimentItemDict]]


@dataclass(repr=False)
class DatasetExperiment(Utils):
    """
    An experiment, linked or not to a `Dataset`.
    """

    api: "LiteralAPI"
    id: str
    created_at: str
    name: str
    dataset_id: Optional[str]
    params: Optional[Dict]
    prompt_variant_id: Optional[str] = None
    items: List[DatasetExperimentItem] = field(default_factory=lambda: [])

    def log(self, item_dict: DatasetExperimentItemDict) -> DatasetExperimentItem:
        """
        Logs an item to the dataset experiment.
        """
        experiment_run_id = active_experiment_item_run_id_var.get()
        dataset_experiment_item = DatasetExperimentItem.from_dict(
            {
                "experimentRunId": experiment_run_id,
                "datasetExperimentId": self.id,
                "datasetItemId": item_dict.get("datasetItemId"),
                "input": item_dict.get("input", {}),
                "output": item_dict.get("output", {}),
                "scores": item_dict.get("scores", []),
            }
        )

        item = self.api.create_experiment_item(dataset_experiment_item)
        self.items.append(item)
        return item

    def to_dict(self):
        return {
            "id": self.id,
            "createdAt": self.created_at,
            "name": self.name,
            "datasetId": self.dataset_id,
            "promptExperimentId": self.prompt_variant_id,
            "params": self.params,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(
        cls, api: "LiteralAPI", dataset_experiment: DatasetExperimentDict
    ) -> "DatasetExperiment":
        items = dataset_experiment.get("items", [])
        if not isinstance(items, list):
            raise Exception("Dataset items should be a list.")
        return cls(
            api=api,
            id=dataset_experiment.get("id", ""),
            created_at=dataset_experiment.get("createdAt", ""),
            name=dataset_experiment.get("name", ""),
            dataset_id=dataset_experiment.get("datasetId", ""),
            params=dataset_experiment.get("params"),
            prompt_variant_id=dataset_experiment.get("promptExperimentId"),
            items=[DatasetExperimentItem.from_dict(item) for item in items],
        )
