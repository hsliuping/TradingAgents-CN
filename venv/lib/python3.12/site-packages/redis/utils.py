import datetime
import logging
import textwrap
from contextlib import contextmanager
from functools import wraps
from typing import Any, Dict, List, Mapping, Optional, Union

from redis.exceptions import DataError
from redis.typing import AbsExpiryT, EncodableT, ExpiryT

try:
    import hiredis  # noqa

    # Only support Hiredis >= 3.0:
    hiredis_version = hiredis.__version__.split(".")
    HIREDIS_AVAILABLE = int(hiredis_version[0]) > 3 or (
        int(hiredis_version[0]) == 3 and int(hiredis_version[1]) >= 2
    )
    if not HIREDIS_AVAILABLE:
        raise ImportError("hiredis package should be >= 3.2.0")
except ImportError:
    HIREDIS_AVAILABLE = False

try:
    import ssl  # noqa

    SSL_AVAILABLE = True
except ImportError:
    SSL_AVAILABLE = False

try:
    import cryptography  # noqa

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

from importlib import metadata


def from_url(url, **kwargs):
    """
    Returns an active Redis client generated from the given database URL.

    Will attempt to extract the database id from the path url fragment, if
    none is provided.
    """
    from redis.client import Redis

    return Redis.from_url(url, **kwargs)


@contextmanager
def pipeline(redis_obj):
    p = redis_obj.pipeline()
    yield p
    p.execute()


def str_if_bytes(value: Union[str, bytes]) -> str:
    return (
        value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    )


def safe_str(value):
    return str(str_if_bytes(value))


def dict_merge(*dicts: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Merge all provided dicts into 1 dict.
    *dicts : `dict`
        dictionaries to merge
    """
    merged = {}

    for d in dicts:
        merged.update(d)

    return merged


def list_keys_to_dict(key_list, callback):
    return dict.fromkeys(key_list, callback)


def merge_result(command, res):
    """
    Merge all items in `res` into a list.

    This command is used when sending a command to multiple nodes
    and the result from each node should be merged into a single list.

    res : 'dict'
    """
    result = set()

    for v in res.values():
        for value in v:
            result.add(value)

    return list(result)


def warn_deprecated(name, reason="", version="", stacklevel=2):
    import warnings

    msg = f"Call to deprecated {name}."
    if reason:
        msg += f" ({reason})"
    if version:
        msg += f" -- Deprecated since version {version}."
    warnings.warn(msg, category=DeprecationWarning, stacklevel=stacklevel)


def deprecated_function(reason="", version="", name=None):
    """
    Decorator to mark a function as deprecated.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            warn_deprecated(name or func.__name__, reason, version, stacklevel=3)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def warn_deprecated_arg_usage(
    arg_name: Union[list, str],
    function_name: str,
    reason: str = "",
    version: str = "",
    stacklevel: int = 2,
):
    import warnings

    msg = (
        f"Call to '{function_name}' function with deprecated"
        f" usage of input argument/s '{arg_name}'."
    )
    if reason:
        msg += f" ({reason})"
    if version:
        msg += f" -- Deprecated since version {version}."
    warnings.warn(msg, category=DeprecationWarning, stacklevel=stacklevel)


def deprecated_args(
    args_to_warn: list = ["*"],
    allowed_args: list = [],
    reason: str = "",
    version: str = "",
):
    """
    Decorator to mark specified args of a function as deprecated.
    If '*' is in args_to_warn, all arguments will be marked as deprecated.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function argument names
            arg_names = func.__code__.co_varnames[: func.__code__.co_argcount]

            provided_args = dict(zip(arg_names, args))
            provided_args.update(kwargs)

            provided_args.pop("self", None)
            for allowed_arg in allowed_args:
                provided_args.pop(allowed_arg, None)

            for arg in args_to_warn:
                if arg == "*" and len(provided_args) > 0:
                    warn_deprecated_arg_usage(
                        list(provided_args.keys()),
                        func.__name__,
                        reason,
                        version,
                        stacklevel=3,
                    )
                elif arg in provided_args:
                    warn_deprecated_arg_usage(
                        arg, func.__name__, reason, version, stacklevel=3
                    )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def _set_info_logger():
    """
    Set up a logger that log info logs to stdout.
    (This is used by the default push response handler)
    """
    if "push_response" not in logging.root.manager.loggerDict.keys():
        logger = logging.getLogger("push_response")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)


def get_lib_version():
    try:
        libver = metadata.version("redis")
    except metadata.PackageNotFoundError:
        libver = "99.99.99"
    return libver


def format_error_message(host_error: str, exception: BaseException) -> str:
    if not exception.args:
        return f"Error connecting to {host_error}."
    elif len(exception.args) == 1:
        return f"Error {exception.args[0]} connecting to {host_error}."
    else:
        return (
            f"Error {exception.args[0]} connecting to {host_error}. "
            f"{exception.args[1]}."
        )


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two versions.

    :return: -1 if version1 > version2
             0 if both versions are equal
             1 if version1 < version2
    """

    num_versions1 = list(map(int, version1.split(".")))
    num_versions2 = list(map(int, version2.split(".")))

    if len(num_versions1) > len(num_versions2):
        diff = len(num_versions1) - len(num_versions2)
        for _ in range(diff):
            num_versions2.append(0)
    elif len(num_versions1) < len(num_versions2):
        diff = len(num_versions2) - len(num_versions1)
        for _ in range(diff):
            num_versions1.append(0)

    for i, ver in enumerate(num_versions1):
        if num_versions1[i] > num_versions2[i]:
            return -1
        elif num_versions1[i] < num_versions2[i]:
            return 1

    return 0


def ensure_string(key):
    if isinstance(key, bytes):
        return key.decode("utf-8")
    elif isinstance(key, str):
        return key
    else:
        raise TypeError("Key must be either a string or bytes")


def extract_expire_flags(
    ex: Optional[ExpiryT] = None,
    px: Optional[ExpiryT] = None,
    exat: Optional[AbsExpiryT] = None,
    pxat: Optional[AbsExpiryT] = None,
) -> List[EncodableT]:
    exp_options: list[EncodableT] = []
    if ex is not None:
        exp_options.append("EX")
        if isinstance(ex, datetime.timedelta):
            exp_options.append(int(ex.total_seconds()))
        elif isinstance(ex, int):
            exp_options.append(ex)
        elif isinstance(ex, str) and ex.isdigit():
            exp_options.append(int(ex))
        else:
            raise DataError("ex must be datetime.timedelta or int")
    elif px is not None:
        exp_options.append("PX")
        if isinstance(px, datetime.timedelta):
            exp_options.append(int(px.total_seconds() * 1000))
        elif isinstance(px, int):
            exp_options.append(px)
        else:
            raise DataError("px must be datetime.timedelta or int")
    elif exat is not None:
        if isinstance(exat, datetime.datetime):
            exat = int(exat.timestamp())
        exp_options.extend(["EXAT", exat])
    elif pxat is not None:
        if isinstance(pxat, datetime.datetime):
            pxat = int(pxat.timestamp() * 1000)
        exp_options.extend(["PXAT", pxat])

    return exp_options


def truncate_text(txt, max_length=100):
    return textwrap.shorten(
        text=txt, width=max_length, placeholder="...", break_long_words=True
    )
