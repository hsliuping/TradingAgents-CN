from abc import abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import Field
from pydantic.dataclasses import dataclass

from chainlit.types import InputWidgetType


@dataclass
class InputWidget:
    id: str
    label: str
    initial: Any = None
    tooltip: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(
        self,
    ) -> None:
        if not self.id or not self.label:
            raise ValueError("Must provide key and label to load InputWidget")

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass


@dataclass
class Switch(InputWidget):
    """Useful to create a switch input."""

    type: InputWidgetType = "switch"
    initial: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "label": self.label,
            "initial": self.initial,
            "tooltip": self.tooltip,
            "description": self.description,
        }


@dataclass
class Slider(InputWidget):
    """Useful to create a slider input."""

    type: InputWidgetType = "slider"
    initial: float = 0
    min: float = 0
    max: float = 10
    step: float = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "label": self.label,
            "initial": self.initial,
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "tooltip": self.tooltip,
            "description": self.description,
        }


@dataclass
class Select(InputWidget):
    """Useful to create a select input."""

    type: InputWidgetType = "select"
    initial: Optional[str] = None
    initial_index: Optional[int] = None
    initial_value: Optional[str] = None
    values: List[str] = Field(default_factory=list)
    items: Dict[str, str] = Field(default_factory=dict)

    def __post_init__(
        self,
    ) -> None:
        super().__post_init__()

        if not self.values and not self.items:
            raise ValueError("Must provide values or items to create a Select")

        if self.values and self.items:
            raise ValueError(
                "You can only provide either values or items to create a Select"
            )

        if not self.values and self.initial_index is not None:
            raise ValueError(
                "Initial_index can only be used in combination with values to create a Select"
            )

        if self.items:
            self.initial = self.initial_value
        elif self.values:
            self.items = {value: value for value in self.values}
            self.initial = (
                self.values[self.initial_index]
                if self.initial_index is not None
                else self.initial_value
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "label": self.label,
            "initial": self.initial,
            "items": [
                {"label": id, "value": value} for id, value in self.items.items()
            ],
            "tooltip": self.tooltip,
            "description": self.description,
        }


@dataclass
class TextInput(InputWidget):
    """Useful to create a text input."""

    type: InputWidgetType = "textinput"
    initial: Optional[str] = None
    placeholder: Optional[str] = None
    multiline: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "label": self.label,
            "initial": self.initial,
            "placeholder": self.placeholder,
            "tooltip": self.tooltip,
            "description": self.description,
            "multiline": self.multiline,
        }


@dataclass
class NumberInput(InputWidget):
    """Useful to create a number input."""

    type: InputWidgetType = "numberinput"
    initial: Optional[float] = None
    placeholder: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "label": self.label,
            "initial": self.initial,
            "placeholder": self.placeholder,
            "tooltip": self.tooltip,
            "description": self.description,
        }


@dataclass
class Tags(InputWidget):
    """Useful to create an input for an array of strings."""

    type: InputWidgetType = "tags"
    initial: List[str] = Field(default_factory=list)
    values: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "label": self.label,
            "initial": self.initial,
            "tooltip": self.tooltip,
            "description": self.description,
        }
