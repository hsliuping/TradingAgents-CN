import os

from dotenv import load_dotenv

# ruff: noqa: E402
# Keep this here to ensure imports have environment available.
env_file = os.getenv("CHAINLIT_ENV_FILE", ".env")
env_found = load_dotenv(dotenv_path=os.path.join(os.getcwd(), env_file))

from chainlit.logger import logger

if env_found:
    logger.info(f"Loaded {env_file} file")

import asyncio
from typing import TYPE_CHECKING, Any, Dict

from literalai import ChatGeneration, CompletionGeneration, GenerationMessage
from pydantic.dataclasses import dataclass

import chainlit.input_widget as input_widget
from chainlit.action import Action
from chainlit.cache import cache
from chainlit.chat_context import chat_context
from chainlit.chat_settings import ChatSettings
from chainlit.context import context
from chainlit.element import (
    Audio,
    CustomElement,
    Dataframe,
    File,
    Image,
    Pdf,
    Plotly,
    Pyplot,
    Task,
    TaskList,
    TaskStatus,
    Text,
    Video,
)
from chainlit.message import (
    AskActionMessage,
    AskElementMessage,
    AskFileMessage,
    AskUserMessage,
    ErrorMessage,
    Message,
)
from chainlit.sidebar import ElementSidebar
from chainlit.step import Step, step
from chainlit.sync import make_async, run_sync
from chainlit.types import ChatProfile, InputAudioChunk, OutputAudioChunk, Starter
from chainlit.user import PersistedUser, User
from chainlit.user_session import user_session
from chainlit.utils import make_module_getattr
from chainlit.version import __version__

from .callbacks import (
    action_callback,
    author_rename,
    data_layer,
    header_auth_callback,
    oauth_callback,
    on_app_shutdown,
    on_app_startup,
    on_audio_chunk,
    on_audio_end,
    on_audio_start,
    on_chat_end,
    on_chat_resume,
    on_chat_start,
    on_feedback,
    on_logout,
    on_mcp_connect,
    on_mcp_disconnect,
    on_message,
    on_settings_update,
    on_stop,
    on_window_message,
    password_auth_callback,
    send_window_message,
    set_chat_profiles,
    set_starters,
)

if TYPE_CHECKING:
    from chainlit.langchain.callbacks import (
        AsyncLangchainCallbackHandler,
        LangchainCallbackHandler,
    )
    from chainlit.llama_index.callbacks import LlamaIndexCallbackHandler
    from chainlit.mistralai import instrument_mistralai
    from chainlit.openai import instrument_openai
    from chainlit.semantic_kernel import SemanticKernelFilter


def sleep(duration: int):
    """
    Sleep for a given duration.
    Args:
        duration (int): The duration in seconds.
    """
    return asyncio.sleep(duration)


@dataclass()
class CopilotFunction:
    name: str
    args: Dict[str, Any]

    def acall(self):
        return context.emitter.send_call_fn(self.name, self.args)


__getattr__ = make_module_getattr(
    {
        "LangchainCallbackHandler": "chainlit.langchain.callbacks",
        "AsyncLangchainCallbackHandler": "chainlit.langchain.callbacks",
        "LlamaIndexCallbackHandler": "chainlit.llama_index.callbacks",
        "instrument_openai": "chainlit.openai",
        "instrument_mistralai": "chainlit.mistralai",
        "SemanticKernelFilter": "chainlit.semantic_kernel",
    }
)

__all__ = [
    "Action",
    "AskActionMessage",
    "AskElementMessage",
    "AskFileMessage",
    "AskUserMessage",
    "AsyncLangchainCallbackHandler",
    "Audio",
    "ChatGeneration",
    "ChatProfile",
    "ChatSettings",
    "CompletionGeneration",
    "CopilotFunction",
    "CustomElement",
    "Dataframe",
    "ElementSidebar",
    "ErrorMessage",
    "File",
    "GenerationMessage",
    "Image",
    "InputAudioChunk",
    "LangchainCallbackHandler",
    "LlamaIndexCallbackHandler",
    "Message",
    "OutputAudioChunk",
    "Pdf",
    "PersistedUser",
    "Plotly",
    "Pyplot",
    "SemanticKernelFilter",
    "Starter",
    "Step",
    "Task",
    "TaskList",
    "TaskStatus",
    "Text",
    "User",
    "Video",
    "__version__",
    "action_callback",
    "author_rename",
    "cache",
    "chat_context",
    "context",
    "data_layer",
    "header_auth_callback",
    "input_widget",
    "instrument_mistralai",
    "instrument_openai",
    "make_async",
    "oauth_callback",
    "on_app_shutdown",
    "on_app_startup",
    "on_audio_chunk",
    "on_audio_end",
    "on_audio_start",
    "on_chat_end",
    "on_chat_resume",
    "on_chat_start",
    "on_feedback",
    "on_logout",
    "on_mcp_connect",
    "on_mcp_disconnect",
    "on_message",
    "on_settings_update",
    "on_stop",
    "on_window_message",
    "password_auth_callback",
    "run_sync",
    "send_window_message",
    "set_chat_profiles",
    "set_starters",
    "sleep",
    "step",
    "user_session",
]


def __dir__():
    return __all__
