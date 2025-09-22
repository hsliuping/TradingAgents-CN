import asyncio
import uuid
from typing import Any, Dict, List, Literal, Optional, Union, cast, get_args

from socketio.exceptions import TimeoutError

from chainlit.chat_context import chat_context
from chainlit.config import config
from chainlit.data import get_data_layer
from chainlit.element import Element, ElementDict, File
from chainlit.logger import logger
from chainlit.message import Message
from chainlit.session import BaseSession, WebsocketSession
from chainlit.step import StepDict
from chainlit.types import (
    AskActionResponse,
    AskElementResponse,
    AskSpec,
    CommandDict,
    FileDict,
    FileReference,
    MessagePayload,
    OutputAudioChunk,
    ThreadDict,
    ToastType,
)
from chainlit.user import PersistedUser
from chainlit.utils import utc_now


class BaseChainlitEmitter:
    """
    Chainlit Emitter Stub class. This class is used for testing purposes.
    It stubs the ChainlitEmitter class and does nothing on function calls.
    """

    session: BaseSession
    enabled: bool = True

    def __init__(self, session: BaseSession) -> None:
        """Initialize with the user session."""
        self.session = session

    async def emit(self, event: str, data: Any):
        """Stub method to get the 'emit' property from the session."""
        pass

    async def emit_call(self):
        """Stub method to get the 'emit_call' property from the session."""
        pass

    async def resume_thread(self, thread_dict: ThreadDict):
        """Stub method to resume a thread."""
        pass

    async def send_resume_thread_error(self, error: str):
        """Stub method to send a resume thread error."""
        pass

    async def send_element(self, element_dict: ElementDict):
        """Stub method to send an element to the UI."""
        pass

    async def update_audio_connection(self, state: Literal["on", "off"]):
        """Audio connection signaling."""
        pass

    async def send_audio_chunk(self, chunk: OutputAudioChunk):
        """Stub method to send an audio chunk to the UI."""
        pass

    async def send_audio_interrupt(self):
        """Stub method to interrupt the current audio response."""
        pass

    async def send_step(self, step_dict: StepDict):
        """Stub method to send a message to the UI."""
        pass

    async def update_step(self, step_dict: StepDict):
        """Stub method to update a message in the UI."""
        pass

    async def delete_step(self, step_dict: StepDict):
        """Stub method to delete a message in the UI."""
        pass

    def send_timeout(self, event: Literal["ask_timeout", "call_fn_timeout"]):
        """Stub method to send a timeout to the UI."""
        pass

    def clear(self, event: Literal["clear_ask", "clear_call_fn"]):
        pass

    async def init_thread(self, interaction: str):
        pass

    async def process_message(self, payload: MessagePayload) -> Message:
        """Stub method to process user message."""
        return Message(content="")

    async def send_ask_user(
        self, step_dict: StepDict, spec: AskSpec, raise_on_timeout=False
    ) -> Optional[
        Union["StepDict", "AskActionResponse", "AskElementResponse", List["FileDict"]]
    ]:
        """Stub method to send a prompt to the UI and wait for a response."""
        pass

    async def send_call_fn(
        self, name: str, args: Dict[str, Any], timeout=300, raise_on_timeout=False
    ) -> Optional[Dict[str, Any]]:
        """Stub method to send a call function event to the copilot and wait for a response."""
        pass

    async def update_token_count(self, count: int):
        """Stub method to update the token count for the UI."""
        pass

    async def task_start(self):
        """Stub method to send a task start signal to the UI."""
        pass

    async def task_end(self):
        """Stub method to send a task end signal to the UI."""
        pass

    async def stream_start(self, step_dict: StepDict):
        """Stub method to send a stream start signal to the UI."""
        pass

    async def send_token(self, id: str, token: str, is_sequence=False, is_input=False):
        """Stub method to send a message token to the UI."""
        pass

    async def set_chat_settings(self, settings: dict):
        """Stub method to set chat settings."""
        pass

    async def set_commands(self, commands: List[CommandDict]):
        """Stub method to send the available commands to the UI."""
        pass

    async def send_window_message(self, data: Any):
        """Stub method to send custom data to the host window."""
        pass

    def send_toast(self, message: str, type: Optional[ToastType] = "info"):
        """Stub method to send a toast message to the UI."""
        pass


