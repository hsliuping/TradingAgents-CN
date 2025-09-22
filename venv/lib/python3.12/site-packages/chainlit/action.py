import uuid
from typing import Dict, Optional

from dataclasses_json import DataClassJsonMixin
from pydantic import Field
from pydantic.dataclasses import dataclass

from chainlit.context import context


@dataclass
class Action(DataClassJsonMixin):
    # Name of the action, this should be used in the action_callback
    name: str
    # The parameters to call this action with.
    payload: Dict
    # The label of the action. This is what the user will see.
    label: str = ""
    # The tooltip of the action button. This is what the user will see when they hover the action.
    tooltip: str = ""
    # The lucid icon name for this action.
    icon: Optional[str] = None
    # This should not be set manually, only used internally.
    forId: Optional[str] = None
    # The ID of the action
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    async def send(self, for_id: str):
        self.forId = for_id
        await context.emitter.emit("action", self.to_dict())

    async def remove(self):
        await context.emitter.emit("remove_action", self.to_dict())
