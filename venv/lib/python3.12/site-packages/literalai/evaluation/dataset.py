from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, cast

from typing_extensions import TypedDict

from literalai.my_types import Utils

if TYPE_CHECKING:
    from literalai.api import LiteralAPI

from literalai.evaluation.dataset_experiment import DatasetExperiment
from literalai.evaluation.dataset_item import DatasetItem, DatasetItemDict

DatasetType = Literal["key_value", "generation"]


class DatasetDict(TypedDict, total=False):
    id: str
    createdAt: str
    metadata: Dict
    name: Optional[str]
    description: Optional[str]
    items: Optional[List[DatasetItemDict]]
    type: DatasetType


@dataclass(repr=False)
class Dataset(Utils):
    """
    A dataset of items, each item representing an ideal scenario to run experiments on.
    """

    api: "LiteralAPI"
    id: str
    created_at: str
    metadata: Dict
    name: Optional[str] = None
    description: Optional[str] = None
    items: List[DatasetItem] = field(default_factory=lambda: [])
    type: DatasetType = "key_value"

    def to_dict(self):
        return {
            "id": self.id,
            "createdAt": self.created_at,
            "metadata": self.metadata,
            "name": self.name,
            "description": self.description,
            "items": [item.to_dict() for item in self.items],
            "type": self.type,
        }

    @classmethod
    def from_dict(cls, api: "LiteralAPI", dataset: DatasetDict) -> "Dataset":
        items = dataset.get("items", [])
        if not isinstance(items, list):
            raise Exception("Dataset items should be an array")

        return cls(
            api=api,
            id=dataset.get("id", ""),
            created_at=dataset.get("createdAt", ""),
            metadata=dataset.get("metadata", {}),
            name=dataset.get("name"),
            description=dataset.get("description"),
            items=[DatasetItem.from_dict(item) for item in items],
            type=dataset.get("type", cast(DatasetType, "key_value")),
        )

    def update(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Update the dataset with the given name, description and metadata.
        """
        updated_dataset = self.api.update_dataset(
            self.id, name=name, description=description, metadata=metadata
        )
        self.name = updated_dataset.name
        self.description = updated_dataset.description
        self.metadata = updated_dataset.metadata

    def delete(self):
        """
        Deletes the dataset.
        """
        self.api.delete_dataset(self.id)

    def create_item(
        self,
        input: Dict,
        expected_output: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> DatasetItem:
        """
        Creates a new dataset item and adds it to this dataset.

        Args:
            input: The input data for the dataset item.
            expected_output: The output data for the dataset item (optional).
            metadata: Metadata for the dataset item (optional).

        Returns:
            `DatasetItem`:The created DatasetItem instance.
        """
        dataset_item = self.api.create_dataset_item(
            self.id, input, expected_output, metadata
        )
        if self.items is None:
            self.items = []
        self.items.append(dataset_item)
        return dataset_item

    def create_experiment(
        self,
        name: str,
        prompt_variant_id: Optional[str] = None,
        params: Optional[Dict] = None,
    ) -> DatasetExperiment:
        """
        Creates a new dataset experiment based on this dataset.

        Args:
            name: The name of the experiment.
            prompt_variant_id: The Prompt variant ID to experiment on.
            params: The params used on the experiment.

        Returns:
            `DatasetExperiment`: The created DatasetExperiment instance.
        """
        experiment = self.api.create_experiment(
            name=name,
            dataset_id=self.id,
            prompt_variant_id=prompt_variant_id,
            params=params,
        )
        return experiment

    def delete_item(self, item_id: str):
        """
        Deletes a dataset item from this dataset.

        Args:
            item_id: The ID of the dataset item to delete.
        """
        self.api.delete_dataset_item(item_id)
        if self.items is not None:
            self.items = [item for item in self.items if item.id != item_id]

    def add_step(self, step_id: str, metadata: Optional[Dict] = None) -> DatasetItem:
        """
        Create a new dataset item based on a step and add it to this dataset.

        Args:
            step_id: The id of the step to add to the dataset.
            metadata: Metadata for the dataset item (optional).

        Returns:
            `DatasetItem`: The created DatasetItem instance.
        """
        if self.type == "generation":
            raise ValueError("Cannot add a step to a generation dataset")

        dataset_item = self.api.add_step_to_dataset(self.id, step_id, metadata)
        if self.items is None:
            self.items = []
        self.items.append(dataset_item)
        return dataset_item

    def add_generation(
        self, generation_id: str, metadata: Optional[Dict] = None
    ) -> DatasetItem:
        """
        Create a new dataset item based on a generation and add it to this dataset.

        Args:
            generation_id: The id of the generation to add to the dataset.
            metadata: Metadata for the dataset item (optional).

        Returns:
            `DatasetItem`: The created DatasetItem instance.
        """
        dataset_item = self.api.add_generation_to_dataset(
            self.id, generation_id, metadata
        )
        if self.items is None:
            self.items = []
        self.items.append(dataset_item)
        return dataset_item
