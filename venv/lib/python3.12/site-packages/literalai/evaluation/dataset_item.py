from dataclasses import dataclass
from typing import Dict, List, Optional, TypedDict

from literalai.my_types import Utils


class DatasetItemDict(TypedDict, total=False):
    id: str
    createdAt: str
    datasetId: str
    metadata: Dict
    input: Dict
    expectedOutput: Optional[Dict]
    intermediarySteps: Optional[List[Dict]]


@dataclass(repr=False)
class DatasetItem(Utils):
    """
    A `Dataset` item, containing `input`, `expectedOutput` and `metadata`.
    """

    id: str
    created_at: str
    dataset_id: str
    metadata: Dict
    input: Dict
    expected_output: Optional[Dict] = None
    intermediary_steps: Optional[List[Dict]] = None

    def to_dict(self):
        """
        Dumps the contents of the object into a dictionary.
        """
        return {
            "id": self.id,
            "createdAt": self.created_at,
            "datasetId": self.dataset_id,
            "metadata": self.metadata,
            "input": self.input,
            "expectedOutput": self.expected_output,
            "intermediarySteps": self.intermediary_steps,
        }

    @classmethod
    def from_dict(cls, dataset_item: DatasetItemDict) -> "DatasetItem":
        """
        Builds a `DatasetItem` object from a dictionary.
        """
        return cls(
            id=dataset_item.get("id", ""),
            created_at=dataset_item.get("createdAt", ""),
            dataset_id=dataset_item.get("datasetId", ""),
            metadata=dataset_item.get("metadata", {}),
            input=dataset_item.get("input", {}),
            expected_output=dataset_item.get("expectedOutput"),
            intermediary_steps=dataset_item.get("intermediarySteps"),
        )
