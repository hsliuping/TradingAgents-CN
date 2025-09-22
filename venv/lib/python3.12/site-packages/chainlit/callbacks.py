import inspect
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from fastapi import Request, Response
from mcp import ClientSession
from starlette.datastructures import Headers

from chainlit.action import Action
from chainlit.config import config
from chainlit.context import context
from chainlit.data.base import BaseDataLayer
from chainlit.mcp import McpConnection
from chainlit.message import Message
from chainlit.oauth_providers import get_configured_oauth_providers
from chainlit.step import Step, step
from chainlit.types import ChatProfile, Starter, ThreadDict
from chainlit.user import User
from chainlit.utils import wrap_user_function


def on_app_startup(func: Callable[[], Union[None, Awaitable[None]]]) -> Callable:
    """
    Hook to run code when the Chainlit application starts.
    Useful for initializing resources, loading models, setting up database connections, etc.
    The function can be synchronous or asynchronous.

    Args:
        func (Callable[[], Union[None, Awaitable[None]]]): The startup hook to execute. Takes no arguments.

    Example:
        @cl.on_app_startup
        async def startup():
            print("Application is starting!")
            # Initialize resources here

    Returns:
        Callable[[], Union[None, Awaitable[None]]]: The decorated startup hook.
    """
    config.code.on_app_startup = wrap_user_function(func, with_task=False)
    return func


def on_app_shutdown(func: Callable[[], Union[None, Awaitable[None]]]) -> Callable:
    """
    Hook to run code when the Chainlit application shuts down.
    Useful for cleaning up resources, closing connections, saving state, etc.
    The function can be synchronous or asynchronous.

    Args:
        func (Callable[[], Union[None, Awaitable[None]]]): The shutdown hook to execute. Takes no arguments.

    Example:
        @cl.on_app_shutdown
        async def shutdown():
            print("Application is shutting down!")
            # Clean up resources here

    Returns:
        Callable[[], Union[None, Awaitable[None]]]: The decorated shutdown hook.
    """
    config.code.on_app_shutdown = wrap_user_function(func, with_task=False)
    return func


def password_auth_callback(
    func: Callable[[str, str], Awaitable[Optional[User]]],
) -> Callable:
    """
    Framework agnostic decorator to authenticate the user.

    Args:
        func (Callable[[str, str], Awaitable[Optional[User]]]): The authentication callback to execute. Takes the email and password as parameters.

    Example:
        @cl.password_auth_callback
        async def password_auth_callback(username: str, password: str) -> Optional[User]:

    Returns:
        Callable[[str, str], Awaitable[Optional[User]]]: The decorated authentication callback.
    """

    config.code.password_auth_callback = wrap_user_function(func)
    return func


def header_auth_callback(
    func: Callable[[Headers], Awaitable[Optional[User]]],
) -> Callable:
    """
    Framework agnostic decorator to authenticate the user via a header

    Args:
        func (Callable[[Headers], Awaitable[Optional[User]]]): The authentication callback to execute.

    Example:
        @cl.header_auth_callback
        async def header_auth_callback(headers: Headers) -> Optional[User]:

    Returns:
        Callable[[Headers], Awaitable[Optional[User]]]: The decorated authentication callback.
    """

    config.code.header_auth_callback = wrap_user_function(func)
    return func


def oauth_callback(
    func: Callable[
        [str, str, Dict[str, str], User, Optional[str]], Awaitable[Optional[User]]
    ],
) -> Callable:
    """
    Framework agnostic decorator to authenticate the user via oauth

    Args:
        func (Callable[[str, str, Dict[str, str], User, Optional[str]], Awaitable[Optional[User]]]): The authentication callback to execute.

    Example:
        @cl.oauth_callback
        async def oauth_callback(provider_id: str, token: str, raw_user_data: Dict[str, str], default_app_user: User, id_token: Optional[str]) -> Optional[User]:

    Returns:
        Callable[[str, str, Dict[str, str], User, Optional[str]], Awaitable[Optional[User]]]: The decorated authentication callback.
    """

    if len(get_configured_oauth_providers()) == 0:
        raise ValueError(
            "You must set the environment variable for at least one oauth provider to use oauth authentication."
        )

    config.code.oauth_callback = wrap_user_function(func)
    return func


