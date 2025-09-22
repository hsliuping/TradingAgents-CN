import sys
from typing import Any, Coroutine, TypeVar

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

import asyncio
import threading

from asyncer import asyncify
from syncer import sync

from chainlit.context import context_var

make_async = asyncify

T_Retval = TypeVar("T_Retval")
T_ParamSpec = ParamSpec("T_ParamSpec")
T = TypeVar("T")


def run_sync(co: Coroutine[Any, Any, T_Retval]) -> T_Retval:
    """Run the coroutine synchronously."""

    # Copy the current context
    current_context = context_var.get()

    # Define a wrapper coroutine that sets the context before running the original coroutine
    async def context_preserving_coroutine():
        # Set the copied context to the coroutine
        context_var.set(current_context)
        return await co

    # Execute from the main thread in the main event loop
    if threading.current_thread() == threading.main_thread():
        return sync(context_preserving_coroutine())
    else:  # Execute from a thread in the main event loop
        result = asyncio.run_coroutine_threadsafe(
            context_preserving_coroutine(), loop=current_context.loop
        )
        return result.result()
