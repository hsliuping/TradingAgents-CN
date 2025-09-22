import functools
import warnings
from typing import Callable


class LangSmithBetaWarning(UserWarning):
    """This is a warning specific to the LangSmithBeta module."""


@functools.lru_cache(maxsize=100)
def _warn_once(message: str, stacklevel: int = 2) -> None:
    warnings.warn(message, LangSmithBetaWarning, stacklevel=stacklevel)


def warn_beta(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _warn_once(f"Function {func.__name__} is in beta.", stacklevel=3)
        return func(*args, **kwargs)

    return wrapper
