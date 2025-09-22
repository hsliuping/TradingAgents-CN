import time
from functools import wraps
from importlib import import_module
from typing import TYPE_CHECKING, Callable, Optional, TypedDict, Union

from literalai.context import active_steps_var

if TYPE_CHECKING:
    from literalai.observability.generation import ChatGeneration, CompletionGeneration
    from literalai.observability.step import Step


class BeforeContext(TypedDict):
    original_func: Callable
    generation: Optional[Union["ChatGeneration", "CompletionGeneration"]]
    step: Optional["Step"]
    start: float


class AfterContext(TypedDict):
    original_func: Callable
    generation: Optional[Union["ChatGeneration", "CompletionGeneration"]]
    step: Optional["Step"]
    start: float


def remove_literalai_args(kargs):
    """Remove argument prefixed with "literalai_" from kwargs and return them in a separate dict"""
    largs = {}
    for key in list(kargs.keys()):
        if key.startswith("literalai_"):
            value = kargs.pop(key)
            largs[key] = value
    return largs


def restore_literalai_args(kargs, largs):
    """Reverse the effect of remove_literalai_args by merging the literal arguments into kwargs"""
    for key in list(largs.keys()):
        kargs[key] = largs[key]


def sync_wrapper(before_func=None, after_func=None):
    def decorator(original_func):
        @wraps(original_func)
        def wrapped(*args, **kwargs):
            context = {"original_func": original_func}
            # If a before_func is provided, call it with the shared context.
            if before_func:
                before_func(context, *args, **kwargs)
            # Remove literal arguments before calling the original function
            literalai_args = remove_literalai_args(kwargs)
            context["start"] = time.time()
            try:
                result = original_func(*args, **kwargs)
            except Exception as e:
                active_steps = active_steps_var.get()
                if active_steps and len(active_steps) > 0:
                    current_step = active_steps[-1]
                    current_step.error = str(e)
                    current_step.end()
                    current_step.processor.flush()
                raise e
            # If an after_func is provided, call it with the result and the shared context.
            if after_func:
                restore_literalai_args(kwargs, literalai_args)
                result = after_func(result, context, *args, **kwargs)

            return result

        return wrapped

    return decorator


def async_wrapper(before_func=None, after_func=None):
    def decorator(original_func):
        @wraps(original_func)
        async def wrapped(*args, **kwargs):
            context = {"original_func": original_func}
            # If a before_func is provided, call it with the shared context.
            if before_func:
                await before_func(context, *args, **kwargs)

            # Remove literal arguments before calling the original function
            literalai_args = remove_literalai_args(kwargs)
            context["start"] = time.time()
            try:
                result = await original_func(*args, **kwargs)
            except Exception as e:
                active_steps = active_steps_var.get()
                if active_steps and len(active_steps) > 0:
                    current_step = active_steps[-1]
                    current_step.error = str(e)
                    current_step.end()
                    current_step.processor.flush()
                raise e

            # If an after_func is provided, call it with the result and the shared context.
            if after_func:
                restore_literalai_args(kwargs, literalai_args)
                result = await after_func(result, context, *args, **kwargs)

            return result

        return wrapped

    return decorator


def wrap_all(
    to_wrap: list,
    before_wrapper,
    after_wrapper,
    async_before_wrapper,
    async_after_wrapper,
):
    for patch in to_wrap:
        module = import_module(str(patch["module"]))
        target_object = getattr(module, str(patch["object"]))
        original_method = getattr(target_object, str(patch["method"]))

        if patch["async"]:
            wrapped_method = async_wrapper(
                before_func=async_before_wrapper(metadata=patch["metadata"]),
                after_func=async_after_wrapper(metadata=patch["metadata"]),
            )(original_method)
        else:
            wrapped_method = sync_wrapper(
                before_func=before_wrapper(metadata=patch["metadata"]),
                after_func=after_wrapper(metadata=patch["metadata"]),
            )(original_method)

        setattr(target_object, str(patch["method"]), wrapped_method)
