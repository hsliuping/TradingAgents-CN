from typing import List

from pydantic import Field
from pydantic.dataclasses import dataclass

from chainlit.context import context
from chainlit.input_widget import InputWidget


@dataclass
class ChatSettings:
    """Useful to create chat settings that the user can change."""

    inputs: List[InputWidget] = Field(default_factory=list, exclude=True)

    def __init__(
        self,
        inputs: List[InputWidget],
    ) -> None:
        self.inputs = inputs

    def settings(self):
        return dict(
            [(input_widget.id, input_widget.initial) for input_widget in self.inputs]
        )

    async def send(self):
        settings = self.settings()
        context.emitter.set_chat_settings(settings)

        inputs_content = [input_widget.to_dict() for input_widget in self.inputs]
        await context.emitter.emit("chat_settings", inputs_content)

        return settings