def on_logout(func: Callable[[Request, Response], Any]) -> Callable:
    """
    Function called when the user logs out.
    Takes the FastAPI request and response as parameters.
    """

    config.code.on_logout = wrap_user_function(func)
    return func


def on_message(func: Callable) -> Callable:
    """
    Framework agnostic decorator to react to messages coming from the UI.
    The decorated function is called every time a new message is received.

    Args:
        func (Callable[[Message], Any]): The function to be called when a new message is received. Takes a cl.Message.

    Returns:
        Callable[[str], Any]: The decorated on_message function.
    """

    async def with_parent_id(message: Message):
        async with Step(name="on_message", type="run", parent_id=message.id) as s:
            s.input = message.content
            if len(inspect.signature(func).parameters) > 0:
                await func(message)
            else:
                await func()

    config.code.on_message = wrap_user_function(with_parent_id)
    return func


async def send_window_message(data: Any):
    """
    Send custom data to the host window via a window.postMessage event.

    Args:
        data (Any): The data to send with the event.
    """
    await context.emitter.send_window_message(data)


def on_window_message(func: Callable[[str], Any]) -> Callable:
    """
    Hook to react to javascript postMessage events coming from the UI.

    Args:
        func (Callable[[str], Any]): The function to be called when a window message is received.
                                     Takes the message content as a string parameter.

    Returns:
        Callable[[str], Any]: The decorated on_window_message function.
    """
    config.code.on_window_message = wrap_user_function(func)
    return func


def on_chat_start(func: Callable) -> Callable:
    """
    Hook to react to the user websocket connection event.

    Args:
        func (Callable[], Any]): The connection hook to execute.

    Returns:
        Callable[], Any]: The decorated hook.
    """

    config.code.on_chat_start = wrap_user_function(
        step(func, name="on_chat_start", type="run"), with_task=True
    )
    return func


def on_chat_resume(func: Callable[[ThreadDict], Any]) -> Callable:
    """
    Hook to react to resume websocket connection event.

    Args:
        func (Callable[], Any]): The connection hook to execute.

    Returns:
        Callable[], Any]: The decorated hook.
    """

    config.code.on_chat_resume = wrap_user_function(func, with_task=True)
    return func


def set_chat_profiles(
    func: Callable[[Optional["User"]], Awaitable[List["ChatProfile"]]],
) -> Callable:
    """
    Programmatic declaration of the available chat profiles (can depend on the User from the session if authentication is setup).

    Args:
        func (Callable[[Optional["User"]], Awaitable[List["ChatProfile"]]]): The function declaring the chat profiles.

    Returns:
        Callable[[Optional["User"]], Awaitable[List["ChatProfile"]]]: The decorated function.
    """

    config.code.set_chat_profiles = wrap_user_function(func)
    return func


def set_starters(
    func: Callable[[Optional["User"]], Awaitable[List["Starter"]]],
) -> Callable:
    """
    Programmatic declaration of the available starter (can depend on the User from the session if authentication is setup).

    Args:
        func (Callable[[Optional["User"]], Awaitable[List["Starter"]]]): The function declaring the starters.

    Returns:
        Callable[[Optional["User"]], Awaitable[List["Starter"]]]: The decorated function.
    """

    config.code.set_starters = wrap_user_function(func)
    return func


def on_chat_end(func: Callable) -> Callable:
    """
    Hook to react to the user websocket disconnect event.

    Args:
        func (Callable[], Any]): The disconnect hook to execute.

    Returns:
        Callable[], Any]: The decorated hook.
    """

    config.code.on_chat_end = wrap_user_function(func, with_task=True)
    return func


