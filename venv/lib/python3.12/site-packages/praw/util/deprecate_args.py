"""Positional argument deprecation decorator."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable
from warnings import warn


def _deprecate_args(*old_args: str) -> Callable:
    def _generate_arg_string(used_args: tuple[str, ...]) -> str:
        used_args = list(map(repr, used_args))
        arg_count = len(used_args)
        arg_string = (
            " and ".join(used_args)
            if arg_count < 3
            else f"{', '.join(used_args[:-1])}, and {used_args[-1]}"
        )
        arg_string += f" as {'' if arg_count > 1 else 'a '}"
        arg_string += "keyword argument"
        return arg_string + ("s" if arg_count > 1 else "")

    def wrapper(func: Callable):
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any):
            signature = inspect.signature(func)
            positional_args = [
                name
                for name, parameter in signature.parameters.items()
                if parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            ]
            _old_args = tuple(filter(lambda arg: arg not in positional_args, old_args))
            if positional_args:
                # remove the acceptable positional arguments like self or id for helpers
                kwargs.update(zip(positional_args, args))
                args = tuple(args[len(positional_args) :])
            if args:
                arg_string = _generate_arg_string(_old_args[: len(args)])
                warn(
                    f"Positional arguments for {func.__qualname__!r} will no longer be"
                    f" supported in PRAW 8.\nCall this function with {arg_string}.",
                    DeprecationWarning,
                    stacklevel=2,
                )
            return func(**dict(zip(_old_args, args)), **kwargs)

        return wrapped

    return wrapper