class ChainlitEmitter(BaseChainlitEmitter):
    """
    Chainlit Emitter class. The Emitter is not directly exposed to the developer.
    Instead, the developer interacts with the Emitter through the methods and classes exposed in the __init__ file.
    """

    session: WebsocketSession

    def __init__(self, session: WebsocketSession) -> None:
        """Initialize with the user session."""
        self.session = session

    def _get_session_property(self, property_name: str, raise_error=True):
        """Helper method to get a property from the session."""
        if not hasattr(self, "session") or not hasattr(self.session, property_name):
            if raise_error:
                raise ValueError(f"Session does not have property '{property_name}'")
            else:
                return None
        return getattr(self.session, property_name)

    @property
    def emit(self):
        """Get the 'emit' property from the session."""

        return self._get_session_property("emit")

    @property
    def emit_call(self):
        """Get the 'emit_call' property from the session."""
        return self._get_session_property("emit_call")

    def resume_thread(self, thread_dict: ThreadDict):
        """Send a thread to the UI to resume it"""
        return self.emit("resume_thread", thread_dict)

    def send_resume_thread_error(self, error: str):
        """Send a thread resume error to the UI"""
        return self.emit("resume_thread_error", error)

    async def update_audio_connection(self, state: Literal["on", "off"]):
        """Audio connection signaling."""
        await self.emit("audio_connection", state)

    async def send_audio_chunk(self, chunk: OutputAudioChunk):
        """Send an audio chunk to the UI."""
        await self.emit("audio_chunk", chunk)

    async def send_audio_interrupt(self):
        """Method to interrupt the current audio response."""
        await self.emit("audio_interrupt", {})

    async def send_element(self, element_dict: ElementDict):
        """Stub method to send an element to the UI."""
        await self.emit("element", element_dict)

    def send_step(self, step_dict: StepDict):
        """Send a message to the UI."""
        return self.emit("new_message", step_dict)

    def update_step(self, step_dict: StepDict):
        """Update a message in the UI."""
        return self.emit("update_message", step_dict)

    def delete_step(self, step_dict: StepDict):
        """Delete a message in the UI."""
        return self.emit("delete_message", step_dict)

    def send_timeout(self, event: Literal["ask_timeout", "call_fn_timeout"]):
        return self.emit(event, {})

    def clear(self, event: Literal["clear_ask", "clear_call_fn"]):
        return self.emit(event, {})

    async def flush_thread_queues(self, interaction: str):
        if data_layer := get_data_layer():
            if isinstance(self.session.user, PersistedUser):
                user_id = self.session.user.id
            else:
                user_id = None
            try:
                should_tag_thread = (
                    self.session.chat_profile and config.features.auto_tag_thread
                )
                tags = [self.session.chat_profile] if should_tag_thread else None
                await data_layer.update_thread(
                    thread_id=self.session.thread_id,
                    name=interaction,
                    user_id=user_id,
                    tags=tags,
                )
            except Exception as e:
                logger.error(f"Error updating thread: {e}")
            asyncio.create_task(self.session.flush_method_queue())

    async def init_thread(self, interaction: str):
        await self.flush_thread_queues(interaction)
        await self.emit(
            "first_interaction",
            {
                "interaction": interaction,
                "thread_id": self.session.thread_id,
            },
        )

    async def process_message(self, payload: MessagePayload):
        step_dict = payload["message"]
        file_refs = payload.get("fileReferences")
        # UUID generated by the frontend should use v4
        assert uuid.UUID(step_dict["id"]).version == 4

        message = Message.from_dict(step_dict)
        # Overwrite the created_at timestamp with the current time
        message.created_at = utc_now()
        chat_context.add(message)

        asyncio.create_task(message._create())

        if not self.session.has_first_interaction:
            self.session.has_first_interaction = True
            asyncio.create_task(self.init_thread(message.content))

        if file_refs:
            files = [
                self.session.files[file["id"]]
                for file in file_refs
                if file["id"] in self.session.files
            ]

            elements = [
                Element.from_dict(
                    {
                        "id": file["id"],
                        "name": file["name"],
                        "path": str(file["path"]),
                        "chainlitKey": file["id"],
                        "display": "inline",
                        "type": Element.infer_type_from_mime(file["type"]),
                        "mime": file["type"],
                    }
                )
                for file in files
            ]

            message.elements = elements

            async def send_elements():
                for element in message.elements:
                    await element.send(for_id=message.id)

            asyncio.create_task(send_elements())

        return message

    async def send_ask_user(
        self, step_dict: StepDict, spec: AskSpec, raise_on_timeout=False
    ):
        """Send a prompt to the UI and wait for a response."""

        try:
            # Send the prompt to the UI
            user_res = await self.emit_call(
                "ask", {"msg": step_dict, "spec": spec.to_dict()}, spec.timeout
            )  # type: Optional[Union["StepDict", "AskActionResponse", "AskElementResponse", List["FileReference"]]]

            # End the task temporarily so that the User can answer the prompt
            await self.task_end()

            final_res: Optional[
                Union[StepDict, AskActionResponse, AskElementResponse, List[FileDict]]
            ] = None

            if user_res:
                interaction: Union[str, None] = None
                if spec.type == "text":
                    message_dict_res = cast(StepDict, user_res)
                    await self.process_message(
                        {"message": message_dict_res, "fileReferences": None}
                    )
                    interaction = message_dict_res["output"]
                    final_res = message_dict_res
                elif spec.type == "file":
                    file_refs = cast(List[FileReference], user_res)
                    files = [
                        self.session.files[file["id"]]
                        for file in file_refs
                        if file["id"] in self.session.files
                    ]
                    final_res = files
                    interaction = ",".join([file["name"] for file in files])
                    if get_data_layer():
                        coros = [
                            File(
                                id=file["id"],
                                name=file["name"],
                                path=str(file["path"]),
                                mime=file["type"],
                                chainlit_key=file["id"],
                                for_id=step_dict["id"],
                            )._create()
                            for file in files
                        ]
                        await asyncio.gather(*coros)
                elif spec.type == "action":
                    action_res = cast(AskActionResponse, user_res)
                    final_res = action_res
                    interaction = action_res["name"]
                elif spec.type == "element":
                    final_res = cast(AskElementResponse, user_res)
                    interaction = "custom_element"

                if not self.session.has_first_interaction and interaction:
                    self.session.has_first_interaction = True
                    await self.init_thread(interaction=interaction)

            await self.clear("clear_ask")
            return final_res
        except TimeoutError as e:
            await self.send_timeout("ask_timeout")

            if raise_on_timeout:
                raise e
        finally:
            await self.task_start()

    async def send_call_fn(
        self, name: str, args: Dict[str, Any], timeout=300, raise_on_timeout=False
    ) -> Optional[Dict[str, Any]]:
        """Stub method to send a call function event to the copilot and wait for a response."""
        try:
            call_fn_res = await self.emit_call(
                "call_fn", {"name": name, "args": args}, timeout
            )  # type: Dict

            await self.clear("clear_call_fn")
            return call_fn_res
        except TimeoutError as e:
            await self.send_timeout("call_fn_timeout")

            if raise_on_timeout:
                raise e
            return None

    def update_token_count(self, count: int):
        """Update the token count for the UI."""

        return self.emit("token_usage", count)

    def task_start(self):
        """
        Send a task start signal to the UI.
        """
        return self.emit("task_start", {})

    def task_end(self):
        """Send a task end signal to the UI."""
        return self.emit("task_end", {})

    def stream_start(self, step_dict: StepDict):
        """Send a stream start signal to the UI."""
        return self.emit(
            "stream_start",
            step_dict,
        )

    def send_token(self, id: str, token: str, is_sequence=False, is_input=False):
        """Send a message token to the UI."""
        return self.emit(
            "stream_token",
            {"id": id, "token": token, "isSequence": is_sequence, "isInput": is_input},
        )

    def set_chat_settings(self, settings: Dict[str, Any]):
        self.session.chat_settings = settings

    def set_commands(self, commands: List[CommandDict]):
        """Send the available commands to the UI."""
        return self.emit(
            "set_commands",
            commands,
        )

    def send_window_message(self, data: Any):
        """Send custom data to the host window."""
        return self.emit("window_message", data)

    def send_toast(self, message: str, type: Optional[ToastType] = "info"):
        """Send a toast message to the UI."""
        # check that the type is valid using ToastType
        if type not in get_args(ToastType):
            raise ValueError(f"Invalid toast type: {type}")
        return self.emit("toast", {"message": message, "type": type})