def on_audio_start(func: Callable) -> Callable:
    """
    Hook to react to the user initiating audio.

    Returns:
        Callable[], Any]: The decorated hook.
    """

    config.code.on_audio_start = wrap_user_function(func, with_task=False)
    return func


def on_audio_chunk(func: Callable) -> Callable:
    """
    Hook to react to the audio chunks being sent.

    Args:
        chunk (InputAudioChunk): The audio chunk being sent.

    Returns:
        Callable[], Any]: The decorated hook.
    """

    config.code.on_audio_chunk = wrap_user_function(func, with_task=False)
    return func


def on_audio_end(func: Callable) -> Callable:
    """
    Hook to react to the audio stream ending. This is called after the last audio chunk is sent.

    Returns:
        Callable[], Any]: The decorated hook.
    """

    config.code.on_audio_end = wrap_user_function(
        step(func, name="on_audio_end", type="run"), with_task=True
    )
    return func


def author_rename(
    func: Callable[[str], Awaitable[str]],
) -> Callable[[str], Awaitable[str]]:
    """
    Useful to rename the author of message to display more friendly author names in the UI.
    Args:
        func (Callable[[str], Awaitable[str]]): The function to be called to rename an author. Takes the original author name as parameter.

    Returns:
        Callable[[Any, str], Awaitable[Any]]: The decorated function.
    """

    config.code.author_rename = wrap_user_function(func)
    return func


def on_mcp_connect(func: Callable[[McpConnection, ClientSession], None]) -> Callable:
    """
    Called everytime an MCP is connected
    """

    config.code.on_mcp_connect = wrap_user_function(func)
    return func


def on_mcp_disconnect(func: Callable[[str, ClientSession], None]) -> Callable:
    """
    Called everytime an MCP is disconnected
    """

    config.code.on_mcp_disconnect = wrap_user_function(func)
    return func


def on_stop(func: Callable) -> Callable:
    """
    Hook to react to the user stopping a thread.

    Args:
        func (Callable[[], Any]): The stop hook to execute.

    Returns:
        Callable[[], Any]: The decorated stop hook.
    """

    config.code.on_stop = wrap_user_function(func)
    return func


def action_callback(name: str) -> Callable:
    """
    Callback to call when an action is clicked in the UI.

    Args:
        func (Callable[[Action], Any]): The action callback to execute. First parameter is the action.
    """

    def decorator(func: Callable[[Action], Any]):
        config.code.action_callbacks[name] = wrap_user_function(func, with_task=False)
        return func

    return decorator


def on_settings_update(
    func: Callable[[Dict[str, Any]], Any],
) -> Callable[[Dict[str, Any]], Any]:
    """
    Hook to react to the user changing any settings.

    Args:
        func (Callable[], Any]): The hook to execute after settings were changed.

    Returns:
        Callable[], Any]: The decorated hook.
    """

    config.code.on_settings_update = wrap_user_function(func, with_task=True)
    return func


def data_layer(
    func: Callable[[], BaseDataLayer],
) -> Callable[[], BaseDataLayer]:
    """
    Hook to configure custom data layer.
    """

    # We don't use wrap_user_function here because:
    # 1. We don't need to support async here and;
    # 2. We don't want to change the API for get_data_layer() to be async, everywhere (at this point).
    config.code.data_layer = func
    return func


def on_feedback(func: Callable) -> Callable:
    """
    Hook to react to user feedback events from the UI.
    The decorated function is called every time feedback is received.

    Args:
        func (Callable[[Feedback], Any]): The function to be called when feedback is received. Takes a cl.Feedback object.

    Example:
        @cl.on_feedback
        async def on_feedback(feedback: Feedback):
            print(f"Received feedback: {feedback.value} for step {feedback.forId}")
            # Handle feedback here

    Returns:
        Callable[[Feedback], Any]: The decorated on_feedback function.
    """
    config.code.on_feedback = wrap_user_function(func)
    return func
