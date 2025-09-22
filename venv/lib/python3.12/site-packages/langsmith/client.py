"""Client for interacting with the LangSmith API.

Use the client to customize API keys / workspace connections, SSL certs,
etc. for tracing.

Also used to create, read, update, and delete LangSmith resources
such as runs (~trace spans), datasets, examples (~records),
feedback (~metrics), projects (tracer sessions/groups), etc.

For detailed API documentation, visit: https://docs.smith.langchain.com/.
"""

from __future__ import annotations

import atexit
import collections
import concurrent.futures as cf
import contextlib
import datetime
import functools
import importlib
import importlib.metadata
import io
import itertools
import json
import logging
import os
import random
import threading
import time
import traceback
import typing
import uuid
import warnings
import weakref
from collections.abc import AsyncIterable, Iterable, Iterator, Mapping, Sequence
from inspect import signature
from pathlib import Path
from queue import PriorityQueue
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Optional,
    Union,
    cast,
)
from urllib import parse as urllib_parse

import requests
from requests import adapters as requests_adapters
from requests_toolbelt import (  # type: ignore[import-untyped]
    multipart as rqtb_multipart,
)
from typing_extensions import TypeGuard, overload
from urllib3.poolmanager import PoolKey  # type: ignore[attr-defined, import-untyped]
from urllib3.util import Retry  # type: ignore[import-untyped]

import langsmith
from langsmith import env as ls_env
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith._internal import _orjson
from langsmith._internal._background_thread import (
    TracingQueueItem,
)
from langsmith._internal._background_thread import (
    tracing_control_thread_func as _tracing_control_thread_func,
)
from langsmith._internal._beta_decorator import warn_beta
from langsmith._internal._compressed_traces import CompressedTraces
from langsmith._internal._constants import (
    _AUTO_SCALE_UP_NTHREADS_LIMIT,
    _BLOCKSIZE_BYTES,
    _BOUNDARY,
    _SIZE_LIMIT_BYTES,
)
from langsmith._internal._multipart import (
    MultipartPart,
    MultipartPartsAndContext,
    join_multipart_parts_and_context,
)
from langsmith._internal._operations import (
    SerializedFeedbackOperation,
    SerializedRunOperation,
    combine_serialized_queue_operations,
    compress_multipart_parts_and_context,
    serialize_feedback_dict,
    serialize_run_dict,
    serialized_feedback_operation_to_multipart_parts_and_context,
    serialized_run_operation_to_multipart_parts_and_context,
)
from langsmith._internal._serde import dumps_json as _dumps_json
from langsmith.schemas import AttachmentInfo

HAS_OTEL = False
try:
    if ls_utils.is_truish(ls_utils.get_env_var("OTEL_ENABLED")):
        from opentelemetry import trace as otel_trace  # type: ignore[import]
        from opentelemetry.trace import set_span_in_context  # type: ignore[import]

        from langsmith._internal.otel._otel_client import (
            get_otlp_tracer_provider,
        )
        from langsmith._internal.otel._otel_exporter import OTELExporter

        HAS_OTEL = True
except ImportError:
    raise ImportError(
        "To use OTEL tracing, you must install it with `pip install langsmith[otel]`"
    )

try:
    from zoneinfo import ZoneInfo  # type: ignore[import-not-found]
except ImportError:

    class ZoneInfo:  # type: ignore[no-redef]
        """Introduced in python 3.9."""


try:
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
except ImportError:

    class TracerProvider:  # type: ignore[no-redef]
        """Used for optional OTEL tracing."""


if TYPE_CHECKING:
    import pandas as pd  # type: ignore
    from langchain_core.runnables import Runnable

    from langsmith import schemas
    from langsmith.evaluation import evaluator as ls_evaluator
    from langsmith.evaluation._arunner import (
        AEVALUATOR_T,
        ATARGET_T,
        AsyncExperimentResults,
    )
    from langsmith.evaluation._runner import (
        COMPARATIVE_EVALUATOR_T,
        DATA_T,
        EVALUATOR_T,
        EXPERIMENT_T,
        SUMMARY_EVALUATOR_T,
        TARGET_T,
        ComparativeExperimentResults,
        ExperimentResults,
    )


logger = logging.getLogger(__name__)
_urllib3_logger = logging.getLogger("urllib3.connectionpool")

X_API_KEY = "x-api-key"
EMPTY_SEQ: tuple[dict, ...] = ()
URLLIB3_SUPPORTS_BLOCKSIZE = "key_blocksize" in signature(PoolKey).parameters


def _parse_token_or_url(
    url_or_token: Union[str, uuid.UUID],
    api_url: str,
    num_parts: int = 2,
    kind: str = "dataset",
) -> tuple[str, str]:
    """Parse a public dataset URL or share token."""
    try:
        if isinstance(url_or_token, uuid.UUID) or uuid.UUID(url_or_token):
            return api_url, str(url_or_token)
    except ValueError:
        pass

    # Then it's a URL
    parsed_url = urllib_parse.urlparse(str(url_or_token))
    # Extract the UUID from the path
    path_parts = parsed_url.path.split("/")
    if len(path_parts) >= num_parts:
        token_uuid = path_parts[-num_parts]
        _as_uuid(token_uuid, var="token parts")
    else:
        raise ls_utils.LangSmithUserError(f"Invalid public {kind} URL: {url_or_token}")
    if parsed_url.netloc == "smith.langchain.com":
        api_url = "https://api.smith.langchain.com"
    elif parsed_url.netloc == "beta.smith.langchain.com":
        api_url = "https://beta.api.smith.langchain.com"
    return api_url, token_uuid


def _is_langchain_hosted(url: str) -> bool:
    """Check if the URL is langchain hosted.

    Args:
        url (str): The URL to check.

    Returns:
        bool: True if the URL is langchain hosted, False otherwise.
    """
    try:
        netloc = urllib_parse.urlsplit(url).netloc.split(":")[0]
        return netloc.endswith("langchain.com")
    except Exception:
        return False


ID_TYPE = Union[uuid.UUID, str]
RUN_TYPE_T = Literal[
    "tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"
]


@functools.lru_cache(maxsize=1)
def _default_retry_config() -> Retry:
    """Get the default retry configuration.

    If urllib3 version is 1.26 or greater, retry on all methods.

    Returns:
        Retry: The default retry configuration.
    """
    retry_params = dict(
        total=3,
        status_forcelist=[502, 503, 504, 408, 425],
        backoff_factor=0.5,
        # Sadly urllib3 1.x doesn't support backoff_jitter
        raise_on_redirect=False,
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    # the `allowed_methods` keyword is not available in urllib3 < 1.26

    # check to see if urllib3 version is 1.26 or greater
    urllib3_version = importlib.metadata.version("urllib3")
    use_allowed_methods = tuple(map(int, urllib3_version.split("."))) >= (1, 26)

    if use_allowed_methods:
        # Retry on all methods
        retry_params["allowed_methods"] = None

    return ls_utils.LangSmithRetry(**retry_params)  # type: ignore


def close_session(session: requests.Session) -> None:
    """Close the session.

    Args:
        session (requests.Session): The session to close.
    """
    logger.debug("Closing Client.session")
    session.close()


def _validate_api_key_if_hosted(api_url: str, api_key: Optional[str]) -> None:
    """Verify API key is provided if url not localhost.

    Args:
        api_url (str): The API URL.
        api_key (Optional[str]): The API key.

    Returns:
        None

    Raises:
        LangSmithUserError: If the API key is not provided when using the hosted service.
    """
    # If the domain is langchain.com, raise error if no api_key
    if not api_key:
        if _is_langchain_hosted(api_url) and not ls_utils.is_truish(
            ls_utils.get_env_var("OTEL_ENABLED")
        ):
            warnings.warn(
                "API key must be provided when using hosted LangSmith API",
                ls_utils.LangSmithMissingAPIKeyWarning,
            )


def _format_feedback_score(score: Union[float, int, bool, None]):
    """Format a feedback score by truncating numerical values to 4 decimal places.

    Args:
        score: The score to format, can be a number or any other type

    Returns:
        The formatted score
    """
    if isinstance(score, float):
        # Truncate at 4 decimal places
        return round(score, 4)
    return score


def _get_tracing_sampling_rate(
    tracing_sampling_rate: Optional[float] = None,
) -> float | None:
    """Get the tracing sampling rate.

    Returns:
        Optional[float]: The tracing sampling rate.
    """
    if tracing_sampling_rate is None:
        sampling_rate_str = ls_utils.get_env_var("TRACING_SAMPLING_RATE")
        if not sampling_rate_str:
            return None
    else:
        sampling_rate_str = str(tracing_sampling_rate)
    sampling_rate = float(sampling_rate_str)
    if sampling_rate < 0 or sampling_rate > 1:
        raise ls_utils.LangSmithUserError(
            "LANGSMITH_TRACING_SAMPLING_RATE must be between 0 and 1 if set."
            f" Got: {sampling_rate}"
        )
    return sampling_rate


def _get_write_api_urls(_write_api_urls: Optional[dict[str, str]]) -> dict[str, str]:
    _write_api_urls = _write_api_urls or json.loads(
        os.getenv("LANGSMITH_RUNS_ENDPOINTS", "{}")
    )
    processed_write_api_urls = {}
    for url, api_key in _write_api_urls.items():
        processed_url = url.strip()
        if not processed_url:
            raise ls_utils.LangSmithUserError(
                "LangSmith runs API URL within LANGSMITH_RUNS_ENDPOINTS cannot be empty"
            )
        processed_url = processed_url.strip().strip('"').strip("'").rstrip("/")
        processed_api_key = api_key.strip().strip('"').strip("'")
        _validate_api_key_if_hosted(processed_url, processed_api_key)
        processed_write_api_urls[processed_url] = processed_api_key

    return processed_write_api_urls


def _as_uuid(value: ID_TYPE, var: Optional[str] = None) -> uuid.UUID:
    try:
        return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
    except ValueError as e:
        var = var or "value"
        raise ls_utils.LangSmithUserError(
            f"{var} must be a valid UUID or UUID string. Got {value}"
        ) from e


@typing.overload
def _ensure_uuid(value: Optional[Union[str, uuid.UUID]]) -> uuid.UUID: ...


@typing.overload
def _ensure_uuid(
    value: Optional[Union[str, uuid.UUID]], *, accept_null: bool = True
) -> Optional[uuid.UUID]: ...


def _ensure_uuid(value: Optional[Union[str, uuid.UUID]], *, accept_null: bool = False):
    if value is None:
        if accept_null:
            return None
        return uuid.uuid4()
    return _as_uuid(value)


@functools.lru_cache(maxsize=1)
def _parse_url(url):
    parsed_url = urllib_parse.urlparse(url)
    host = parsed_url.netloc.split(":")[0]
    return host


class _LangSmithHttpAdapter(requests_adapters.HTTPAdapter):
    __attrs__ = [
        "max_retries",
        "config",
        "_pool_connections",
        "_pool_maxsize",
        "_pool_block",
        "_blocksize",
    ]

    def __init__(
        self,
        pool_connections: int = requests_adapters.DEFAULT_POOLSIZE,
        pool_maxsize: int = requests_adapters.DEFAULT_POOLSIZE,
        max_retries: Union[Retry, int, None] = requests_adapters.DEFAULT_RETRIES,
        pool_block: bool = requests_adapters.DEFAULT_POOLBLOCK,
        blocksize: int = 16384,  # default from urllib3.BaseHTTPSConnection
    ) -> None:
        self._blocksize = blocksize
        super().__init__(pool_connections, pool_maxsize, max_retries, pool_block)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        if URLLIB3_SUPPORTS_BLOCKSIZE:
            # urllib3 before 2.0 doesn't support blocksize
            pool_kwargs["blocksize"] = self._blocksize
        return super().init_poolmanager(connections, maxsize, block, **pool_kwargs)


class Client:
    """Client for interacting with the LangSmith API."""

    __slots__ = [
        "__weakref__",
        "api_url",
        "_api_key",
        "_headers",
        "retry_config",
        "timeout_ms",
        "_timeout",
        "session",
        "_get_data_type_cached",
        "_web_url",
        "_tenant_id",
        "tracing_sample_rate",
        "_filtered_post_uuids",
        "tracing_queue",
        "_anonymizer",
        "_hide_inputs",
        "_hide_outputs",
        "_hide_metadata",
        "_info",
        "_write_api_urls",
        "_settings",
        "_manual_cleanup",
        "_pyo3_client",
        "compressed_traces",
        "_data_available_event",
        "_futures",
        "otel_exporter",
    ]

    _api_key: Optional[str]
    _headers: dict[str, str]
    _timeout: tuple[float, float]
    _manual_cleanup: bool

    def __init__(
        self,
        api_url: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        retry_config: Optional[Retry] = None,
        timeout_ms: Optional[Union[int, tuple[int, int]]] = None,
        web_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
        auto_batch_tracing: bool = True,
        anonymizer: Optional[Callable[[dict], dict]] = None,
        hide_inputs: Optional[Union[Callable[[dict], dict], bool]] = None,
        hide_outputs: Optional[Union[Callable[[dict], dict], bool]] = None,
        hide_metadata: Optional[Union[Callable[[dict], dict], bool]] = None,
        info: Optional[Union[dict, ls_schemas.LangSmithInfo]] = None,
        api_urls: Optional[dict[str, str]] = None,
        otel_tracer_provider: Optional[TracerProvider] = None,
        tracing_sampling_rate: Optional[float] = None,
    ) -> None:
        """Initialize a Client instance.

        Args:
            api_url (Optional[str]): URL for the LangSmith API. Defaults to the LANGCHAIN_ENDPOINT
                environment variable or https://api.smith.langchain.com if not set.
            api_key (Optional[str]): API key for the LangSmith API. Defaults to the LANGCHAIN_API_KEY
                environment variable.
            retry_config (Optional[Retry]): Retry configuration for the HTTPAdapter.
            timeout_ms (Optional[Union[int, Tuple[int, int]]]): Timeout for the HTTPAdapter. Can also be a 2-tuple of
                (connect timeout, read timeout) to set them separately.
            web_url (Optional[str]): URL for the LangSmith web app. Default is auto-inferred from
                the ENDPOINT.
            session (Optional[requests.Session]): The session to use for requests. If None, a new session will be
                created.
            auto_batch_tracing (bool, default=True): Whether to automatically batch tracing.
            anonymizer (Optional[Callable[[dict], dict]]): A function applied for masking serialized run inputs and outputs,
                before sending to the API.
            hide_inputs (Optional[Union[Callable[[dict], dict], bool]]): Whether to hide run inputs when tracing with this client.
                If True, hides the entire inputs. If a function, applied to
                all run inputs when creating runs.
            hide_outputs (Optional[Union[Callable[[dict], dict], bool]]): Whether to hide run outputs when tracing with this client.
                If True, hides the entire outputs. If a function, applied to
                all run outputs when creating runs.
            hide_metadata (Optional[Union[Callable[[dict], dict], bool]]): Whether to hide run metadata when tracing with this client.
                If True, hides the entire metadata. If a function, applied to
                all run metadata when creating runs.
            info (Optional[ls_schemas.LangSmithInfo]): The information about the LangSmith API.
                If not provided, it will be fetched from the API.
            api_urls (Optional[Dict[str, str]]): A dictionary of write API URLs and their corresponding API keys.
                Useful for multi-tenant setups. Data is only read from the first
                URL in the dictionary. However, ONLY Runs are written (POST and PATCH)
                to all URLs in the dictionary. Feedback, sessions, datasets, examples,
                annotation queues and evaluation results are only written to the first.
            otel_tracer_provider (Optional[TracerProvider]): Optional tracer provider for OpenTelemetry integration.
                If not provided, a LangSmith-specific tracer provider will be used.
            tracing_sampling_rate (Optional[float]): The sampling rate for tracing. If provided,
                overrides the LANGCHAIN_TRACING_SAMPLING_RATE environment variable.
                Should be a float between 0 and 1, where 1 means trace everything
                and 0 means trace nothing.

        Raises:
            LangSmithUserError: If the API key is not provided when using the hosted service.
                If both api_url and api_urls are provided.
        """
        if api_url and api_urls:
            raise ls_utils.LangSmithUserError(
                "You cannot provide both api_url and api_urls."
            )

        if (
            os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT")
        ) and os.getenv("LANGSMITH_RUNS_ENDPOINTS"):
            raise ls_utils.LangSmithUserError(
                "You cannot provide both LANGSMITH_ENDPOINT / LANGCHAIN_ENDPOINT "
                "and LANGSMITH_RUNS_ENDPOINTS."
            )

        self.tracing_sample_rate = _get_tracing_sampling_rate(tracing_sampling_rate)
        self._filtered_post_uuids: set[uuid.UUID] = set()
        self._write_api_urls: Mapping[str, Optional[str]] = _get_write_api_urls(
            api_urls
        )
        if self._write_api_urls:
            self.api_url = next(iter(self._write_api_urls))
            self.api_key = self._write_api_urls[self.api_url]
        else:
            self.api_url = ls_utils.get_api_url(api_url)
            self.api_key = ls_utils.get_api_key(api_key)
            _validate_api_key_if_hosted(self.api_url, self.api_key)
            self._write_api_urls = {self.api_url: self.api_key}
        self.retry_config = retry_config or _default_retry_config()
        self.timeout_ms = (
            (timeout_ms, timeout_ms)
            if isinstance(timeout_ms, int)
            else (timeout_ms or (10_000, 90_001))
        )
        self._timeout = (self.timeout_ms[0] / 1000, self.timeout_ms[1] / 1000)
        self._web_url = web_url
        self._tenant_id: Optional[uuid.UUID] = None
        # Create a session and register a finalizer to close it
        session_ = session if session else requests.Session()
        self.session = session_
        self._info = (
            info
            if info is None or isinstance(info, ls_schemas.LangSmithInfo)
            else ls_schemas.LangSmithInfo(**info)
        )
        weakref.finalize(self, close_session, self.session)
        atexit.register(close_session, session_)
        self.compressed_traces: Optional[CompressedTraces] = None
        self._data_available_event: Optional[threading.Event] = None
        self._futures: Optional[weakref.WeakSet[cf.Future]] = None
        self.otel_exporter: Optional[OTELExporter] = None

        # Initialize auto batching
        if auto_batch_tracing:
            self.tracing_queue: Optional[PriorityQueue] = PriorityQueue()

            threading.Thread(
                target=_tracing_control_thread_func,
                # arg must be a weakref to self to avoid the Thread object
                # preventing garbage collection of the Client object
                args=(weakref.ref(self),),
            ).start()
        else:
            self.tracing_queue = None

        # Mount the HTTPAdapter with the retry configuration.
        adapter = _LangSmithHttpAdapter(
            max_retries=self.retry_config,
            blocksize=_BLOCKSIZE_BYTES,
            # We need to set the pool_maxsize to a value greater than the
            # number of threads used for batch tracing, plus 1 for other
            # requests.
            pool_maxsize=_AUTO_SCALE_UP_NTHREADS_LIMIT + 1,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self._get_data_type_cached = functools.lru_cache(maxsize=10)(
            self._get_data_type
        )
        self._anonymizer = anonymizer
        self._hide_inputs = (
            hide_inputs
            if hide_inputs is not None
            else ls_utils.get_env_var("HIDE_INPUTS") == "true"
        )
        self._hide_outputs = (
            hide_outputs
            if hide_outputs is not None
            else ls_utils.get_env_var("HIDE_OUTPUTS") == "true"
        )
        self._hide_metadata = (
            hide_metadata
            if hide_metadata is not None
            else ls_utils.get_env_var("HIDE_METADATA") == "true"
        )

        # To trigger this code, set the `LANGSMITH_USE_PYO3_CLIENT` env var to any value.
        self._pyo3_client = None
        if ls_utils.get_env_var("USE_PYO3_CLIENT") is not None:
            langsmith_pyo3 = None
            try:
                import langsmith_pyo3  # type: ignore[import-not-found, no-redef]
            except ImportError as e:
                logger.warning(
                    "Failed to import `langsmith_pyo3` when PyO3 client was requested, "
                    "falling back to Python impl: %s",
                    repr(e),
                )

            if langsmith_pyo3:
                # TODO: tweak these constants as needed
                queue_capacity = 1_000_000
                batch_size = 100
                batch_timeout_millis = 1000
                worker_threads = 1

                try:
                    self._pyo3_client = langsmith_pyo3.BlockingTracingClient(
                        self.api_url,
                        self.api_key,
                        queue_capacity,
                        batch_size,
                        batch_timeout_millis,
                        worker_threads,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to instantiate `langsmith_pyo3.BlockingTracingClient` "
                        "when PyO3 client was requested, falling back to Python impl: %s",
                        repr(e),
                    )

        self._settings: Union[ls_schemas.LangSmithSettings, None] = None

        self._manual_cleanup = False

        if ls_utils.is_truish(ls_utils.get_env_var("OTEL_ENABLED")):
            if not HAS_OTEL:
                warnings.warn(
                    "LANGSMITH_OTEL_ENABLED is set but OpenTelemetry packages are not installed. "
                    "Install with `pip install langsmith[otel]`"
                )
            existing_provider = otel_trace.get_tracer_provider()
            tracer = existing_provider.get_tracer(__name__)
            if otel_tracer_provider is None:
                # Use existing global provider if available
                if not (
                    isinstance(existing_provider, otel_trace.ProxyTracerProvider)
                    and hasattr(tracer, "_tracer")
                    and isinstance(
                        cast(
                            otel_trace.ProxyTracer,
                            tracer,
                        )._tracer,
                        otel_trace.NoOpTracer,
                    )
                ):
                    otel_tracer_provider = cast(TracerProvider, existing_provider)
                else:
                    otel_tracer_provider = get_otlp_tracer_provider()
                    otel_trace.set_tracer_provider(otel_tracer_provider)

            self.otel_exporter = OTELExporter(tracer_provider=otel_tracer_provider)

    def _repr_html_(self) -> str:
        """Return an HTML representation of the instance with a link to the URL.

        Returns:
            str: The HTML representation of the instance.
        """
        link = self._host_url
        return f'<a href="{link}", target="_blank" rel="noopener">LangSmith Client</a>'

    def __repr__(self) -> str:
        """Return a string representation of the instance with a link to the URL.

        Returns:
            str: The string representation of the instance.
        """
        return f"Client (API URL: {self.api_url})"

    @property
    def _host(self) -> str:
        return _parse_url(self.api_url)

    @property
    def _host_url(self) -> str:
        """The web host url."""
        return ls_utils.get_host_url(self._web_url, self.api_url)

    def _compute_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": f"langsmith-py/{langsmith.__version__}",
            "Accept": "application/json",
        }
        if self.api_key:
            headers[X_API_KEY] = self.api_key
        return headers

    @property
    def api_key(self) -> Optional[str]:
        """Return the API key used for authentication."""
        return self._api_key

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        object.__setattr__(self, "_api_key", value)
        object.__setattr__(self, "_headers", self._compute_headers())

    @property
    def info(self) -> ls_schemas.LangSmithInfo:
        """Get the information about the LangSmith API.

        Returns:
            ls_schemas.LangSmithInfo: The information about the LangSmith API, or None if the API is
                not available.
        """
        if self._info is None:
            try:
                response = self.request_with_retries(
                    "GET",
                    "/info",
                    headers={"Accept": "application/json"},
                    timeout=self._timeout,
                )
                ls_utils.raise_for_status_with_text(response)
                self._info = ls_schemas.LangSmithInfo(**response.json())
            except BaseException as e:
                logger.warning(
                    f"Failed to get info from {self.api_url}: {repr(e)}",
                )
                self._info = ls_schemas.LangSmithInfo()
        return self._info

    def _get_settings(self) -> ls_schemas.LangSmithSettings:
        """Get the settings for the current tenant.

        Returns:
            dict: The settings for the current tenant.
        """
        if self._settings is None:
            response = self.request_with_retries("GET", "/settings")
            ls_utils.raise_for_status_with_text(response)
            self._settings = ls_schemas.LangSmithSettings(**response.json())

        return self._settings

    def _content_above_size(self, content_length: Optional[int]) -> Optional[str]:
        if content_length is None or self._info is None:
            return None
        info = cast(ls_schemas.LangSmithInfo, self._info)
        bic = info.batch_ingest_config
        if not bic:
            return None
        size_limit = bic.get("size_limit_bytes")
        if size_limit is None:
            return None
        if content_length > size_limit:
            return (
                f"The content length of {content_length} bytes exceeds the "
                f"maximum size limit of {size_limit} bytes."
            )
        return None

    def request_with_retries(
        self,
        /,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        pathname: str,
        *,
        request_kwargs: Optional[Mapping] = None,
        stop_after_attempt: int = 1,
        retry_on: Optional[Sequence[type[BaseException]]] = None,
        to_ignore: Optional[Sequence[type[BaseException]]] = None,
        handle_response: Optional[Callable[[requests.Response, int], Any]] = None,
        _context: str = "",
        **kwargs: Any,
    ) -> requests.Response:
        """Send a request with retries.

        Args:
            method (str): The HTTP request method.
            pathname (str): The pathname of the request URL. Will be appended to the API URL.
            request_kwargs (Mapping): Additional request parameters.
            stop_after_attempt (int, default=1): The number of attempts to make.
            retry_on (Optional[Sequence[Type[BaseException]]]): The exceptions to retry on. In addition to:
                [LangSmithConnectionError, LangSmithAPIError].
            to_ignore (Optional[Sequence[Type[BaseException]]]): The exceptions to ignore / pass on.
            handle_response (Optional[Callable[[requests.Response, int], Any]]): A function to handle the response and return whether to continue retrying.
            _context (str, default=""): The context of the request.
            **kwargs (Any): Additional keyword arguments to pass to the request.

        Returns:
            requests.Response: The response object.

        Raises:
            LangSmithAPIError: If a server error occurs.
            LangSmithUserError: If the request fails.
            LangSmithConnectionError: If a connection error occurs.
            LangSmithError: If the request fails.
        """
        request_kwargs = request_kwargs or {}
        request_kwargs = {
            "timeout": self._timeout,
            **request_kwargs,
            **kwargs,
            "headers": {
                **self._headers,
                **request_kwargs.get("headers", {}),
                **kwargs.get("headers", {}),
            },
        }
        if (
            method != "GET"
            and "data" in request_kwargs
            and "files" not in request_kwargs
            and not request_kwargs["headers"].get("Content-Type")
        ):
            request_kwargs["headers"]["Content-Type"] = "application/json"
        logging_filters = [
            ls_utils.FilterLangSmithRetry(),
            ls_utils.FilterPoolFullWarning(host=str(self._host)),
        ]
        retry_on_: tuple[type[BaseException], ...] = (
            *(retry_on or ()),
            *(
                ls_utils.LangSmithConnectionError,
                ls_utils.LangSmithRequestTimeout,  # 408
                ls_utils.LangSmithAPIError,  # 500
            ),
        )
        to_ignore_: tuple[type[BaseException], ...] = (*(to_ignore or ()),)
        response = None
        for idx in range(stop_after_attempt):
            try:
                try:
                    with ls_utils.filter_logs(_urllib3_logger, logging_filters):
                        response = self.session.request(
                            method,
                            _construct_url(self.api_url, pathname),
                            stream=False,
                            **request_kwargs,
                        )
                    ls_utils.raise_for_status_with_text(response)
                    return response
                except requests.exceptions.ReadTimeout as e:
                    logger.debug("Passing on exception %s", e)
                    if idx + 1 == stop_after_attempt:
                        raise
                    sleep_time = 2**idx + (random.random() * 0.5)
                    time.sleep(sleep_time)
                    continue

                except requests.HTTPError as e:
                    if response is not None:
                        if handle_response is not None:
                            if idx + 1 < stop_after_attempt:
                                should_continue = handle_response(response, idx + 1)
                                if should_continue:
                                    continue
                        if response.status_code == 500:
                            raise ls_utils.LangSmithAPIError(
                                f"Server error caused failure to {method}"
                                f" {pathname} in"
                                f" LangSmith API. {repr(e)}"
                                f"{_context}"
                            )
                        elif response.status_code == 408:
                            raise ls_utils.LangSmithRequestTimeout(
                                f"Client took too long to send request to {method}"
                                f"{pathname} {_context}"
                            )
                        elif response.status_code == 429:
                            raise ls_utils.LangSmithRateLimitError(
                                f"Rate limit exceeded for {pathname}. {repr(e)}"
                                f"{_context}"
                            )
                        elif response.status_code == 401:
                            raise ls_utils.LangSmithAuthError(
                                f"Authentication failed for {pathname}. {repr(e)}"
                                f"{_context}"
                            )
                        elif response.status_code == 404:
                            raise ls_utils.LangSmithNotFoundError(
                                f"Resource not found for {pathname}. {repr(e)}"
                                f"{_context}"
                            )
                        elif response.status_code == 409:
                            raise ls_utils.LangSmithConflictError(
                                f"Conflict for {pathname}. {repr(e)}{_context}"
                            )
                        else:
                            raise ls_utils.LangSmithError(
                                f"Failed to {method} {pathname} in LangSmith"
                                f" API. {repr(e)}"
                            )

                    else:
                        raise ls_utils.LangSmithUserError(
                            f"Failed to {method} {pathname} in LangSmith API. {repr(e)}"
                        )
                except requests.ConnectionError as e:
                    recommendation = (
                        "Please confirm your LANGCHAIN_ENDPOINT."
                        if self.api_url != "https://api.smith.langchain.com"
                        else "Please confirm your internet connection."
                    )
                    try:
                        content_length = int(
                            str(e.request.headers.get("Content-Length"))
                            if e.request
                            else ""
                        )
                        size_rec = self._content_above_size(content_length)
                        if size_rec:
                            recommendation = size_rec
                    except ValueError:
                        content_length = None

                    api_key = (
                        e.request.headers.get("x-api-key") or "" if e.request else ""
                    )
                    prefix, suffix = api_key[:5], api_key[-2:]
                    filler = "*" * (max(0, len(api_key) - 7))
                    masked_api_key = f"{prefix}{filler}{suffix}"

                    raise ls_utils.LangSmithConnectionError(
                        f"Connection error caused failure to {method} {pathname}"
                        f" in LangSmith API. {recommendation}"
                        f" {repr(e)}"
                        f"\nContent-Length: {content_length}"
                        f"\nAPI Key: {masked_api_key}"
                        f"{_context}"
                    ) from e
                except Exception as e:
                    args = list(e.args)
                    msg = args[1] if len(args) > 1 else ""
                    msg = msg.replace("session", "session (project)")
                    if args:
                        emsg = "\n".join(
                            [str(args[0])]
                            + [msg]
                            + [str(arg) for arg in (args[2:] if len(args) > 2 else [])]
                        )
                    else:
                        emsg = msg
                    raise ls_utils.LangSmithError(
                        f"Failed to {method} {pathname} in LangSmith API. {emsg}"
                        f"{_context}"
                    ) from e
            except to_ignore_ as e:
                if response is not None:
                    logger.debug("Passing on exception %s", e)
                    return response
            except ls_utils.LangSmithRateLimitError:
                if idx + 1 == stop_after_attempt:
                    raise
                if response is not None:
                    try:
                        retry_after = float(response.headers.get("retry-after", "30"))
                    except Exception as e:
                        logger.warning(
                            "Invalid retry-after header: %s",
                            repr(e),
                        )
                        retry_after = 30
                # Add exponential backoff
                retry_after = retry_after * 2**idx + random.random()
                time.sleep(retry_after)
            except retry_on_:
                # Handle other exceptions more immediately
                if idx + 1 == stop_after_attempt:
                    raise
                sleep_time = 2**idx + (random.random() * 0.5)
                time.sleep(sleep_time)
                continue
            # Else we still raise an error

        raise ls_utils.LangSmithError(
            f"Failed to {method} {pathname} in LangSmith API."
        )

    def _get_paginated_list(
        self, path: str, *, params: Optional[dict] = None
    ) -> Iterator[dict]:
        """Get a paginated list of items.

        Args:
            path (str): The path of the request URL.
            params (Optional[dict]): The query parameters.

        Yields:
            The items in the paginated list.
        """
        params_ = params.copy() if params else {}
        offset = params_.get("offset", 0)
        params_["limit"] = params_.get("limit", 100)
        while True:
            params_["offset"] = offset
            response = self.request_with_retries(
                "GET",
                path,
                params=params_,
            )
            items = response.json()
            if not items:
                break
            yield from items
            if len(items) < params_["limit"]:
                # offset and limit isn't respected if we're
                # querying for specific values
                break
            offset += len(items)

    def _get_cursor_paginated_list(
        self,
        path: str,
        *,
        body: Optional[dict] = None,
        request_method: Literal["GET", "POST"] = "POST",
        data_key: str = "runs",
    ) -> Iterator[dict]:
        """Get a cursor paginated list of items.

        Args:
            path (str): The path of the request URL.
            body (Optional[dict]): The query body.
            request_method (Literal["GET", "POST"], default="POST"): The HTTP request method.
            data_key (str, default="runs"): The key in the response body that contains the items.

        Yields:
            The items in the paginated list.
        """
        params_ = body.copy() if body else {}
        while True:
            response = self.request_with_retries(
                request_method,
                path,
                request_kwargs={
                    "data": _dumps_json(params_),
                },
            )
            response_body = response.json()
            if not response_body:
                break
            if not response_body.get(data_key):
                break
            yield from response_body[data_key]
            cursors = response_body.get("cursors")
            if not cursors:
                break
            if not cursors.get("next"):
                break
            params_["cursor"] = cursors["next"]

    def upload_dataframe(
        self,
        df: pd.DataFrame,
        name: str,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        *,
        description: Optional[str] = None,
        data_type: Optional[ls_schemas.DataType] = ls_schemas.DataType.kv,
    ) -> ls_schemas.Dataset:
        """Upload a dataframe as individual examples to the LangSmith API.

        Args:
            df (pd.DataFrame): The dataframe to upload.
            name (str): The name of the dataset.
            input_keys (Sequence[str]): The input keys.
            output_keys (Sequence[str]): The output keys.
            description (Optional[str]): The description of the dataset.
            data_type (Optional[DataType]): The data type of the dataset.

        Returns:
            Dataset: The uploaded dataset.

        Raises:
            ValueError: If the csv_file is not a string or tuple.

        Examples:

            .. code-block:: python

                from langsmith import Client
                import os
                import pandas as pd

                client = Client()

                df = pd.read_parquet("path/to/your/myfile.parquet")
                input_keys = ["column1", "column2"]  # replace with your input column names
                output_keys = ["output1", "output2"]  # replace with your output column names

                dataset = client.upload_dataframe(
                    df=df,
                    input_keys=input_keys,
                    output_keys=output_keys,
                    name="My Parquet Dataset",
                    description="Dataset created from a parquet file",
                    data_type="kv",  # The default
                )
        """
        csv_file = io.BytesIO()
        df.to_csv(csv_file, index=False)
        csv_file.seek(0)
        return self.upload_csv(
            ("data.csv", csv_file),
            input_keys=input_keys,
            output_keys=output_keys,
            description=description,
            name=name,
            data_type=data_type,
        )

    def upload_csv(
        self,
        csv_file: Union[str, tuple[str, io.BytesIO]],
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        data_type: Optional[ls_schemas.DataType] = ls_schemas.DataType.kv,
    ) -> ls_schemas.Dataset:
        """Upload a CSV file to the LangSmith API.

        Args:
            csv_file (Union[str, Tuple[str, io.BytesIO]]): The CSV file to upload. If a string, it should be the path
                If a tuple, it should be a tuple containing the filename
                and a BytesIO object.
            input_keys (Sequence[str]): The input keys.
            output_keys (Sequence[str]): The output keys.
            name (Optional[str]): The name of the dataset.
            description (Optional[str]): The description of the dataset.
            data_type (Optional[ls_schemas.DataType]): The data type of the dataset.

        Returns:
            Dataset: The uploaded dataset.

        Raises:
            ValueError: If the csv_file is not a string or tuple.

        Examples:

            .. code-block:: python

                from langsmith import Client
                import os

                client = Client()

                csv_file = "path/to/your/myfile.csv"
                input_keys = ["column1", "column2"]  # replace with your input column names
                output_keys = ["output1", "output2"]  # replace with your output column names

                dataset = client.upload_csv(
                    csv_file=csv_file,
                    input_keys=input_keys,
                    output_keys=output_keys,
                    name="My CSV Dataset",
                    description="Dataset created from a CSV file",
                    data_type="kv",  # The default
                )
        """
        data = {
            "input_keys": input_keys,
            "output_keys": output_keys,
        }
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if data_type:
            data["data_type"] = ls_utils.get_enum_value(data_type)
        data["id"] = str(uuid.uuid4())
        if isinstance(csv_file, str):
            with open(csv_file, "rb") as f:
                file_ = {"file": f}
                response = self.request_with_retries(
                    "POST",
                    "/datasets/upload",
                    data=data,
                    files=file_,
                )
        elif isinstance(csv_file, tuple):
            response = self.request_with_retries(
                "POST",
                "/datasets/upload",
                data=data,
                files={"file": csv_file},
            )
        else:
            raise ValueError("csv_file must be a string or tuple")
        ls_utils.raise_for_status_with_text(response)
        result = response.json()
        # TODO: Make this more robust server-side
        if "detail" in result and "already exists" in result["detail"]:
            file_name = csv_file if isinstance(csv_file, str) else csv_file[0]
            file_name = file_name.split("/")[-1]
            raise ValueError(f"Dataset {file_name} already exists")
        return ls_schemas.Dataset(
            **result,
            _host_url=self._host_url,
            _tenant_id=self._get_optional_tenant_id(),
        )

    def _run_transform(
        self,
        run: Union[ls_schemas.Run, dict, ls_schemas.RunLikeDict],
        update: bool = False,
        copy: bool = False,
    ) -> dict:
        """Transform the given run object into a dictionary representation.

        Args:
            run (Union[ls_schemas.Run, dict]): The run object to transform.
            update (Optional[bool]): Whether the payload is for an "update" event.
            copy (Optional[bool]): Whether to deepcopy run inputs/outputs.

        Returns:
            dict: The transformed run object as a dictionary.
        """
        if hasattr(run, "dict") and callable(getattr(run, "dict")):
            run_create: dict = run.dict()  # type: ignore
        else:
            run_create = cast(dict, run)
        if "id" not in run_create:
            run_create["id"] = uuid.uuid4()
        elif isinstance(run_create["id"], str):
            run_create["id"] = uuid.UUID(run_create["id"])
        if "inputs" in run_create and run_create["inputs"] is not None:
            if copy:
                run_create["inputs"] = ls_utils.deepish_copy(run_create["inputs"])
            run_create["inputs"] = self._hide_run_inputs(run_create["inputs"])
        if "outputs" in run_create and run_create["outputs"] is not None:
            if copy:
                run_create["outputs"] = ls_utils.deepish_copy(run_create["outputs"])
            run_create["outputs"] = self._hide_run_outputs(run_create["outputs"])
        # Hide metadata in extra if present
        if "extra" in run_create and isinstance(run_create["extra"], dict):
            extra = run_create["extra"]
            if "metadata" in extra and extra["metadata"] is not None:
                if copy:
                    extra["metadata"] = ls_utils.deepish_copy(extra["metadata"])
                extra["metadata"] = self._hide_run_metadata(extra["metadata"])
        if not update and not run_create.get("start_time"):
            run_create["start_time"] = datetime.datetime.now(datetime.timezone.utc)

        # Only retain LLM & Prompt manifests
        if "serialized" in run_create:
            if run_create.get("run_type") not in ("llm", "prompt"):
                # Drop completely
                run_create.pop("serialized", None)
            elif run_create.get("serialized"):
                # Drop graph
                run_create["serialized"].pop("graph", None)

        return run_create

    @staticmethod
    def _insert_runtime_env(runs: Sequence[dict]) -> None:
        runtime_env = ls_env.get_runtime_environment()
        for run_create in runs:
            run_extra = cast(dict, run_create.setdefault("extra", {}))
            # update runtime
            runtime: dict = run_extra.setdefault("runtime", {})
            run_extra["runtime"] = {**runtime_env, **runtime}
            # update metadata
            metadata: dict = run_extra.setdefault("metadata", {})
            langchain_metadata = ls_env.get_langchain_env_var_metadata()
            metadata.update(
                {k: v for k, v in langchain_metadata.items() if k not in metadata}
            )

    def _should_sample(self) -> bool:
        if self.tracing_sample_rate is None:
            return True
        return random.random() < self.tracing_sample_rate

    def _filter_for_sampling(
        self, runs: Iterable[dict], *, patch: bool = False
    ) -> list[dict]:
        if self.tracing_sample_rate is None:
            return list(runs)

        if patch:
            sampled = []
            for run in runs:
                trace_id = _as_uuid(run["trace_id"])
                if trace_id not in self._filtered_post_uuids:
                    sampled.append(run)
                elif run["id"] == trace_id:
                    self._filtered_post_uuids.remove(trace_id)
            return sampled
        else:
            sampled = []
            for run in runs:
                trace_id = run.get("trace_id") or run["id"]

                # If we've already made a decision about this trace, follow it
                if trace_id in self._filtered_post_uuids:
                    continue

                # For new traces, apply sampling
                if run["id"] == trace_id:
                    if self._should_sample():
                        sampled.append(run)
                    else:
                        self._filtered_post_uuids.add(trace_id)
                else:
                    # Child runs follow their trace's sampling decision
                    sampled.append(run)
            return sampled

    def create_run(
        self,
        name: str,
        inputs: dict[str, Any],
        run_type: RUN_TYPE_T,
        *,
        project_name: Optional[str] = None,
        revision_id: Optional[str] = None,
        dangerously_allow_filesystem: bool = False,
        **kwargs: Any,
    ) -> None:
        """Persist a run to the LangSmith API.

        Args:
            name (str): The name of the run.
            inputs (Dict[str, Any]): The input values for the run.
            run_type (str): The type of the run, such as tool, chain, llm, retriever,
                embedding, prompt, or parser.
            project_name (Optional[str]): The project name of the run.
            revision_id (Optional[Union[UUID, str]]): The revision ID of the run.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            None

        Raises:
            LangSmithUserError: If the API key is not provided when using the hosted service.

        Examples:

            .. code-block:: python

                from langsmith import Client
                import datetime
                from uuid import uuid4

                client = Client()

                run_id = uuid4()
                client.create_run(
                    id=run_id,
                    project_name=project_name,
                    name="test_run",
                    run_type="llm",
                    inputs={"prompt": "hello world"},
                    outputs={"generation": "hi there"},
                    start_time=datetime.datetime.now(datetime.timezone.utc),
                    end_time=datetime.datetime.now(datetime.timezone.utc),
                    hide_inputs=True,
                    hide_outputs=True,
                )
        """
        project_name = project_name or kwargs.pop(
            "session_name",
            # if the project is not provided, use the environment's project
            ls_utils.get_tracer_project(),
        )
        run_create = {
            **kwargs,
            "session_name": project_name,
            "name": name,
            "inputs": inputs,
            "run_type": run_type,
        }
        if not self._filter_for_sampling([run_create]):
            return
        if revision_id is not None:
            run_create["extra"]["metadata"]["revision_id"] = revision_id
        run_create = self._run_transform(run_create, copy=False)
        self._insert_runtime_env([run_create])
        if run_create.get("attachments") is not None:
            for attachment in run_create["attachments"].values():
                if (
                    isinstance(attachment, tuple)
                    and isinstance(attachment[1], Path)
                    and not dangerously_allow_filesystem
                ):
                    raise ValueError(
                        "Must set dangerously_allow_filesystem=True to allow passing in Paths for attachments."
                    )

        if (
            # batch ingest requires trace_id and dotted_order to be set
            run_create.get("trace_id") is not None
            and run_create.get("dotted_order") is not None
        ):
            if self._pyo3_client is not None:
                self._pyo3_client.create_run(run_create)
            elif self.compressed_traces is not None:
                if self._data_available_event is None:
                    raise ValueError(
                        "Run compression is enabled but threading event is not configured"
                    )
                serialized_op = serialize_run_dict("post", run_create)
                (
                    multipart_form,
                    opened_files,
                ) = serialized_run_operation_to_multipart_parts_and_context(
                    serialized_op
                )
                logger.log(
                    5,
                    "Adding compressed multipart to queue with context: %s",
                    multipart_form.context,
                )
                with self.compressed_traces.lock:
                    compress_multipart_parts_and_context(
                        multipart_form,
                        self.compressed_traces,
                        _BOUNDARY,
                    )
                    self.compressed_traces.trace_count += 1
                    self._data_available_event.set()

                _close_files(list(opened_files.values()))
            elif self.tracing_queue is not None:
                serialized_op = serialize_run_dict("post", run_create)
                logger.log(
                    5,
                    "Adding to tracing queue: trace_id=%s, run_id=%s",
                    serialized_op.trace_id,
                    serialized_op.id,
                )
                if HAS_OTEL:
                    self.tracing_queue.put(
                        TracingQueueItem(
                            run_create["dotted_order"],
                            serialized_op,
                            otel_context=set_span_in_context(
                                otel_trace.get_current_span()
                            ),
                        )
                    )
                else:
                    self.tracing_queue.put(
                        TracingQueueItem(run_create["dotted_order"], serialized_op)
                    )
            else:
                # Neither Rust nor Python batch ingestion is configured,
                # fall back to the non-batch approach.
                self._create_run(run_create)
        else:
            self._create_run(run_create)

    def _create_run(self, run_create: dict):
        errors = []
        for api_url, api_key in self._write_api_urls.items():
            headers = {**self._headers, X_API_KEY: api_key}
            try:
                self.request_with_retries(
                    "POST",
                    f"{api_url}/runs",
                    request_kwargs={
                        "data": _dumps_json(run_create),
                        "headers": headers,
                    },
                    to_ignore=(ls_utils.LangSmithConflictError,),
                )
            except Exception as e:
                errors.append(e)
        if errors:
            if len(errors) > 1:
                raise ls_utils.LangSmithExceptionGroup(exceptions=errors)
            else:
                raise errors[0]

    def _hide_run_inputs(self, inputs: dict):
        if self._hide_inputs is True:
            return {}
        if self._anonymizer:
            json_inputs = _orjson.loads(_dumps_json(inputs))
            return self._anonymizer(json_inputs)
        if self._hide_inputs is False:
            return inputs
        return self._hide_inputs(inputs)

    def _hide_run_outputs(self, outputs: dict):
        if self._hide_outputs is True:
            return {}
        if self._anonymizer:
            json_outputs = _orjson.loads(_dumps_json(outputs))
            return self._anonymizer(json_outputs)
        if self._hide_outputs is False:
            return outputs
        return self._hide_outputs(outputs)

    def _hide_run_metadata(self, metadata: dict) -> dict:
        if self._hide_metadata is True:
            return {}
        if self._hide_metadata is False:
            return metadata
        return self._hide_metadata(metadata)

    def _batch_ingest_run_ops(
        self,
        ops: list[SerializedRunOperation],
    ) -> None:
        ids_and_partial_body: dict[
            Literal["post", "patch"], list[tuple[str, bytes]]
        ] = {
            "post": [],
            "patch": [],
        }

        # form the partial body and ids
        for op in ops:
            if isinstance(op, SerializedRunOperation):
                curr_dict = _orjson.loads(op._none)
                if op.inputs:
                    curr_dict["inputs"] = _orjson.Fragment(op.inputs)
                if op.outputs:
                    curr_dict["outputs"] = _orjson.Fragment(op.outputs)
                if op.events:
                    curr_dict["events"] = _orjson.Fragment(op.events)
                if op.attachments:
                    logger.warning(
                        "Attachments are not supported when use_multipart_endpoint "
                        "is False"
                    )
                ids_and_partial_body[op.operation].append(
                    (f"trace={op.trace_id},id={op.id}", _orjson.dumps(curr_dict))
                )
            elif isinstance(op, SerializedFeedbackOperation):
                logger.warning(
                    "Feedback operations are not supported in non-multipart mode"
                )
            else:
                logger.error("Unknown item type in tracing queue: %s", type(op))

        # send the requests in batches
        info = self.info
        size_limit_bytes = (info.batch_ingest_config or {}).get(
            "size_limit_bytes"
        ) or _SIZE_LIMIT_BYTES

        body_chunks: collections.defaultdict[str, list] = collections.defaultdict(list)
        context_ids: collections.defaultdict[str, list] = collections.defaultdict(list)
        body_size = 0
        for key in cast(list[Literal["post", "patch"]], ["post", "patch"]):
            body_deque = collections.deque(ids_and_partial_body[key])
            while body_deque:
                if (
                    body_size > 0
                    and body_size + len(body_deque[0][1]) > size_limit_bytes
                ):
                    self._post_batch_ingest_runs(
                        _orjson.dumps(body_chunks),
                        _context=f"\n{key}: {'; '.join(context_ids[key])}",
                    )
                    body_size = 0
                    body_chunks.clear()
                    context_ids.clear()
                curr_id, curr_body = body_deque.popleft()
                body_size += len(curr_body)
                body_chunks[key].append(_orjson.Fragment(curr_body))
                context_ids[key].append(curr_id)
        if body_size:
            context = "; ".join(f"{k}: {'; '.join(v)}" for k, v in context_ids.items())
            self._post_batch_ingest_runs(
                _orjson.dumps(body_chunks), _context="\n" + context
            )

    def batch_ingest_runs(
        self,
        create: Optional[
            Sequence[Union[ls_schemas.Run, ls_schemas.RunLikeDict, dict]]
        ] = None,
        update: Optional[
            Sequence[Union[ls_schemas.Run, ls_schemas.RunLikeDict, dict]]
        ] = None,
        *,
        pre_sampled: bool = False,
    ) -> None:
        """Batch ingest/upsert multiple runs in the Langsmith system.

        Args:
            create (Optional[Sequence[Union[Run, RunLikeDict]]]):
                A sequence of `Run` objects or equivalent dictionaries representing
                runs to be created / posted.
            update (Optional[Sequence[Union[Run, RunLikeDict]]]):
                A sequence of `Run` objects or equivalent dictionaries representing
                runs that have already been created and should be updated / patched.
            pre_sampled (bool, default=False): Whether the runs have already been subject
                to sampling, and therefore should not be sampled again.
                Defaults to False.

        Raises:
            LangsmithAPIError: If there is an error in the API request.

        Returns:
            None

        Note:
            - The run objects MUST contain the dotted_order and trace_id fields
                to be accepted by the API.

        Examples:

            .. code-block:: python

                from langsmith import Client
                import datetime
                from uuid import uuid4

                client = Client()
                _session = "__test_batch_ingest_runs"
                trace_id = uuid4()
                trace_id_2 = uuid4()
                run_id_2 = uuid4()
                current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y%m%dT%H%M%S%fZ"
                )
                later_time = (
                    datetime.datetime.now(datetime.timezone.utc) + timedelta(seconds=1)
                ).strftime("%Y%m%dT%H%M%S%fZ")

                runs_to_create = [
                    {
                        "id": str(trace_id),
                        "session_name": _session,
                        "name": "run 1",
                        "run_type": "chain",
                        "dotted_order": f"{current_time}{str(trace_id)}",
                        "trace_id": str(trace_id),
                        "inputs": {"input1": 1, "input2": 2},
                        "outputs": {"output1": 3, "output2": 4},
                    },
                    {
                        "id": str(trace_id_2),
                        "session_name": _session,
                        "name": "run 3",
                        "run_type": "chain",
                        "dotted_order": f"{current_time}{str(trace_id_2)}",
                        "trace_id": str(trace_id_2),
                        "inputs": {"input1": 1, "input2": 2},
                        "error": "error",
                    },
                    {
                        "id": str(run_id_2),
                        "session_name": _session,
                        "name": "run 2",
                        "run_type": "chain",
                        "dotted_order": f"{current_time}{str(trace_id)}."
                        f"{later_time}{str(run_id_2)}",
                        "trace_id": str(trace_id),
                        "parent_run_id": str(trace_id),
                        "inputs": {"input1": 5, "input2": 6},
                    },
                ]
                runs_to_update = [
                    {
                        "id": str(run_id_2),
                        "dotted_order": f"{current_time}{str(trace_id)}."
                        f"{later_time}{str(run_id_2)}",
                        "trace_id": str(trace_id),
                        "parent_run_id": str(trace_id),
                        "outputs": {"output1": 4, "output2": 5},
                    },
                ]

                client.batch_ingest_runs(create=runs_to_create, update=runs_to_update)
        """
        if not create and not update:
            return
        # transform and convert to dicts
        create_dicts = [
            self._run_transform(run, copy=False) for run in create or EMPTY_SEQ
        ]
        update_dicts = [
            self._run_transform(run, update=True, copy=False)
            for run in update or EMPTY_SEQ
        ]
        for run in create_dicts:
            if not run.get("trace_id") or not run.get("dotted_order"):
                raise ls_utils.LangSmithUserError(
                    "Batch ingest requires trace_id and dotted_order to be set."
                )
        for run in update_dicts:
            if not run.get("trace_id") or not run.get("dotted_order"):
                raise ls_utils.LangSmithUserError(
                    "Batch ingest requires trace_id and dotted_order to be set."
                )
        # filter out runs that are not sampled
        if not pre_sampled:
            create_dicts = self._filter_for_sampling(create_dicts)
            update_dicts = self._filter_for_sampling(update_dicts, patch=True)

        if not create_dicts and not update_dicts:
            return

        self._insert_runtime_env(create_dicts + update_dicts)

        # convert to serialized ops
        serialized_ops = cast(
            list[SerializedRunOperation],
            combine_serialized_queue_operations(
                list(
                    itertools.chain(
                        (serialize_run_dict("post", run) for run in create_dicts),
                        (serialize_run_dict("patch", run) for run in update_dicts),
                    )
                )
            ),
        )

        self._batch_ingest_run_ops(serialized_ops)

    def _post_batch_ingest_runs(self, body: bytes, *, _context: str):
        for api_url, api_key in self._write_api_urls.items():
            try:
                logger.debug(f"Sending batch ingest request with context: {_context}")
                self.request_with_retries(
                    "POST",
                    f"{api_url}/runs/batch",
                    request_kwargs={
                        "data": body,
                        "headers": {
                            **self._headers,
                            X_API_KEY: api_key,
                        },
                    },
                    to_ignore=(ls_utils.LangSmithConflictError,),
                    stop_after_attempt=3,
                    _context=_context,
                )
            except Exception as e:
                try:
                    exc_desc_lines = traceback.format_exception_only(type(e), e)
                    exc_desc = "".join(exc_desc_lines).rstrip()
                    logger.warning(f"Failed to batch ingest runs: {exc_desc}")
                except Exception:
                    logger.warning(f"Failed to batch ingest runs: {repr(e)}")

    def _multipart_ingest_ops(
        self, ops: list[Union[SerializedRunOperation, SerializedFeedbackOperation]]
    ) -> None:
        parts: list[MultipartPartsAndContext] = []
        opened_files_dict: dict[str, io.BufferedReader] = {}
        for op in ops:
            if isinstance(op, SerializedRunOperation):
                (
                    part,
                    opened_files,
                ) = serialized_run_operation_to_multipart_parts_and_context(op)
                parts.append(part)
                opened_files_dict.update(opened_files)
            elif isinstance(op, SerializedFeedbackOperation):
                parts.append(
                    serialized_feedback_operation_to_multipart_parts_and_context(op)
                )
            else:
                logger.error("Unknown operation type in tracing queue: %s", type(op))
        acc_multipart = join_multipart_parts_and_context(parts)
        if acc_multipart:
            try:
                self._send_multipart_req(acc_multipart)
            finally:
                _close_files(list(opened_files_dict.values()))

    def multipart_ingest(
        self,
        create: Optional[
            Sequence[Union[ls_schemas.Run, ls_schemas.RunLikeDict, dict]]
        ] = None,
        update: Optional[
            Sequence[Union[ls_schemas.Run, ls_schemas.RunLikeDict, dict]]
        ] = None,
        *,
        pre_sampled: bool = False,
        dangerously_allow_filesystem: bool = False,
    ) -> None:
        """Batch ingest/upsert multiple runs in the Langsmith system.

        Args:
            create (Optional[Sequence[Union[ls_schemas.Run, RunLikeDict]]]):
                A sequence of `Run` objects or equivalent dictionaries representing
                runs to be created / posted.
            update (Optional[Sequence[Union[ls_schemas.Run, RunLikeDict]]]):
                A sequence of `Run` objects or equivalent dictionaries representing
                runs that have already been created and should be updated / patched.
            pre_sampled (bool, default=False): Whether the runs have already been subject
                to sampling, and therefore should not be sampled again.
                Defaults to False.

        Raises:
            LangsmithAPIError: If there is an error in the API request.

        Returns:
            None

        Note:
            - The run objects MUST contain the dotted_order and trace_id fields
                to be accepted by the API.

        Examples:

            .. code-block:: python

                from langsmith import Client
                import datetime
                from uuid import uuid4

                client = Client()
                _session = "__test_batch_ingest_runs"
                trace_id = uuid4()
                trace_id_2 = uuid4()
                run_id_2 = uuid4()
                current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y%m%dT%H%M%S%fZ"
                )
                later_time = (
                    datetime.datetime.now(datetime.timezone.utc) + timedelta(seconds=1)
                ).strftime("%Y%m%dT%H%M%S%fZ")

                runs_to_create = [
                    {
                        "id": str(trace_id),
                        "session_name": _session,
                        "name": "run 1",
                        "run_type": "chain",
                        "dotted_order": f"{current_time}{str(trace_id)}",
                        "trace_id": str(trace_id),
                        "inputs": {"input1": 1, "input2": 2},
                        "outputs": {"output1": 3, "output2": 4},
                    },
                    {
                        "id": str(trace_id_2),
                        "session_name": _session,
                        "name": "run 3",
                        "run_type": "chain",
                        "dotted_order": f"{current_time}{str(trace_id_2)}",
                        "trace_id": str(trace_id_2),
                        "inputs": {"input1": 1, "input2": 2},
                        "error": "error",
                    },
                    {
                        "id": str(run_id_2),
                        "session_name": _session,
                        "name": "run 2",
                        "run_type": "chain",
                        "dotted_order": f"{current_time}{str(trace_id)}."
                        f"{later_time}{str(run_id_2)}",
                        "trace_id": str(trace_id),
                        "parent_run_id": str(trace_id),
                        "inputs": {"input1": 5, "input2": 6},
                    },
                ]
                runs_to_update = [
                    {
                        "id": str(run_id_2),
                        "dotted_order": f"{current_time}{str(trace_id)}."
                        f"{later_time}{str(run_id_2)}",
                        "trace_id": str(trace_id),
                        "parent_run_id": str(trace_id),
                        "outputs": {"output1": 4, "output2": 5},
                    },
                ]

                client.multipart_ingest(create=runs_to_create, update=runs_to_update)
        """
        if not (create or update):
            return
        # transform and convert to dicts
        create_dicts = [self._run_transform(run) for run in create or EMPTY_SEQ]
        update_dicts = [
            self._run_transform(run, update=True) for run in update or EMPTY_SEQ
        ]
        # require trace_id and dotted_order
        if create_dicts:
            for run in create_dicts:
                if not run.get("trace_id") or not run.get("dotted_order"):
                    raise ls_utils.LangSmithUserError(
                        "Multipart ingest requires trace_id and dotted_order"
                        " to be set in create dicts."
                    )
            else:
                del run
        if update_dicts:
            for run in update_dicts:
                if not run.get("trace_id") or not run.get("dotted_order"):
                    raise ls_utils.LangSmithUserError(
                        "Multipart ingest requires trace_id and dotted_order"
                        " to be set in update dicts."
                    )
            else:
                del run
        # combine post and patch dicts where possible
        if update_dicts and create_dicts:
            create_by_id = {run["id"]: run for run in create_dicts}
            standalone_updates: list[dict] = []
            for run in update_dicts:
                if run["id"] in create_by_id:
                    for k, v in run.items():
                        if v is not None:
                            create_by_id[run["id"]][k] = v
                else:
                    standalone_updates.append(run)
            else:
                del run
            update_dicts = standalone_updates
        # filter out runs that are not sampled
        if not pre_sampled:
            create_dicts = self._filter_for_sampling(create_dicts)
            update_dicts = self._filter_for_sampling(update_dicts, patch=True)
        if not create_dicts and not update_dicts:
            return
        # insert runtime environment
        self._insert_runtime_env(create_dicts)
        self._insert_runtime_env(update_dicts)

        # format as serialized operations
        serialized_ops = combine_serialized_queue_operations(
            list(
                itertools.chain(
                    (serialize_run_dict("post", run) for run in create_dicts),
                    (serialize_run_dict("patch", run) for run in update_dicts),
                )
            )
        )

        for op in serialized_ops:
            if isinstance(op, SerializedRunOperation) and op.attachments:
                for attachment in op.attachments.values():
                    if (
                        isinstance(attachment, tuple)
                        and isinstance(attachment[1], Path)
                        and not dangerously_allow_filesystem
                    ):
                        raise ValueError(
                            "Must set dangerously_allow_filesystem=True to allow passing in Paths for attachments."
                        )

        # sent the runs in multipart requests
        self._multipart_ingest_ops(serialized_ops)

    def _send_multipart_req(self, acc: MultipartPartsAndContext, *, attempts: int = 3):
        parts = acc.parts
        _context = acc.context
        for api_url, api_key in self._write_api_urls.items():
            for idx in range(1, attempts + 1):
                try:
                    encoder = rqtb_multipart.MultipartEncoder(parts, boundary=_BOUNDARY)
                    if encoder.len <= 20_000_000:  # ~20 MB
                        data = encoder.to_string()
                    else:
                        data = encoder
                    logger.debug(f"Sending multipart request with context: {_context}")
                    self.request_with_retries(
                        "POST",
                        f"{api_url}/runs/multipart",
                        request_kwargs={
                            "data": data,
                            "headers": {
                                **self._headers,
                                X_API_KEY: api_key,
                                "Content-Type": encoder.content_type,
                            },
                        },
                        stop_after_attempt=1,
                        _context=_context,
                    )
                    break
                except ls_utils.LangSmithConflictError:
                    break
                except (
                    ls_utils.LangSmithConnectionError,
                    ls_utils.LangSmithRequestTimeout,
                    ls_utils.LangSmithAPIError,
                ) as exc:
                    if idx == attempts:
                        logger.warning(f"Failed to multipart ingest runs: {exc}")
                    else:
                        continue
                except Exception as e:
                    try:
                        exc_desc_lines = traceback.format_exception_only(type(e), e)
                        exc_desc = "".join(exc_desc_lines).rstrip()
                        logger.warning(f"Failed to multipart ingest runs: {exc_desc}")
                    except Exception:
                        logger.warning(f"Failed to multipart ingest runs: {repr(e)}")
                    # do not retry by default
                    break

    def _send_compressed_multipart_req(
        self,
        data_stream: io.BytesIO,
        compressed_traces_info: Optional[tuple[int, int]],
        *,
        attempts: int = 3,
    ):
        """Send a zstd-compressed multipart form data stream to the backend."""
        _context: str = "; ".join(getattr(data_stream, "context", []))

        for api_url, api_key in self._write_api_urls.items():
            data_stream.seek(0)

            for idx in range(1, attempts + 1):
                try:
                    headers = {
                        **self._headers,
                        "X-API-KEY": api_key,
                        "Content-Type": f"multipart/form-data; boundary={_BOUNDARY}",
                        "Content-Encoding": "zstd",
                        "X-Pre-Compressed-Size": (
                            str(compressed_traces_info[0])
                            if compressed_traces_info
                            else ""
                        ),
                        "X-Post-Compressed-Size": (
                            str(compressed_traces_info[1])
                            if compressed_traces_info
                            else ""
                        ),
                    }
                    logger.debug(
                        f"Sending compressed multipart request with context: {_context}"
                    )
                    self.request_with_retries(
                        "POST",
                        f"{api_url}/runs/multipart",
                        request_kwargs={
                            "data": data_stream,
                            "headers": headers,
                        },
                        stop_after_attempt=1,
                        _context=_context,
                    )
                    break
                except ls_utils.LangSmithConflictError:
                    break
                except (
                    ls_utils.LangSmithConnectionError,
                    ls_utils.LangSmithRequestTimeout,
                    ls_utils.LangSmithAPIError,
                ) as exc:
                    if idx == attempts:
                        logger.warning(
                            f"Failed to send compressed multipart ingest: {exc}"
                        )
                    else:
                        continue
                except Exception as e:
                    try:
                        exc_desc_lines = traceback.format_exception_only(type(e), e)
                        exc_desc = "".join(exc_desc_lines).rstrip()
                        logger.warning(
                            f"Failed to send compressed multipart ingest: {exc_desc}"
                        )
                    except Exception:
                        logger.warning(
                            f"Failed to send compressed multipart ingest: {repr(e)}"
                        )
                    # Do not retry by default after unknown exceptions
                    break

    def update_run(
        self,
        run_id: ID_TYPE,
        *,
        name: Optional[str] = None,
        end_time: Optional[datetime.datetime] = None,
        error: Optional[str] = None,
        inputs: Optional[dict] = None,
        outputs: Optional[dict] = None,
        events: Optional[Sequence[dict]] = None,
        extra: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        attachments: Optional[ls_schemas.Attachments] = None,
        dangerously_allow_filesystem: bool = False,
        reference_example_id: str | uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Update a run in the LangSmith API.

        Args:
            run_id (Union[UUID, str]): The ID of the run to update.
            name (Optional[str]): The name of the run.
            end_time (Optional[datetime.datetime]): The end time of the run.
            error (Optional[str]): The error message of the run.
            inputs (Optional[Dict]): The input values for the run.
            outputs (Optional[Dict]): The output values for the run.
            events (Optional[Sequence[dict]]): The events for the run.
            extra (Optional[Dict]): The extra information for the run.
            tags (Optional[List[str]]): The tags for the run.
            attachments (Optional[Dict[str, Attachment]]): A dictionary of attachments to add to the run. The keys are the attachment names,
                and the values are Attachment objects containing the data and mime type.
            reference_example_id (Optional[Union[str, uuid.UUID]]): ID of the example
                that was the source of the run inputs. Used for runs that were part of
                an experiment.
            **kwargs (Any): Kwargs are ignored.

        Returns:
            None

        Examples:

            .. code-block:: python

                from langsmith import Client
                import datetime
                from uuid import uuid4

                client = Client()
                project_name = "__test_update_run"

                start_time = datetime.datetime.now()
                revision_id = uuid4()
                run: dict = dict(
                    id=uuid4(),
                    name="test_run",
                    run_type="llm",
                    inputs={"text": "hello world"},
                    project_name=project_name,
                    api_url=os.getenv("LANGCHAIN_ENDPOINT"),
                    start_time=start_time,
                    extra={"extra": "extra"},
                    revision_id=revision_id,
                )
                # Create the run
                client.create_run(**run)
                run["outputs"] = {"output": ["Hi"]}
                run["extra"]["foo"] = "bar"
                run["name"] = "test_run_updated"
                # Update the run
                client.update_run(run["id"], **run)
        """
        data: dict[str, Any] = {
            "id": _as_uuid(run_id, "run_id"),
            "name": name,
            "trace_id": kwargs.pop("trace_id", None),
            "parent_run_id": kwargs.pop("parent_run_id", None),
            "dotted_order": kwargs.pop("dotted_order", None),
            "tags": tags,
            "extra": extra,
            "session_id": kwargs.pop("session_id", None),
            "session_name": kwargs.pop("session_name", None),
        }
        if attachments:
            for _, attachment in attachments.items():
                if (
                    isinstance(attachment, tuple)
                    and isinstance(attachment[1], Path)
                    and not dangerously_allow_filesystem
                ):
                    raise ValueError(
                        "Must set dangerously_allow_filesystem=True to allow passing in Paths for attachments."
                    )
            data["attachments"] = attachments
        use_multipart = (
            (self.tracing_queue is not None or self.compressed_traces is not None)
            # batch ingest requires trace_id and dotted_order to be set
            and data["trace_id"] is not None
            and data["dotted_order"] is not None
        )
        if not self._filter_for_sampling([data], patch=True):
            return
        if end_time is not None:
            data["end_time"] = end_time.isoformat()
        else:
            data["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if error is not None:
            data["error"] = error
        if inputs is not None:
            data["inputs"] = self._hide_run_inputs(inputs)
        if outputs is not None:
            if not use_multipart:
                outputs = ls_utils.deepish_copy(outputs)
            data["outputs"] = self._hide_run_outputs(outputs)
        if events is not None:
            data["events"] = events
        if data["extra"]:
            self._insert_runtime_env([data])
            if metadata := data["extra"].get("metadata"):
                data["extra"]["metadata"] = self._hide_run_metadata(metadata)
        if reference_example_id is not None:
            data["reference_example_id"] = reference_example_id

        if self._pyo3_client is not None:
            self._pyo3_client.update_run(data)
        elif use_multipart:
            serialized_op = serialize_run_dict(operation="patch", payload=data)
            if self.compressed_traces is not None:
                (
                    multipart_form,
                    opened_files,
                ) = serialized_run_operation_to_multipart_parts_and_context(
                    serialized_op
                )
                logger.log(
                    5,
                    "Adding compressed multipart to queue with context: %s",
                    multipart_form.context,
                )
                with self.compressed_traces.lock:
                    if self._data_available_event is None:
                        raise ValueError(
                            "Run compression is enabled but threading event is not configured"
                        )
                    compress_multipart_parts_and_context(
                        multipart_form,
                        self.compressed_traces,
                        _BOUNDARY,
                    )
                    self.compressed_traces.trace_count += 1
                    self._data_available_event.set()
                _close_files(list(opened_files.values()))
            elif self.tracing_queue is not None:
                logger.log(
                    5,
                    "Adding to tracing queue: trace_id=%s, run_id=%s",
                    serialized_op.trace_id,
                    serialized_op.id,
                )
                if HAS_OTEL:
                    self.tracing_queue.put(
                        TracingQueueItem(
                            data["dotted_order"],
                            serialized_op,
                            otel_context=set_span_in_context(
                                otel_trace.get_current_span()
                            ),
                        )
                    )
                else:
                    self.tracing_queue.put(
                        TracingQueueItem(data["dotted_order"], serialized_op)
                    )
        else:
            self._update_run(data)

    def _update_run(self, run_update: dict) -> None:
        for api_url, api_key in self._write_api_urls.items():
            headers = {
                **self._headers,
                X_API_KEY: api_key,
            }

            self.request_with_retries(
                "PATCH",
                f"{api_url}/runs/{run_update['id']}",
                request_kwargs={
                    "data": _dumps_json(run_update),
                    "headers": headers,
                },
            )

    def flush_compressed_traces(self, attempts: int = 3) -> None:
        """Force flush the currently buffered compressed runs."""
        if self.compressed_traces is None:
            return

        if self._futures is None:
            raise ValueError(
                "Run compression is enabled but request pool futures is not set"
            )

        # Attempt to drain and send any remaining data
        from langsmith._internal._background_thread import (
            HTTP_REQUEST_THREAD_POOL,
            _tracing_thread_drain_compressed_buffer,
        )

        (
            final_data_stream,
            compressed_traces_info,
        ) = _tracing_thread_drain_compressed_buffer(
            self, size_limit=1, size_limit_bytes=1
        )

        if final_data_stream is not None:
            # We have data to send
            future = None
            try:
                future = HTTP_REQUEST_THREAD_POOL.submit(
                    self._send_compressed_multipart_req,
                    final_data_stream,
                    compressed_traces_info,
                    attempts=attempts,
                )
                self._futures.add(future)
            except RuntimeError:
                # In case the ThreadPoolExecutor is already shutdown
                self._send_compressed_multipart_req(
                    final_data_stream, compressed_traces_info, attempts=attempts
                )

        # If we got a future, wait for it to complete
        if self._futures:
            futures = list(self._futures)
            done, _ = cf.wait(futures)
            # Remove completed futures
            self._futures.difference_update(done)

    def flush(self) -> None:
        """Flush either queue or compressed buffer, depending on mode."""
        if self.compressed_traces is not None:
            self.flush_compressed_traces()
        elif self.tracing_queue is not None:
            self.tracing_queue.join()

    def _load_child_runs(self, run: ls_schemas.Run) -> ls_schemas.Run:
        """Load child runs for a given run.

        Args:
            run (Run): The run to load child runs for.

        Returns:
            Run: The run with loaded child runs.

        Raises:
            LangSmithError: If a child run has no parent.
        """
        child_runs = self.list_runs(
            is_root=False, session_id=run.session_id, trace_id=run.trace_id
        )
        treemap: collections.defaultdict[uuid.UUID, list[ls_schemas.Run]] = (
            collections.defaultdict(list)
        )
        runs: dict[uuid.UUID, ls_schemas.Run] = {}
        for child_run in sorted(
            child_runs,
            key=lambda r: r.dotted_order,
        ):
            if child_run.parent_run_id is None:
                raise ls_utils.LangSmithError(f"Child run {child_run.id} has no parent")

            # Only track downstream children
            if (
                child_run.dotted_order.startswith(run.dotted_order)
                and child_run.id != run.id
            ):
                treemap[child_run.parent_run_id].append(child_run)
                runs[child_run.id] = child_run
        run.child_runs = treemap.pop(run.id, [])
        for run_id, children in treemap.items():
            runs[run_id].child_runs = children
        return run

    def read_run(
        self, run_id: ID_TYPE, load_child_runs: bool = False
    ) -> ls_schemas.Run:
        """Read a run from the LangSmith API.

        Args:
            run_id (Union[UUID, str]):
                The ID of the run to read.
            load_child_runs (bool, default=False):
                Whether to load nested child runs.

        Returns:
            Run: The run read from the LangSmith API.

        Examples:

            .. code-block:: python

                from langsmith import Client

                # Existing run
                run_id = "your-run-id"

                client = Client()
                stored_run = client.read_run(run_id)
        """
        response = self.request_with_retries(
            "GET", f"/runs/{_as_uuid(run_id, 'run_id')}"
        )
        attachments = _convert_stored_attachments_to_attachments_dict(
            response.json(), attachments_key="s3_urls"
        )
        run = ls_schemas.Run(
            attachments=attachments, **response.json(), _host_url=self._host_url
        )

        if load_child_runs:
            run = self._load_child_runs(run)
        return run

    def list_runs(
        self,
        *,
        project_id: Optional[Union[ID_TYPE, Sequence[ID_TYPE]]] = None,
        project_name: Optional[Union[str, Sequence[str]]] = None,
        run_type: Optional[str] = None,
        trace_id: Optional[ID_TYPE] = None,
        reference_example_id: Optional[ID_TYPE] = None,
        query: Optional[str] = None,
        filter: Optional[str] = None,
        trace_filter: Optional[str] = None,
        tree_filter: Optional[str] = None,
        is_root: Optional[bool] = None,
        parent_run_id: Optional[ID_TYPE] = None,
        start_time: Optional[datetime.datetime] = None,
        error: Optional[bool] = None,
        run_ids: Optional[Sequence[ID_TYPE]] = None,
        select: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[ls_schemas.Run]:
        """List runs from the LangSmith API.

        Args:
            project_id (Optional[Union[UUID, str], Sequence[Union[UUID, str]]]):
                The ID(s) of the project to filter by.
            project_name (Optional[Union[str, Sequence[str]]]): The name(s) of the project to filter by.
            run_type (Optional[str]): The type of the runs to filter by.
            trace_id (Optional[Union[UUID, str]]): The ID of the trace to filter by.
            reference_example_id (Optional[Union[UUID, str]]): The ID of the reference example to filter by.
            query (Optional[str]): The query string to filter by.
            filter (Optional[str]): The filter string to filter by.
            trace_filter (Optional[str]): Filter to apply to the ROOT run in the trace tree. This is meant to
                be used in conjunction with the regular `filter` parameter to let you
                filter runs by attributes of the root run within a trace.
            tree_filter (Optional[str]): Filter to apply to OTHER runs in the trace tree, including
                sibling and child runs. This is meant to be used in conjunction with
                the regular `filter` parameter to let you filter runs by attributes
                of any run within a trace.
            is_root (Optional[bool]): Whether to filter by root runs.
            parent_run_id (Optional[Union[UUID, str]]):
                The ID of the parent run to filter by.
            start_time (Optional[datetime.datetime]):
                The start time to filter by.
            error (Optional[bool]): Whether to filter by error status.
            run_ids (Optional[Sequence[Union[UUID, str]]]):
                The IDs of the runs to filter by.
            select (Optional[Sequence[str]]): The fields to select.
            limit (Optional[int]): The maximum number of runs to return.
            **kwargs (Any): Additional keyword arguments.

        Yields:
            The runs.

        Examples:
            .. code-block:: python

                # List all runs in a project
                project_runs = client.list_runs(project_name="<your_project>")

                # List LLM and Chat runs in the last 24 hours
                todays_llm_runs = client.list_runs(
                    project_name="<your_project>",
                    start_time=datetime.now() - timedelta(days=1),
                    run_type="llm",
                )

                # List root traces in a project
                root_runs = client.list_runs(project_name="<your_project>", is_root=1)

                # List runs without errors
                correct_runs = client.list_runs(project_name="<your_project>", error=False)

                # List runs and only return their inputs/outputs (to speed up the query)
                input_output_runs = client.list_runs(
                    project_name="<your_project>", select=["inputs", "outputs"]
                )

                # List runs by run ID
                run_ids = [
                    "a36092d2-4ad5-4fb4-9c0d-0dba9a2ed836",
                    "9398e6be-964f-4aa4-8ae9-ad78cd4b7074",
                ]
                selected_runs = client.list_runs(id=run_ids)

                # List all "chain" type runs that took more than 10 seconds and had
                # `total_tokens` greater than 5000
                chain_runs = client.list_runs(
                    project_name="<your_project>",
                    filter='and(eq(run_type, "chain"), gt(latency, 10), gt(total_tokens, 5000))',
                )

                # List all runs called "extractor" whose root of the trace was assigned feedback "user_score" score of 1
                good_extractor_runs = client.list_runs(
                    project_name="<your_project>",
                    filter='eq(name, "extractor")',
                    trace_filter='and(eq(feedback_key, "user_score"), eq(feedback_score, 1))',
                )

                # List all runs that started after a specific timestamp and either have "error" not equal to null or a "Correctness" feedback score equal to 0
                complex_runs = client.list_runs(
                    project_name="<your_project>",
                    filter='and(gt(start_time, "2023-07-15T12:34:56Z"), or(neq(error, null), and(eq(feedback_key, "Correctness"), eq(feedback_score, 0.0))))',
                )

                # List all runs where `tags` include "experimental" or "beta" and `latency` is greater than 2 seconds
                tagged_runs = client.list_runs(
                    project_name="<your_project>",
                    filter='and(or(has(tags, "experimental"), has(tags, "beta")), gt(latency, 2))',
                )
        """  # noqa: E501
        project_ids = []
        if isinstance(project_id, (uuid.UUID, str)):
            project_ids.append(project_id)
        elif isinstance(project_id, list):
            project_ids.extend(project_id)
        if project_name is not None:
            if isinstance(project_name, str):
                project_name = [project_name]
            project_ids.extend(
                [self.read_project(project_name=name).id for name in project_name]
            )
        default_select = [
            "app_path",
            "completion_cost",
            "completion_tokens",
            "dotted_order",
            "end_time",
            "error",
            "events",
            "extra",
            "feedback_stats",
            "first_token_time",
            "id",
            "inputs",
            "name",
            "outputs",
            "parent_run_id",
            "parent_run_ids",
            "prompt_cost",
            "prompt_tokens",
            "reference_example_id",
            "run_type",
            "session_id",
            "start_time",
            "status",
            "tags",
            "total_cost",
            "total_tokens",
            "trace_id",
        ]
        select = select or default_select
        body_query: dict[str, Any] = {
            "session": project_ids if project_ids else None,
            "run_type": run_type,
            "reference_example": (
                [reference_example_id] if reference_example_id else None
            ),
            "query": query,
            "filter": filter,
            "trace_filter": trace_filter,
            "tree_filter": tree_filter,
            "is_root": is_root,
            "parent_run": parent_run_id,
            "start_time": start_time.isoformat() if start_time else None,
            "error": error,
            "id": run_ids,
            "trace": trace_id,
            "select": select,
            **kwargs,
        }
        body_query = {k: v for k, v in body_query.items() if v is not None}
        for i, run in enumerate(
            self._get_cursor_paginated_list("/runs/query", body=body_query)
        ):
            # Should this be behind a flag?
            attachments = _convert_stored_attachments_to_attachments_dict(
                run, attachments_key="s3_urls"
            )
            yield ls_schemas.Run(
                attachments=attachments, **run, _host_url=self._host_url
            )
            if limit is not None and i + 1 >= limit:
                break

    def get_run_stats(
        self,
        *,
        id: Optional[list[ID_TYPE]] = None,
        trace: Optional[ID_TYPE] = None,
        parent_run: Optional[ID_TYPE] = None,
        run_type: Optional[str] = None,
        project_names: Optional[list[str]] = None,
        project_ids: Optional[list[ID_TYPE]] = None,
        reference_example_ids: Optional[list[ID_TYPE]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        error: Optional[bool] = None,
        query: Optional[str] = None,
        filter: Optional[str] = None,
        trace_filter: Optional[str] = None,
        tree_filter: Optional[str] = None,
        is_root: Optional[bool] = None,
        data_source_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get aggregate statistics over queried runs.

        Takes in similar query parameters to `list_runs` and returns statistics
        based on the runs that match the query.

        Args:
            id (Optional[List[Union[UUID, str]]]): List of run IDs to filter by.
            trace (Optional[Union[UUID, str]]): Trace ID to filter by.
            parent_run (Optional[Union[UUID, str]]): Parent run ID to filter by.
            run_type (Optional[str]): Run type to filter by.
            project_names (Optional[List[str]]): List of project names to filter by.
            project_ids (Optional[List[Union[UUID, str]]]): List of project IDs to filter by.
            reference_example_ids (Optional[List[Union[UUID, str]]]): List of reference example IDs to filter by.
            start_time (Optional[str]): Start time to filter by.
            end_time (Optional[str]): End time to filter by.
            error (Optional[bool]): Filter by error status.
            query (Optional[str]): Query string to filter by.
            filter (Optional[str]): Filter string to apply.
            trace_filter (Optional[str]): Trace filter string to apply.
            tree_filter (Optional[str]): Tree filter string to apply.
            is_root (Optional[bool]): Filter by root run status.
            data_source_type (Optional[str]): Data source type to filter by.

        Returns:
            Dict[str, Any]: A dictionary containing the run statistics.
        """  # noqa: E501
        from concurrent.futures import ThreadPoolExecutor, as_completed  # type: ignore

        project_ids = project_ids or []
        if project_names:
            with ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(self.read_project, project_name=name)
                    for name in project_names
                ]
                for future in as_completed(futures):
                    project_ids.append(future.result().id)
        payload = {
            "id": id,
            "trace": trace,
            "parent_run": parent_run,
            "run_type": run_type,
            "session": project_ids,
            "reference_example": reference_example_ids,
            "start_time": start_time,
            "end_time": end_time,
            "error": error,
            "query": query,
            "filter": filter,
            "trace_filter": trace_filter,
            "tree_filter": tree_filter,
            "is_root": is_root,
            "data_source_type": data_source_type,
        }

        # Remove None values from the payload
        payload = {k: v for k, v in payload.items() if v is not None}

        response = self.request_with_retries(
            "POST",
            "/runs/stats",
            request_kwargs={
                "data": _dumps_json(payload),
            },
        )
        ls_utils.raise_for_status_with_text(response)
        return response.json()

    def get_run_url(
        self,
        *,
        run: ls_schemas.RunBase,
        project_name: Optional[str] = None,
        project_id: Optional[ID_TYPE] = None,
    ) -> str:
        """Get the URL for a run.

        Not recommended for use within your agent runtime.
        More for use interacting with runs after the fact
        for data analysis or ETL workloads.

        Args:
            run (RunBase): The run.
            project_name (Optional[str]): The name of the project.
            project_id (Optional[Union[UUID, str]]): The ID of the project.

        Returns:
            str: The URL for the run.
        """
        if session_id := getattr(run, "session_id", None):
            pass
        elif session_name := getattr(run, "session_name", None):
            session_id = self.read_project(project_name=session_name).id
        elif project_id is not None:
            session_id = project_id
        elif project_name is not None:
            session_id = self.read_project(project_name=project_name).id
        else:
            project_name = ls_utils.get_tracer_project()
            session_id = self.read_project(project_name=project_name).id
        session_id_ = _as_uuid(session_id, "session_id")
        return (
            f"{self._host_url}/o/{self._get_tenant_id()}/projects/p/{session_id_}/"
            f"r/{run.id}?poll=true"
        )

    def share_run(self, run_id: ID_TYPE, *, share_id: Optional[ID_TYPE] = None) -> str:
        """Get a share link for a run.

        Args:
            run_id (Union[UUID, str]): The ID of the run to share.
            share_id (Optional[Union[UUID, str]]): Custom share ID.
                If not provided, a random UUID will be generated.

        Returns:
            str: The URL of the shared run.
        """
        run_id_ = _as_uuid(run_id, "run_id")
        data = {
            "run_id": str(run_id_),
            "share_token": share_id or str(uuid.uuid4()),
        }
        response = self.request_with_retries(
            "PUT",
            f"/runs/{run_id_}/share",
            headers=self._headers,
            json=data,
        )
        ls_utils.raise_for_status_with_text(response)
        share_token = response.json()["share_token"]
        return f"{self._host_url}/public/{share_token}/r"

    def unshare_run(self, run_id: ID_TYPE) -> None:
        """Delete share link for a run.

        Args:
            run_id (Union[UUID, str]): The ID of the run to unshare.

        Returns:
            None
        """
        response = self.request_with_retries(
            "DELETE",
            f"/runs/{_as_uuid(run_id, 'run_id')}/share",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def read_run_shared_link(self, run_id: ID_TYPE) -> Optional[str]:
        """Retrieve the shared link for a specific run.

        Args:
            run_id (Union[UUID, str]): The ID of the run.

        Returns:
            Optional[str]: The shared link for the run, or None if the link is not
            available.
        """
        response = self.request_with_retries(
            "GET",
            f"/runs/{_as_uuid(run_id, 'run_id')}/share",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)
        result = response.json()
        if result is None or "share_token" not in result:
            return None
        return f"{self._host_url}/public/{result['share_token']}/r"

    def run_is_shared(self, run_id: ID_TYPE) -> bool:
        """Get share state for a run.

        Args:
            run_id (Union[UUID, str]): The ID of the run.

        Returns:
            bool: True if the run is shared, False otherwise.
        """
        link = self.read_run_shared_link(_as_uuid(run_id, "run_id"))
        return link is not None

    def read_shared_run(
        self, share_token: Union[ID_TYPE, str], run_id: Optional[ID_TYPE] = None
    ) -> ls_schemas.Run:
        """Get shared runs.

        Args:
            share_token (Union[UUID, str]): The share token or URL of the shared run.
            run_id (Optional[Union[UUID, str]]): The ID of the specific run to retrieve.
                If not provided, the full shared run will be returned.

        Returns:
            Run: The shared run.
        """
        _, token_uuid = _parse_token_or_url(share_token, "", kind="run")
        path = f"/public/{token_uuid}/run"
        if run_id is not None:
            path += f"/{_as_uuid(run_id, 'run_id')}"
        response = self.request_with_retries(
            "GET",
            path,
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.Run(**response.json(), _host_url=self._host_url)

    def list_shared_runs(
        self, share_token: Union[ID_TYPE, str], run_ids: Optional[list[str]] = None
    ) -> Iterator[ls_schemas.Run]:
        """Get shared runs.

        Args:
            share_token (Union[UUID, str]): The share token or URL of the shared run.
            run_ids (Optional[List[str]]): A list of run IDs to filter the results by.

        Yields:
            A shared run.
        """
        body = {"id": run_ids} if run_ids else {}
        _, token_uuid = _parse_token_or_url(share_token, "", kind="run")
        for run in self._get_cursor_paginated_list(
            f"/public/{token_uuid}/runs/query", body=body
        ):
            yield ls_schemas.Run(**run, _host_url=self._host_url)

    def read_dataset_shared_schema(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        *,
        dataset_name: Optional[str] = None,
    ) -> ls_schemas.DatasetShareSchema:
        """Retrieve the shared schema of a dataset.

        Args:
            dataset_id (Optional[Union[UUID, str]]): The ID of the dataset.
                Either `dataset_id` or `dataset_name` must be given.
            dataset_name (Optional[str]): The name of the dataset.
                Either `dataset_id` or `dataset_name` must be given.

        Returns:
            ls_schemas.DatasetShareSchema: The shared schema of the dataset.

        Raises:
            ValueError: If neither `dataset_id` nor `dataset_name` is given.
        """
        if dataset_id is None and dataset_name is None:
            raise ValueError("Either dataset_id or dataset_name must be given")
        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        response = self.request_with_retries(
            "GET",
            f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}/share",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)
        d = response.json()
        return cast(
            ls_schemas.DatasetShareSchema,
            {
                **d,
                "url": f"{self._host_url}/public/"
                f"{_as_uuid(d['share_token'], 'response.share_token')}/d",
            },
        )

    def share_dataset(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        *,
        dataset_name: Optional[str] = None,
    ) -> ls_schemas.DatasetShareSchema:
        """Get a share link for a dataset.

        Args:
            dataset_id (Optional[Union[UUID, str]]): The ID of the dataset.
                Either `dataset_id` or `dataset_name` must be given.
            dataset_name (Optional[str]): The name of the dataset.
                Either `dataset_id` or `dataset_name` must be given.

        Returns:
            ls_schemas.DatasetShareSchema: The shared schema of the dataset.

        Raises:
            ValueError: If neither `dataset_id` nor `dataset_name` is given.
        """
        if dataset_id is None and dataset_name is None:
            raise ValueError("Either dataset_id or dataset_name must be given")
        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        data = {
            "dataset_id": str(dataset_id),
        }
        response = self.request_with_retries(
            "PUT",
            f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}/share",
            headers=self._headers,
            json=data,
        )
        ls_utils.raise_for_status_with_text(response)
        d: dict = response.json()
        return cast(
            ls_schemas.DatasetShareSchema,
            {**d, "url": f"{self._host_url}/public/{d['share_token']}/d"},
        )

    def unshare_dataset(self, dataset_id: ID_TYPE) -> None:
        """Delete share link for a dataset.

        Args:
            dataset_id (Union[UUID, str]): The ID of the dataset to unshare.

        Returns:
            None
        """
        response = self.request_with_retries(
            "DELETE",
            f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}/share",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def read_shared_dataset(
        self,
        share_token: str,
    ) -> ls_schemas.Dataset:
        """Get shared datasets.

        Args:
            share_token (Union[UUID, str]): The share token or URL of the shared dataset.

        Returns:
            Dataset: The shared dataset.
        """
        _, token_uuid = _parse_token_or_url(share_token, self.api_url)
        response = self.request_with_retries(
            "GET",
            f"/public/{token_uuid}/datasets",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.Dataset(
            **response.json(),
            _host_url=self._host_url,
            _public_path=f"/public/{share_token}/d",
        )

    def list_shared_examples(
        self, share_token: str, *, example_ids: Optional[list[ID_TYPE]] = None
    ) -> list[ls_schemas.Example]:
        """Get shared examples.

        Args:
            share_token (Union[UUID, str]): The share token or URL of the shared dataset.
            example_ids (Optional[List[UUID, str]], optional): The IDs of the examples to filter by. Defaults to None.

        Returns:
            List[ls_schemas.Example]: The list of shared examples.
        """
        params = {}
        if example_ids is not None:
            params["id"] = [str(id) for id in example_ids]
        response = self.request_with_retries(
            "GET",
            f"/public/{_as_uuid(share_token, 'share_token')}/examples",
            headers=self._headers,
            params=params,
        )
        ls_utils.raise_for_status_with_text(response)
        return [
            ls_schemas.Example(**dataset, _host_url=self._host_url)
            for dataset in response.json()
        ]

    def list_shared_projects(
        self,
        *,
        dataset_share_token: str,
        project_ids: Optional[list[ID_TYPE]] = None,
        name: Optional[str] = None,
        name_contains: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[ls_schemas.TracerSessionResult]:
        """List shared projects.

        Args:
            dataset_share_token (str): The share token of the dataset.
            project_ids (Optional[List[Union[UUID, str]]]): List of project IDs to filter the results, by default None.
            name (Optional[str]): Name of the project to filter the results, by default None.
            name_contains (Optional[str]): Substring to search for in project names, by default None.
            limit (Optional[int]): Maximum number of projects to return, by default None.

        Yields:
            The shared projects.
        """
        params = {"id": project_ids, "name": name, "name_contains": name_contains}
        share_token = _as_uuid(dataset_share_token, "dataset_share_token")
        for i, project in enumerate(
            self._get_paginated_list(
                f"/public/{share_token}/datasets/sessions",
                params=params,
            )
        ):
            yield ls_schemas.TracerSessionResult(**project, _host_url=self._host_url)
            if limit is not None and i + 1 >= limit:
                break

    def create_project(
        self,
        project_name: str,
        *,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        upsert: bool = False,
        project_extra: Optional[dict] = None,
        reference_dataset_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.TracerSession:
        """Create a project on the LangSmith API.

        Args:
            project_name (str): The name of the project.
            project_extra (Optional[dict]): Additional project information.
            metadata (Optional[dict]): Additional metadata to associate with the project.
            description (Optional[str]): The description of the project.
            upsert (bool, default=False): Whether to update the project if it already exists.
            reference_dataset_id (Optional[Union[UUID, str]): The ID of the reference dataset to associate with the project.

        Returns:
            TracerSession: The created project.
        """
        endpoint = f"{self.api_url}/sessions"
        extra = project_extra
        if metadata:
            extra = {**(extra or {}), "metadata": metadata}
        body: dict[str, Any] = {
            "name": project_name,
            "extra": extra,
            "description": description,
            "id": str(uuid.uuid4()),
        }
        params = {}
        if upsert:
            params["upsert"] = True
        if reference_dataset_id is not None:
            body["reference_dataset_id"] = reference_dataset_id
        response = self.request_with_retries(
            "POST",
            endpoint,
            headers={**self._headers, "Content-Type": "application/json"},
            data=_dumps_json(body),
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.TracerSession(**response.json(), _host_url=self._host_url)

    def update_project(
        self,
        project_id: ID_TYPE,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        project_extra: Optional[dict] = None,
        end_time: Optional[datetime.datetime] = None,
    ) -> ls_schemas.TracerSession:
        """Update a LangSmith project.

        Args:
            project_id (Union[UUID, str]):
                The ID of the project to update.
            name (Optional[str]):
                The new name to give the project. This is only valid if the project
                has been assigned an end_time, meaning it has been completed/closed.
            description (Optional[str]):
                The new description to give the project.
            metadata (Optional[dict]):
                Additional metadata to associate with the project.
            project_extra (Optional[dict]):
                Additional project information.
            end_time (Optional[datetime.datetime]):
                The time the project was completed.

        Returns:
            TracerSession: The updated project.
        """
        endpoint = f"{self.api_url}/sessions/{_as_uuid(project_id, 'project_id')}"
        extra = project_extra
        if metadata:
            extra = {**(extra or {}), "metadata": metadata}
        body: dict[str, Any] = {
            "name": name,
            "extra": extra,
            "description": description,
            "end_time": end_time.isoformat() if end_time else None,
        }
        response = self.request_with_retries(
            "PATCH",
            endpoint,
            headers={**self._headers, "Content-Type": "application/json"},
            data=_dumps_json(body),
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.TracerSession(**response.json(), _host_url=self._host_url)

    def _get_optional_tenant_id(self) -> Optional[uuid.UUID]:
        if self._tenant_id is not None:
            return self._tenant_id
        try:
            response = self.request_with_retries(
                "GET", "/sessions", params={"limit": 1}
            )
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                tracer_session = ls_schemas.TracerSessionResult(
                    **result[0], _host_url=self._host_url
                )
                self._tenant_id = tracer_session.tenant_id
                return self._tenant_id
        except Exception as e:
            logger.debug(
                "Failed to get tenant ID from LangSmith: %s", repr(e), exc_info=True
            )
        return None

    def _get_tenant_id(self) -> uuid.UUID:
        tenant_id = self._get_optional_tenant_id()
        if tenant_id is None:
            raise ls_utils.LangSmithError("No tenant ID found")
        return tenant_id

    @ls_utils.xor_args(("project_id", "project_name"))
    def read_project(
        self,
        *,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        include_stats: bool = False,
    ) -> ls_schemas.TracerSessionResult:
        """Read a project from the LangSmith API.

        Args:
            project_id (Optional[str]):
                The ID of the project to read.
            project_name (Optional[str]): The name of the project to read.
                Only one of project_id or project_name may be given.
            include_stats (bool, default=False):
                Whether to include a project's aggregate statistics in the response.

        Returns:
            TracerSessionResult: The project.
        """
        path = "/sessions"
        params: dict[str, Any] = {"limit": 1}
        if project_id is not None:
            path += f"/{_as_uuid(project_id, 'project_id')}"
        elif project_name is not None:
            params["name"] = project_name
        else:
            raise ValueError("Must provide project_name or project_id")
        params["include_stats"] = include_stats
        response = self.request_with_retries("GET", path, params=params)
        result = response.json()
        if isinstance(result, list):
            if len(result) == 0:
                raise ls_utils.LangSmithNotFoundError(
                    f"Project {project_name} not found"
                )
            return ls_schemas.TracerSessionResult(**result[0], _host_url=self._host_url)
        return ls_schemas.TracerSessionResult(
            **response.json(), _host_url=self._host_url
        )

    def has_project(
        self, project_name: str, *, project_id: Optional[str] = None
    ) -> bool:
        """Check if a project exists.

        Args:
            project_name (str):
                The name of the project to check for.
            project_id (Optional[str]):
                The ID of the project to check for.

        Returns:
            bool: Whether the project exists.
        """
        try:
            self.read_project(project_name=project_name)
        except ls_utils.LangSmithNotFoundError:
            return False
        return True

    def get_test_results(
        self,
        *,
        project_id: Optional[ID_TYPE] = None,
        project_name: Optional[str] = None,
    ) -> pd.DataFrame:
        """Read the record-level information from an experiment into a Pandas DF.

        Note: this will fetch whatever data exists in the DB. Results are not
        immediately available in the DB upon evaluation run completion.

        Feedback score values will be returned as an average across all runs for
        the experiment. Note that non-numeric feedback scores will be omitted.

        Args:
            project_id (Optional[Union[UUID, str]]): The ID of the project.
            project_name (Optional[str]): The name of the project.

        Returns:
            pd.DataFrame: A dataframe containing the test results.
        """
        warnings.warn(
            "Function get_test_results is in beta.", UserWarning, stacklevel=2
        )
        from concurrent.futures import ThreadPoolExecutor, as_completed  # type: ignore

        import pandas as pd  # type: ignore

        runs = self.list_runs(
            project_id=project_id,
            project_name=project_name,
            is_root=True,
            select=[
                "id",
                "reference_example_id",
                "inputs",
                "outputs",
                "error",
                "feedback_stats",
                "start_time",
                "end_time",
            ],
        )
        results: list[dict] = []
        example_ids = []

        def fetch_examples(batch):
            examples = self.list_examples(example_ids=batch)
            return [
                {
                    "example_id": example.id,
                    **{f"reference.{k}": v for k, v in (example.outputs or {}).items()},
                }
                for example in examples
            ]

        batch_size = 50
        cursor = 0
        with ThreadPoolExecutor() as executor:
            futures = []
            for r in runs:
                row = {
                    "example_id": r.reference_example_id,
                    **{f"input.{k}": v for k, v in r.inputs.items()},
                    **{f"outputs.{k}": v for k, v in (r.outputs or {}).items()},
                    "execution_time": (
                        (r.end_time - r.start_time).total_seconds()
                        if r.end_time
                        else None
                    ),
                    "error": r.error,
                    "id": r.id,
                }
                if r.feedback_stats:
                    row.update(
                        {
                            f"feedback.{k}": v.get("avg")
                            for k, v in r.feedback_stats.items()
                        }
                    )
                if r.reference_example_id:
                    example_ids.append(r.reference_example_id)
                else:
                    logger.warning(f"Run {r.id} has no reference example ID.")
                if len(example_ids) % batch_size == 0:
                    # Ensure not empty
                    if batch := example_ids[cursor : cursor + batch_size]:
                        futures.append(executor.submit(fetch_examples, batch))
                        cursor += batch_size
                results.append(row)

            # Handle any remaining examples
            if example_ids[cursor:]:
                futures.append(executor.submit(fetch_examples, example_ids[cursor:]))
        result_df = pd.DataFrame(results).set_index("example_id")
        example_outputs = [
            output for future in as_completed(futures) for output in future.result()
        ]
        if example_outputs:
            example_df = pd.DataFrame(example_outputs).set_index("example_id")
            result_df = example_df.merge(result_df, left_index=True, right_index=True)

        # Flatten dict columns into dot syntax for easier access
        return pd.json_normalize(result_df.to_dict(orient="records"))

    def list_projects(
        self,
        project_ids: Optional[list[ID_TYPE]] = None,
        name: Optional[str] = None,
        name_contains: Optional[str] = None,
        reference_dataset_id: Optional[ID_TYPE] = None,
        reference_dataset_name: Optional[str] = None,
        reference_free: Optional[bool] = None,
        limit: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Iterator[ls_schemas.TracerSession]:
        """List projects from the LangSmith API.

        Args:
            project_ids (Optional[List[Union[UUID, str]]]):
                A list of project IDs to filter by, by default None
            name (Optional[str]):
                The name of the project to filter by, by default None
            name_contains (Optional[str]):
                A string to search for in the project name, by default None
            reference_dataset_id (Optional[List[Union[UUID, str]]]):
                A dataset ID to filter by, by default None
            reference_dataset_name (Optional[str]):
                The name of the reference dataset to filter by, by default None
            reference_free (Optional[bool]):
                Whether to filter for only projects not associated with a dataset.
            limit (Optional[int]):
                The maximum number of projects to return, by default None
            metadata (Optional[Dict[str, Any]]):
                Metadata to filter by.

        Yields:
            The projects.

        Raises:
            ValueError: If both reference_dataset_id and reference_dataset_name are given.
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100) if limit is not None else 100
        }
        if project_ids is not None:
            params["id"] = project_ids
        if name is not None:
            params["name"] = name
        if name_contains is not None:
            params["name_contains"] = name_contains
        if reference_dataset_id is not None:
            if reference_dataset_name is not None:
                raise ValueError(
                    "Only one of reference_dataset_id or"
                    " reference_dataset_name may be given"
                )
            params["reference_dataset"] = reference_dataset_id
        elif reference_dataset_name is not None:
            reference_dataset_id = self.read_dataset(
                dataset_name=reference_dataset_name
            ).id
            params["reference_dataset"] = reference_dataset_id
        if reference_free is not None:
            params["reference_free"] = reference_free
        if metadata is not None:
            params["metadata"] = json.dumps(metadata)
        for i, project in enumerate(
            self._get_paginated_list("/sessions", params=params)
        ):
            yield ls_schemas.TracerSession(**project, _host_url=self._host_url)
            if limit is not None and i + 1 >= limit:
                break

    @ls_utils.xor_args(("project_name", "project_id"))
    def delete_project(
        self, *, project_name: Optional[str] = None, project_id: Optional[str] = None
    ) -> None:
        """Delete a project from LangSmith.

        Args:
            project_name (Optional[str]):
                The name of the project to delete.
            project_id (Optional[str]):
                The ID of the project to delete.

        Returns:
            None

        Raises:
            ValueError: If neither project_name or project_id is provided.
        """
        if project_name is not None:
            project_id = str(self.read_project(project_name=project_name).id)
        elif project_id is None:
            raise ValueError("Must provide project_name or project_id")
        response = self.request_with_retries(
            "DELETE",
            f"/sessions/{_as_uuid(project_id, 'project_id')}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def create_dataset(
        self,
        dataset_name: str,
        *,
        description: Optional[str] = None,
        data_type: ls_schemas.DataType = ls_schemas.DataType.kv,
        inputs_schema: Optional[dict[str, Any]] = None,
        outputs_schema: Optional[dict[str, Any]] = None,
        transformations: Optional[list[ls_schemas.DatasetTransformation]] = None,
        metadata: Optional[dict] = None,
    ) -> ls_schemas.Dataset:
        """Create a dataset in the LangSmith API.

        Args:
            dataset_name (str):
                The name of the dataset.
            description (Optional[str]):
                The description of the dataset.
            data_type (DataType, default=DataType.kv):
                The data type of the dataset.
            inputs_schema (Optional[Dict[str, Any]]):
                The schema definition for the inputs of the dataset.
            outputs_schema (Optional[Dict[str, Any]]):
                The schema definition for the outputs of the dataset.
            transformations (Optional[List[DatasetTransformation]]):
                A list of transformations to apply to the dataset.
            metadata (Optional[dict]):
                Additional metadata to associate with the dataset.

        Returns:
            Dataset: The created dataset.

        Raises:
            requests.HTTPError: If the request to create the dataset fails.
        """
        dataset: dict[str, Any] = {
            "name": dataset_name,
            "data_type": data_type.value,
            "transformations": transformations,
            "extra": {"metadata": metadata} if metadata else None,
        }
        if description is not None:
            dataset["description"] = description

        if inputs_schema is not None:
            dataset["inputs_schema_definition"] = inputs_schema

        if outputs_schema is not None:
            dataset["outputs_schema_definition"] = outputs_schema

        response = self.request_with_retries(
            "POST",
            "/datasets",
            headers={**self._headers, "Content-Type": "application/json"},
            data=_orjson.dumps(dataset),
        )
        ls_utils.raise_for_status_with_text(response)

        return ls_schemas.Dataset(
            **response.json(),
            _host_url=self._host_url,
            _tenant_id=self._get_optional_tenant_id(),
        )

    def has_dataset(
        self,
        *,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> bool:
        """Check whether a dataset exists in your tenant.

        Args:
            dataset_name (Optional[str]):
                The name of the dataset to check.
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset to check.

        Returns:
            bool: Whether the dataset exists.
        """
        try:
            self.read_dataset(dataset_name=dataset_name, dataset_id=dataset_id)
            return True
        except ls_utils.LangSmithNotFoundError:
            return False

    @ls_utils.xor_args(("dataset_name", "dataset_id"))
    def read_dataset(
        self,
        *,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.Dataset:
        """Read a dataset from the LangSmith API.

        Args:
            dataset_name (Optional[str]):
                The name of the dataset to read.
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset to read.

        Returns:
            Dataset: The dataset.
        """
        path = "/datasets"
        params: dict[str, Any] = {"limit": 1}
        if dataset_id is not None:
            path += f"/{_as_uuid(dataset_id, 'dataset_id')}"
        elif dataset_name is not None:
            params["name"] = dataset_name
        else:
            raise ValueError("Must provide dataset_name or dataset_id")
        response = self.request_with_retries(
            "GET",
            path,
            params=params,
        )
        result = response.json()
        if isinstance(result, list):
            if len(result) == 0:
                raise ls_utils.LangSmithNotFoundError(
                    f"Dataset {dataset_name} not found"
                )
            return ls_schemas.Dataset(
                **result[0],
                _host_url=self._host_url,
                _tenant_id=self._get_optional_tenant_id(),
            )
        return ls_schemas.Dataset(
            **result,
            _host_url=self._host_url,
            _tenant_id=self._get_optional_tenant_id(),
        )

    def diff_dataset_versions(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        *,
        dataset_name: Optional[str] = None,
        from_version: Union[str, datetime.datetime],
        to_version: Union[str, datetime.datetime],
    ) -> ls_schemas.DatasetDiffInfo:
        """Get the difference between two versions of a dataset.

        Args:
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset.
            dataset_name (Optional[str]):
                The name of the dataset.
            from_version (Union[str, datetime.datetime]):
                The starting version for the diff.
            to_version (Union[str, datetime.datetime]):
                The ending version for the diff.

        Returns:
            DatasetDiffInfo: The difference between the two versions of the dataset.

        Examples:
            .. code-block:: python

                # Get the difference between two tagged versions of a dataset
                from_version = "prod"
                to_version = "dev"
                diff = client.diff_dataset_versions(
                    dataset_name="my-dataset",
                    from_version=from_version,
                    to_version=to_version,
                )

                # Get the difference between two timestamped versions of a dataset
                from_version = datetime.datetime(2024, 1, 1)
                to_version = datetime.datetime(2024, 2, 1)
                diff = client.diff_dataset_versions(
                    dataset_name="my-dataset",
                    from_version=from_version,
                    to_version=to_version,
                )
        """
        if dataset_id is None:
            if dataset_name is None:
                raise ValueError("Must provide either dataset name or ID")
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        dsid = _as_uuid(dataset_id, "dataset_id")
        response = self.request_with_retries(
            "GET",
            f"/datasets/{dsid}/versions/diff",
            headers=self._headers,
            params={
                "from_version": (
                    from_version.isoformat()
                    if isinstance(from_version, datetime.datetime)
                    else from_version
                ),
                "to_version": (
                    to_version.isoformat()
                    if isinstance(to_version, datetime.datetime)
                    else to_version
                ),
            },
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.DatasetDiffInfo(**response.json())

    def read_dataset_openai_finetuning(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        *,
        dataset_name: Optional[str] = None,
    ) -> list:
        """Download a dataset in OpenAI Jsonl format and load it as a list of dicts.

        Args:
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset to download.
            dataset_name (Optional[str]):
                The name of the dataset to download.

        Returns:
            list[dict]: The dataset loaded as a list of dicts.

        Raises:
            ValueError: If neither dataset_id nor dataset_name is provided.
        """
        path = "/datasets"
        if dataset_id is not None:
            pass
        elif dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        else:
            raise ValueError("Must provide dataset_name or dataset_id")
        response = self.request_with_retries(
            "GET",
            f"{path}/{_as_uuid(dataset_id, 'dataset_id')}/openai_ft",
        )
        dataset = [json.loads(line) for line in response.text.strip().split("\n")]
        return dataset

    def list_datasets(
        self,
        *,
        dataset_ids: Optional[list[ID_TYPE]] = None,
        data_type: Optional[str] = None,
        dataset_name: Optional[str] = None,
        dataset_name_contains: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterator[ls_schemas.Dataset]:
        """List the datasets on the LangSmith API.

        Args:
            dataset_ids (Optional[List[Union[UUID, str]]]):
                A list of dataset IDs to filter the results by.
            data_type (Optional[str]):
                The data type of the datasets to filter the results by.
            dataset_name (Optional[str]):
                The name of the dataset to filter the results by.
            dataset_name_contains (Optional[str]):
                A substring to search for in the dataset names.
            metadata (Optional[Dict[str, Any]]):
                A dictionary of metadata to filter the results by.
            limit (Optional[int]):
                The maximum number of datasets to return.

        Yields:
            The datasets.
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100) if limit is not None else 100
        }
        if dataset_ids is not None:
            params["id"] = dataset_ids
        if data_type is not None:
            params["data_type"] = data_type
        if dataset_name is not None:
            params["name"] = dataset_name
        if dataset_name_contains is not None:
            params["name_contains"] = dataset_name_contains
        if metadata is not None:
            params["metadata"] = json.dumps(metadata)
        for i, dataset in enumerate(
            self._get_paginated_list("/datasets", params=params)
        ):
            yield ls_schemas.Dataset(
                **dataset,
                _host_url=self._host_url,
                _tenant_id=self._get_optional_tenant_id(),
            )
            if limit is not None and i + 1 >= limit:
                break

    @ls_utils.xor_args(("dataset_id", "dataset_name"))
    def delete_dataset(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
    ) -> None:
        """Delete a dataset from the LangSmith API.

        Args:
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset to delete.
            dataset_name (Optional[str]):
                The name of the dataset to delete.

        Returns:
            None
        """
        if dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        if dataset_id is None:
            raise ValueError("Must provide either dataset name or ID")
        response = self.request_with_retries(
            "DELETE",
            f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def update_dataset_tag(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        as_of: datetime.datetime,
        tag: str,
    ) -> None:
        """Update the tags of a dataset.

        If the tag is already assigned to a different version of this dataset,
        the tag will be moved to the new version. The as_of parameter is used to
        determine which version of the dataset to apply the new tags to.
        It must be an exact version of the dataset to succeed. You can
        use the read_dataset_version method to find the exact version
        to apply the tags to.

        Args:
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset to update.
            dataset_name (Optional[str]):
                The name of the dataset to update.
            as_of (datetime.datetime):
                The timestamp of the dataset to apply the new tags to.
            tag (str):
                The new tag to apply to the dataset.

        Returns:
            None

        Examples:
            .. code-block:: python

                dataset_name = "my-dataset"
                # Get the version of a dataset <= a given timestamp
                dataset_version = client.read_dataset_version(
                    dataset_name=dataset_name, as_of=datetime.datetime(2024, 1, 1)
                )
                # Assign that version a new tag
                client.update_dataset_tags(
                    dataset_name="my-dataset",
                    as_of=dataset_version.as_of,
                    tag="prod",
                )
        """
        if dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        if dataset_id is None:
            raise ValueError("Must provide either dataset name or ID")
        response = self.request_with_retries(
            "PUT",
            f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}/tags",
            headers=self._headers,
            json={
                "as_of": as_of.isoformat(),
                "tag": tag,
            },
        )
        ls_utils.raise_for_status_with_text(response)

    def list_dataset_versions(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[ls_schemas.DatasetVersion]:
        """List dataset versions.

        Args:
            dataset_id (Optional[Union[UUID, str]]): The ID of the dataset.
            dataset_name (Optional[str]): The name of the dataset.
            search (Optional[str]): The search query.
            limit (Optional[int]): The maximum number of versions to return.

        Yields:
            The dataset versions.
        """
        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        params = {
            "search": search,
            "limit": min(limit, 100) if limit is not None else 100,
        }
        for i, version in enumerate(
            self._get_paginated_list(
                f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}/versions",
                params=params,
            )
        ):
            yield ls_schemas.DatasetVersion(**version)
            if limit is not None and i + 1 >= limit:
                break

    def read_dataset_version(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        as_of: Optional[datetime.datetime] = None,
        tag: Optional[str] = None,
    ) -> ls_schemas.DatasetVersion:
        """Get dataset version by as_of or exact tag.

        Ues this to resolve the nearest version to a given timestamp or for a given tag.

        Args:
            dataset_id (Optional[ID_TYPE]): The ID of the dataset.
            dataset_name (Optional[str]): The name of the dataset.
            as_of (Optional[datetime.datetime]): The timestamp of the dataset
                to retrieve.
            tag (Optional[str]): The tag of the dataset to retrieve.

        Returns:
            DatasetVersion: The dataset version.

        Examples:
            .. code-block:: python

                # Get the latest version of a dataset
                client.read_dataset_version(dataset_name="my-dataset", tag="latest")

                # Get the version of a dataset <= a given timestamp
                client.read_dataset_version(
                    dataset_name="my-dataset",
                    as_of=datetime.datetime(2024, 1, 1),
                )


                # Get the version of a dataset with a specific tag
                client.read_dataset_version(dataset_name="my-dataset", tag="prod")
        """
        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        if (as_of and tag) or (as_of is None and tag is None):
            raise ValueError("Exactly one of as_of and tag must be specified.")
        response = self.request_with_retries(
            "GET",
            f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}/version",
            params={"as_of": as_of, "tag": tag},
        )
        return ls_schemas.DatasetVersion(**response.json())

    def clone_public_dataset(
        self,
        token_or_url: str,
        *,
        source_api_url: Optional[str] = None,
        dataset_name: Optional[str] = None,
    ) -> ls_schemas.Dataset:
        """Clone a public dataset to your own langsmith tenant.

        This operation is idempotent. If you already have a dataset with the given name,
        this function will do nothing.

        Args:
            token_or_url (str): The token of the public dataset to clone.
            source_api_url (Optional[str]): The URL of the langsmith server where the data is hosted.
                Defaults to the API URL of your current client.
            dataset_name (Optional[str]): The name of the dataset to create in your tenant.
                Defaults to the name of the public dataset.

        Returns:
            Dataset: The cloned dataset.
        """
        source_api_url = source_api_url or self.api_url
        source_api_url, token_uuid = _parse_token_or_url(token_or_url, source_api_url)
        source_client = Client(
            # Placeholder API key not needed anymore in most cases, but
            # some private deployments may have API key-based rate limiting
            # that would cause this to fail if we provide no value.
            api_url=source_api_url,
            api_key="placeholder",
        )
        ds = source_client.read_shared_dataset(token_uuid)
        dataset_name = dataset_name or ds.name
        try:
            ds = self.read_dataset(dataset_name=dataset_name)
            logger.info(
                f"Dataset {dataset_name} already exists in your tenant. Skipping."
            )
            return ds
        except ls_utils.LangSmithNotFoundError:
            pass

        try:
            # Fetch examples first
            examples = list(source_client.list_shared_examples(token_uuid))
            dataset = self.create_dataset(
                dataset_name=dataset_name,
                description=ds.description,
                data_type=ds.data_type or ls_schemas.DataType.kv,
                inputs_schema=ds.inputs_schema,
                outputs_schema=ds.outputs_schema,
                transformations=ds.transformations,
            )
            try:
                self.create_examples(
                    inputs=[e.inputs for e in examples],
                    outputs=[e.outputs for e in examples],
                    dataset_id=dataset.id,
                )
            except BaseException as e:
                # Let's not do automatic clean up for now in case there might be
                # some other reasons why create_examples fails (i.e., not network issue
                # or keyboard interrupt).
                # The risk is that this is an existing dataset that has valid examples
                # populated from another source so we don't want to delete it.
                logger.error(
                    f"An error occurred while creating dataset {dataset_name}. "
                    "You should delete it manually."
                )
                raise e
        finally:
            del source_client
        return dataset

    def _get_data_type(self, dataset_id: ID_TYPE) -> ls_schemas.DataType:
        dataset = self.read_dataset(dataset_id=dataset_id)
        return dataset.data_type

    @ls_utils.xor_args(("dataset_id", "dataset_name"))
    def create_llm_example(
        self,
        prompt: str,
        generation: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
    ) -> ls_schemas.Example:
        """Add an example (row) to an LLM-type dataset.

        Args:
            prompt (str):
                The input prompt for the example.
            generation (Optional[str]):
                The output generation for the example.
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset.
            dataset_name (Optional[str]):
                The name of the dataset.
            created_at (Optional[datetime.datetime]):
                The creation timestamp of the example.

        Returns:
            Example: The created example
        """
        return self.create_example(
            inputs={"input": prompt},
            outputs={"output": generation},
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            created_at=created_at,
        )

    @ls_utils.xor_args(("dataset_id", "dataset_name"))
    def create_chat_example(
        self,
        messages: list[Union[Mapping[str, Any], ls_schemas.BaseMessageLike]],
        generations: Optional[
            Union[Mapping[str, Any], ls_schemas.BaseMessageLike]
        ] = None,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
    ) -> ls_schemas.Example:
        """Add an example (row) to a Chat-type dataset.

        Args:
            messages (List[Union[Mapping[str, Any], BaseMessageLike]]):
                The input messages for the example.
            generations (Optional[Union[Mapping[str, Any], BaseMessageLike]]):
                The output messages for the example.
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset.
            dataset_name (Optional[str]):
                The name of the dataset.
            created_at (Optional[datetime.datetime]):
                The creation timestamp of the example.

        Returns:
            Example: The created example
        """
        final_input = []
        for message in messages:
            if ls_utils.is_base_message_like(message):
                final_input.append(
                    ls_utils.convert_langchain_message(
                        cast(ls_schemas.BaseMessageLike, message)
                    )
                )
            else:
                final_input.append(cast(dict, message))
        final_generations = None
        if generations is not None:
            if ls_utils.is_base_message_like(generations):
                final_generations = ls_utils.convert_langchain_message(
                    cast(ls_schemas.BaseMessageLike, generations)
                )
            else:
                final_generations = cast(dict, generations)
        return self.create_example(
            inputs={"input": final_input},
            outputs=(
                {"output": final_generations} if final_generations is not None else None
            ),
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            created_at=created_at,
        )

    def create_example_from_run(
        self,
        run: ls_schemas.Run,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
    ) -> ls_schemas.Example:
        """Add an example (row) to a dataset from a run.

        Args:
            run (Run): The run to create an example from.
            dataset_id (Optional[Union[UUID, str]]): The ID of the dataset.
            dataset_name (Optional[str]): The name of the dataset.
            created_at (Optional[datetime.datetime]): The creation timestamp of the example.

        Returns:
            Example: The created example
        """
        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
            dataset_name = None  # Nested call expects only 1 defined
        dataset_type = self._get_data_type_cached(dataset_id)
        if dataset_type == ls_schemas.DataType.llm:
            if run.run_type != "llm":
                raise ValueError(
                    f"Run type {run.run_type} is not supported"
                    " for dataset of type 'LLM'"
                )
            try:
                prompt = ls_utils.get_prompt_from_inputs(run.inputs)
            except ValueError:
                raise ValueError(
                    "Error converting LLM run inputs to prompt for run"
                    f" {run.id} with inputs {run.inputs}"
                )
            inputs: dict[str, Any] = {"input": prompt}
            if not run.outputs:
                outputs: Optional[dict[str, Any]] = None
            else:
                try:
                    generation = ls_utils.get_llm_generation_from_outputs(run.outputs)
                except ValueError:
                    raise ValueError(
                        "Error converting LLM run outputs to generation for run"
                        f" {run.id} with outputs {run.outputs}"
                    )
                outputs = {"output": generation}
        elif dataset_type == ls_schemas.DataType.chat:
            if run.run_type != "llm":
                raise ValueError(
                    f"Run type {run.run_type} is not supported"
                    " for dataset of type 'chat'"
                )
            try:
                inputs = {"input": ls_utils.get_messages_from_inputs(run.inputs)}
            except ValueError:
                raise ValueError(
                    "Error converting LLM run inputs to chat messages for run"
                    f" {run.id} with inputs {run.inputs}"
                )
            if not run.outputs:
                outputs = None
            else:
                try:
                    outputs = {
                        "output": ls_utils.get_message_generation_from_outputs(
                            run.outputs
                        )
                    }
                except ValueError:
                    raise ValueError(
                        "Error converting LLM run outputs to chat generations"
                        f" for run {run.id} with outputs {run.outputs}"
                    )
        elif dataset_type == ls_schemas.DataType.kv:
            # Anything goes
            inputs = run.inputs
            outputs = run.outputs

        else:
            raise ValueError(f"Dataset type {dataset_type} not recognized.")
        return self.create_example(
            inputs=inputs,
            outputs=outputs,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            created_at=created_at,
        )

    def _prepare_multipart_data(
        self,
        examples: Union[
            list[ls_schemas.ExampleCreate]
            | list[ls_schemas.ExampleUpsertWithAttachments]
            | list[ls_schemas.ExampleUpdate],
        ],
        include_dataset_id: bool = False,
        dangerously_allow_filesystem: bool = False,
    ) -> tuple[Any, bytes, dict[str, io.BufferedReader]]:
        parts: list[MultipartPart] = []
        opened_files_dict: dict[str, io.BufferedReader] = {}
        if include_dataset_id:
            if not isinstance(examples[0], ls_schemas.ExampleUpsertWithAttachments):
                raise ValueError(
                    "The examples must be of type ExampleUpsertWithAttachments"
                    " if include_dataset_id is True"
                )
            dataset_id = examples[0].dataset_id

        for example in examples:
            if (
                not isinstance(example, ls_schemas.ExampleCreate)
                and not isinstance(example, ls_schemas.ExampleUpsertWithAttachments)
                and not isinstance(example, ls_schemas.ExampleUpdate)
            ):
                raise ValueError(
                    "The examples must be of type ExampleCreate"
                    " or ExampleUpsertWithAttachments"
                    " or ExampleUpdate"
                )
            if example.id is not None:
                example_id = str(example.id)
            else:
                example_id = str(uuid.uuid4())

            if isinstance(example, ls_schemas.ExampleUpdate):
                created_at = None
            else:
                created_at = example.created_at

            if isinstance(example, ls_schemas.ExampleCreate):
                use_source_run_io = example.use_source_run_io
                use_source_run_attachments = example.use_source_run_attachments
                source_run_id = example.source_run_id
            else:
                use_source_run_io, use_source_run_attachments, source_run_id = (
                    None,
                    None,
                    None,
                )

            example_body = {
                **({"dataset_id": dataset_id} if include_dataset_id else {}),
                **({"created_at": created_at} if created_at is not None else {}),
                **(
                    {"use_source_run_io": use_source_run_io}
                    if use_source_run_io
                    else {}
                ),
                **(
                    {"use_source_run_attachments": use_source_run_attachments}
                    if use_source_run_attachments
                    else {}
                ),
                **({"source_run_id": source_run_id} if source_run_id else {}),
            }
            if example.metadata is not None:
                example_body["metadata"] = example.metadata
            if example.split is not None:
                example_body["split"] = example.split
            valb = _dumps_json(example_body)

            parts.append(
                (
                    f"{example_id}",
                    (
                        None,
                        valb,
                        "application/json",
                        {},
                    ),
                )
            )

            if example.inputs is not None:
                inputsb = _dumps_json(example.inputs)
                parts.append(
                    (
                        f"{example_id}.inputs",
                        (
                            None,
                            inputsb,
                            "application/json",
                            {},
                        ),
                    )
                )

            if example.outputs is not None:
                outputsb = _dumps_json(example.outputs)
                parts.append(
                    (
                        f"{example_id}.outputs",
                        (
                            None,
                            outputsb,
                            "application/json",
                            {},
                        ),
                    )
                )

            if example.attachments:
                for name, attachment in example.attachments.items():
                    if isinstance(attachment, dict):
                        mime_type = attachment["mime_type"]
                        attachment_data = attachment["data"]
                    else:
                        mime_type, attachment_data = attachment
                    if isinstance(attachment_data, Path):
                        if dangerously_allow_filesystem:
                            try:
                                file_size = os.path.getsize(attachment_data)
                                file = open(attachment_data, "rb")
                            except FileNotFoundError:
                                logger.warning(
                                    "Attachment file not found for example %s: %s",
                                    example_id,
                                    attachment_data,
                                )
                                continue
                            opened_files_dict[
                                str(attachment_data) + str(uuid.uuid4())
                            ] = file

                            parts.append(
                                (
                                    f"{example_id}.attachment.{name}",
                                    (
                                        None,
                                        file,  # type: ignore[arg-type]
                                        f"{mime_type}; length={file_size}",
                                        {},
                                    ),
                                )
                            )
                        else:
                            raise ValueError(
                                "dangerously_allow_filesystem must be True to upload files from the filesystem"
                            )
                    else:
                        parts.append(
                            (
                                f"{example_id}.attachment.{name}",
                                (
                                    None,
                                    attachment_data,
                                    f"{mime_type}; length={len(attachment_data)}",
                                    {},
                                ),
                            )
                        )

            if (
                isinstance(example, ls_schemas.ExampleUpdate)
                and example.attachments_operations
            ):
                attachments_operationsb = _dumps_json(example.attachments_operations)
                parts.append(
                    (
                        f"{example_id}.attachments_operations",
                        (
                            None,
                            attachments_operationsb,
                            "application/json",
                            {},
                        ),
                    )
                )

        encoder = rqtb_multipart.MultipartEncoder(parts, boundary=_BOUNDARY)
        if encoder.len <= 20_000_000:  # ~20 MB
            data = encoder.to_string()
        else:
            data = encoder

        return encoder, data, opened_files_dict

    def update_examples_multipart(
        self,
        *,
        dataset_id: ID_TYPE,
        updates: Optional[list[ls_schemas.ExampleUpdate]] = None,
        dangerously_allow_filesystem: bool = False,
    ) -> ls_schemas.UpsertExamplesResponse:
        """Update examples using multipart.

        .. deprecated:: 0.3.9

            Use Client.update_examples instead. Will be removed in 0.4.0.
        """
        return self._update_examples_multipart(
            dataset_id=dataset_id,
            updates=updates,
            dangerously_allow_filesystem=dangerously_allow_filesystem,
        )

    def _update_examples_multipart(
        self,
        *,
        dataset_id: ID_TYPE,
        updates: Optional[list[ls_schemas.ExampleUpdate]] = None,
        dangerously_allow_filesystem: bool = False,
    ) -> ls_schemas.UpsertExamplesResponse:
        """Update examples using multipart.

        Args:
            dataset_id (Union[UUID, str]): The ID of the dataset to update.
            updates (Optional[List[ExampleUpdate]]): The updates to apply to the examples.

        Raises:
            ValueError: If the multipart examples endpoint is not enabled.
        """
        if not (self.info.instance_flags or {}).get(
            "dataset_examples_multipart_enabled", False
        ):
            raise ValueError(
                "Your LangSmith deployment does not allow using the latest examples "
                "endpoints, please upgrade your deployment to the latest version or downgrade your SDK "
                "to langsmith<0.3.9."
            )
        if updates is None:
            updates = []

        encoder, data, opened_files_dict = self._prepare_multipart_data(
            updates,
            include_dataset_id=False,
            dangerously_allow_filesystem=dangerously_allow_filesystem,
        )

        try:
            response = self.request_with_retries(
                "PATCH",
                _dataset_examples_path(self.api_url, dataset_id),
                request_kwargs={
                    "data": data,
                    "headers": {
                        **self._headers,
                        "Content-Type": encoder.content_type,
                    },
                },
            )
            ls_utils.raise_for_status_with_text(response)
        finally:
            _close_files(list(opened_files_dict.values()))
        return response.json()

    def upload_examples_multipart(
        self,
        *,
        dataset_id: ID_TYPE,
        uploads: Optional[list[ls_schemas.ExampleCreate]] = None,
        dangerously_allow_filesystem: bool = False,
    ) -> ls_schemas.UpsertExamplesResponse:
        """Upload examples using multipart.

        .. deprecated:: 0.3.9

            Use Client.create_examples instead. Will be removed in 0.4.0.
        """
        return self._upload_examples_multipart(
            dataset_id=dataset_id,
            uploads=uploads,
            dangerously_allow_filesystem=dangerously_allow_filesystem,
        )

    def _upload_examples_multipart(
        self,
        *,
        dataset_id: ID_TYPE,
        uploads: Optional[list[ls_schemas.ExampleCreate]] = None,
        dangerously_allow_filesystem: bool = False,
    ) -> ls_schemas.UpsertExamplesResponse:
        """Upload examples using multipart.

        Args:
            dataset_id (Union[UUID, str]): The ID of the dataset to upload to.
            uploads (Optional[List[ExampleCreate]]): The examples to upload.
            dangerously_allow_filesystem (bool): Whether to allow uploading files from the filesystem.

        Returns:
            ls_schemas.UpsertExamplesResponse: The count and ids of the successfully uploaded examples

        Raises:
            ValueError: If the multipart examples endpoint is not enabled.
        """
        if not (self.info.instance_flags or {}).get(
            "dataset_examples_multipart_enabled", False
        ):
            raise ValueError(
                "Your LangSmith deployment does not allow using the multipart examples endpoint, please upgrade your deployment to the latest version."
            )
        if uploads is None:
            uploads = []
        encoder, data, opened_files_dict = self._prepare_multipart_data(
            uploads,
            include_dataset_id=False,
            dangerously_allow_filesystem=dangerously_allow_filesystem,
        )

        try:
            response = self.request_with_retries(
                "POST",
                _dataset_examples_path(self.api_url, dataset_id),
                request_kwargs={
                    "data": data,
                    "headers": {
                        **self._headers,
                        "Content-Type": encoder.content_type,
                    },
                },
            )
            ls_utils.raise_for_status_with_text(response)
        finally:
            _close_files(list(opened_files_dict.values()))
        return response.json()

    def upsert_examples_multipart(
        self,
        *,
        upserts: Optional[list[ls_schemas.ExampleUpsertWithAttachments]] = None,
        dangerously_allow_filesystem: bool = False,
    ) -> ls_schemas.UpsertExamplesResponse:
        """Upsert examples.

        .. deprecated:: 0.3.9

            Use Client.create_examples and Client.update_examples instead. Will be
            removed in 0.4.0.
        """
        if not (self.info.instance_flags or {}).get(
            "examples_multipart_enabled", False
        ):
            raise ValueError(
                "Your LangSmith deployment does not allow using the multipart examples endpoint, please upgrade your deployment to the latest version."
            )
        if upserts is None:
            upserts = []

        encoder, data, opened_files_dict = self._prepare_multipart_data(
            upserts,
            include_dataset_id=True,
            dangerously_allow_filesystem=dangerously_allow_filesystem,
        )

        try:
            response = self.request_with_retries(
                "POST",
                (
                    "/v1/platform/examples/multipart"
                    if self.api_url[-3:] != "/v1" and self.api_url[-4:] != "/v1/"
                    else "/platform/examples/multipart"
                ),
                request_kwargs={
                    "data": data,
                    "headers": {
                        **self._headers,
                        "Content-Type": encoder.content_type,
                    },
                },
            )
            ls_utils.raise_for_status_with_text(response)
        finally:
            _close_files(list(opened_files_dict.values()))
        return response.json()

    @ls_utils.xor_args(("dataset_id", "dataset_name"))
    def create_examples(
        self,
        *,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
        examples: Optional[Sequence[ls_schemas.ExampleCreate | dict]] = None,
        dangerously_allow_filesystem: bool = False,
        **kwargs: Any,
    ) -> ls_schemas.UpsertExamplesResponse | dict[str, Any]:
        """Create examples in a dataset.

        Args:
            dataset_name (str | None):
                The name of the dataset to create the examples in. Must specify exactly
                one of dataset_name or dataset_id.
            dataset_id (UUID | str | None):
                The ID of the dataset to create the examples in. Must specify exactly
                one of dataset_name or dataset_id
            examples (Sequence[ExampleCreate | dict]):
                The examples to create.
            dangerously_allow_filesystem (bool):
                Whether to allow uploading files from the filesystem.
            **kwargs (Any): Legacy keyword args. Should not be specified if 'examples' is specified.

                - inputs (Sequence[Mapping[str, Any]]): The input values for the examples.
                - outputs (Optional[Sequence[Optional[Mapping[str, Any]]]]): The output values for the examples.
                - metadata (Optional[Sequence[Optional[Mapping[str, Any]]]]): The metadata for the examples.
                - splits (Optional[Sequence[Optional[str | List[str]]]]): The splits for the examples, which are divisions of your dataset such as 'train', 'test', or 'validation'.
                - source_run_ids (Optional[Sequence[Optional[Union[UUID, str]]]]): The IDs of the source runs associated with the examples.
                - ids (Optional[Sequence[Union[UUID, str]]]): The IDs of the examples.

        Raises:
            ValueError: If 'examples' and legacy args are both provided.

        Returns:
            The LangSmith JSON response. Includes 'count' and 'example_ids'.

        .. versionchanged:: 0.3.11

            Updated to take argument 'examples', a single list where each
            element is the full example to create. This should be used instead of the
            legacy 'inputs', 'outputs', etc. arguments which split each examples
            attributes across arguments.

            Updated to support creating examples with attachments.

        Example:
            .. code-block:: python

                from langsmith import Client

                client = Client()

                dataset = client.create_dataset("agent-qa")

                examples = [
                    {
                        "inputs": {"question": "what's an agent"},
                        "outputs": {"answer": "an agent is..."},
                        "metadata": {"difficulty": "easy"},
                    },
                    {
                        "inputs": {
                            "question": "can you explain the agent architecture in this diagram?"
                        },
                        "outputs": {"answer": "this diagram shows..."},
                        "attachments": {"diagram": {"mime_type": "image/png", "data": b"..."}},
                        "metadata": {"difficulty": "medium"},
                    },
                    # more examples...
                ]

                response = client.create_examples(dataset_name="agent-qa", examples=examples)
                # -> {"example_ids": [...
        """  # noqa: E501
        if kwargs and examples:
            kwarg_keys = ", ".join([f"'{k}'" for k in kwargs])
            raise ValueError(
                f"Cannot specify {kwarg_keys} when 'examples' is specified."
            )

        supported_kwargs = {
            "inputs",
            "outputs",
            "metadata",
            "splits",
            "ids",
            "source_run_ids",
        }
        if kwargs and (unsupported := set(kwargs).difference(supported_kwargs)):
            raise ValueError(
                f"Received unsupported keyword arguments: {tuple(unsupported)}."
            )

        if not (dataset_id or dataset_name):
            raise ValueError("Either dataset_id or dataset_name must be provided.")
        elif not dataset_id:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id

        if examples:
            uploads = [
                ls_schemas.ExampleCreate(**x) if isinstance(x, dict) else x
                for x in examples
            ]

        # For backwards compatibility
        else:
            inputs = kwargs.get("inputs")
            if not inputs:
                raise ValueError("Must specify either 'examples' or 'inputs.'")
            # Since inputs are required, we will check against them
            input_len = len(inputs)
            for arg_name, arg_value in kwargs.items():
                if arg_value is not None and len(arg_value) != input_len:
                    raise ValueError(
                        f"Length of {arg_name} ({len(arg_value)}) does not match"
                        f" length of inputs ({input_len})"
                    )
            uploads = [
                ls_schemas.ExampleCreate(
                    **{
                        "inputs": in_,
                        "outputs": out_,
                        "metadata": metadata_,
                        "split": split_,
                        "id": id_ or str(uuid.uuid4()),
                        "source_run_id": source_run_id_,
                    }
                )
                for in_, out_, metadata_, split_, id_, source_run_id_ in zip(
                    inputs,
                    kwargs.get("outputs") or (None for _ in range(input_len)),
                    kwargs.get("metadata") or (None for _ in range(input_len)),
                    kwargs.get("splits") or (None for _ in range(input_len)),
                    kwargs.get("ids") or (None for _ in range(input_len)),
                    kwargs.get("source_run_ids") or (None for _ in range(input_len)),
                )
            ]

        if (self.info.instance_flags or {}).get(
            "dataset_examples_multipart_enabled", False
        ):
            return self._upload_examples_multipart(
                dataset_id=cast(uuid.UUID, dataset_id),
                uploads=uploads,
                dangerously_allow_filesystem=dangerously_allow_filesystem,
            )
        else:
            for upload in uploads:
                if getattr(upload, "attachments") is not None:
                    upload.attachments = None
                    warnings.warn(
                        "Must upgrade your LangSmith version to use attachments."
                    )
            # fallback to old method
            response = self.request_with_retries(
                "POST",
                "/examples/bulk",
                headers={**self._headers, "Content-Type": "application/json"},
                data=_dumps_json(
                    [
                        {**dump_model(upload), "dataset_id": str(dataset_id)}
                        for upload in uploads
                    ]
                ),
            )
            ls_utils.raise_for_status_with_text(response)
            return response.json()

    @ls_utils.xor_args(("dataset_id", "dataset_name"))
    def create_example(
        self,
        inputs: Optional[Mapping[str, Any]] = None,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
        outputs: Optional[Mapping[str, Any]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        split: Optional[str | list[str]] = None,
        example_id: Optional[ID_TYPE] = None,
        source_run_id: Optional[ID_TYPE] = None,
        use_source_run_io: bool = False,
        use_source_run_attachments: Optional[list[str]] = None,
        attachments: Optional[ls_schemas.Attachments] = None,
    ) -> ls_schemas.Example:
        """Create a dataset example in the LangSmith API.

        Examples are rows in a dataset, containing the inputs
        and expected outputs (or other reference information)
        for a model or chain.

        Args:
            inputs (Mapping[str, Any]):
                The input values for the example.
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset to create the example in.
            dataset_name (Optional[str]):
                The name of the dataset to create the example in.
            created_at (Optional[datetime.datetime]):
                The creation timestamp of the example.
            outputs (Optional[Mapping[str, Any]]):
                The output values for the example.
            metadata (Optional[Mapping[str, Any]]):
                The metadata for the example.
            split (Optional[str | List[str]]):
                The splits for the example, which are divisions
                of your dataset such as 'train', 'test', or 'validation'.
            example_id (Optional[Union[UUID, str]]):
                The ID of the example to create. If not provided, a new
                example will be created.
            source_run_id (Optional[Union[UUID, str]]):
                The ID of the source run associated with this example.
            use_source_run_io (bool):
                Whether to use the inputs, outputs, and attachments from the source run.
            use_source_run_attachments (Optional[List[str]]):
                Which attachments to use from the source run. If use_source_run_io
                is True, all attachments will be used regardless of this param.
            attachments (Optional[Attachments]):
                The attachments for the example.

        Returns:
            Example: The created example.
        """
        if inputs is None and not use_source_run_io:
            raise ValueError("Must provide either inputs or use_source_run_io")

        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id

        data = ls_schemas.ExampleCreate(
            **{
                "inputs": inputs,
                "outputs": outputs,
                "metadata": metadata,
                "split": split,
                "source_run_id": source_run_id,
                "use_source_run_io": use_source_run_io,
                "use_source_run_attachments": use_source_run_attachments,
                "attachments": attachments,
            }
        )
        if created_at:
            data.created_at = created_at
        data.id = (
            (uuid.UUID(example_id) if isinstance(example_id, str) else example_id)
            if example_id
            else uuid.uuid4()
        )

        if (self.info.instance_flags or {}).get(
            "dataset_examples_multipart_enabled", False
        ):
            self._upload_examples_multipart(dataset_id=dataset_id, uploads=[data])
            return self.read_example(example_id=data.id)
        else:
            # fallback to old method
            if getattr(data, "attachments") is not None:
                data.attachments = None
                warnings.warn("Must upgrade your LangSmith version to use attachments")
            response = self.request_with_retries(
                "POST",
                "/examples",
                headers={**self._headers, "Content-Type": "application/json"},
                data=_dumps_json(
                    {
                        **{k: v for k, v in dump_model(data).items() if v is not None},
                        "dataset_id": str(dataset_id),
                    }
                ),
            )
            ls_utils.raise_for_status_with_text(response)
            result = response.json()
            return ls_schemas.Example(
                **result,
                _host_url=self._host_url,
                _tenant_id=self._get_optional_tenant_id(),
            )

    def read_example(
        self, example_id: ID_TYPE, *, as_of: Optional[datetime.datetime] = None
    ) -> ls_schemas.Example:
        """Read an example from the LangSmith API.

        Args:
            example_id (Union[UUID, str]): The ID of the example to read.
            as_of (Optional[datetime.datetime]): The dataset version tag OR
                timestamp to retrieve the example as of.
                Response examples will only be those that were present at the time
                of the tagged (or timestamped) version.

        Returns:
            Example: The example.
        """
        response = self.request_with_retries(
            "GET",
            f"/examples/{_as_uuid(example_id, 'example_id')}",
            params={
                "as_of": as_of.isoformat() if as_of else None,
            },
        )

        example = response.json()
        attachments = _convert_stored_attachments_to_attachments_dict(
            example, attachments_key="attachment_urls", api_url=self.api_url
        )

        return ls_schemas.Example(
            **{k: v for k, v in example.items() if k != "attachment_urls"},
            attachments=attachments,
            _host_url=self._host_url,
            _tenant_id=self._get_optional_tenant_id(),
        )

    def list_examples(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        example_ids: Optional[Sequence[ID_TYPE]] = None,
        as_of: Optional[Union[datetime.datetime, str]] = None,
        splits: Optional[Sequence[str]] = None,
        inline_s3_urls: bool = True,
        *,
        offset: int = 0,
        limit: Optional[int] = None,
        metadata: Optional[dict] = None,
        filter: Optional[str] = None,
        include_attachments: bool = False,
        **kwargs: Any,
    ) -> Iterator[ls_schemas.Example]:
        r"""Retrieve the example rows of the specified dataset.

        Args:
            dataset_id (Optional[Union[UUID, str]]): The ID of the dataset to filter by.
                Defaults to None.
            dataset_name (Optional[str]): The name of the dataset to filter by.
                Defaults to None.
            example_ids (Optional[Sequence[Union[UUID, str]]): The IDs of the examples to filter by.
                Defaults to None.
            as_of (Optional[Union[datetime.datetime, str]]): The dataset version tag OR
                timestamp to retrieve the examples as of.
                Response examples will only be those that were present at the time
                of the tagged (or timestamped) version.
            splits (Optional[Sequence[str]]): A list of dataset splits, which are
                divisions of your dataset such as 'train', 'test', or 'validation'.
                Returns examples only from the specified splits.
            inline_s3_urls (bool, default=True): Whether to inline S3 URLs.
                Defaults to True.
            offset (int, default=0): The offset to start from. Defaults to 0.
            limit (Optional[int]): The maximum number of examples to return.
            metadata (Optional[dict]): A dictionary of metadata to filter by.
            filter (Optional[str]): A structured filter string to apply to
                the examples.
            include_attachments (bool, default=False): Whether to include the
                attachments in the response. Defaults to False.
            **kwargs (Any): Additional keyword arguments are ignored.

        Yields:
            The examples.

        Examples:
            List all examples for a dataset:

            .. code-block:: python

                from langsmith import Client

                client = Client()

                # By Dataset ID
                examples = client.list_examples(
                    dataset_id="c9ace0d8-a82c-4b6c-13d2-83401d68e9ab"
                )
                # By Dataset Name
                examples = client.list_examples(dataset_name="My Test Dataset")

            List examples by id

            .. code-block:: python

                example_ids = [
                    "734fc6a0-c187-4266-9721-90b7a025751a",
                    "d6b4c1b9-6160-4d63-9b61-b034c585074f",
                    "4d31df4e-f9c3-4a6e-8b6c-65701c2fed13",
                ]
                examples = client.list_examples(example_ids=example_ids)

            List examples by metadata

            .. code-block:: python

                examples = client.list_examples(
                    dataset_name=dataset_name, metadata={"foo": "bar"}
                )

            List examples by structured filter

            .. code-block:: python

                examples = client.list_examples(
                    dataset_name=dataset_name,
                    filter='and(not(has(metadata, \'{"foo": "bar"}\')), exists(metadata, "tenant_id"))',
                )
        """
        params: dict[str, Any] = {
            **kwargs,
            "offset": offset,
            "id": example_ids,
            "as_of": (
                as_of.isoformat() if isinstance(as_of, datetime.datetime) else as_of
            ),
            "splits": splits,
            "inline_s3_urls": inline_s3_urls,
            "limit": min(limit, 100) if limit is not None else 100,
            "filter": filter,
        }
        if metadata is not None:
            params["metadata"] = _dumps_json(metadata)
        if dataset_id is not None:
            params["dataset"] = dataset_id
        elif dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
            params["dataset"] = dataset_id
        else:
            pass
        if include_attachments:
            params["select"] = ["attachment_urls", "outputs", "metadata"]
        for i, example in enumerate(
            self._get_paginated_list("/examples", params=params)
        ):
            attachments = _convert_stored_attachments_to_attachments_dict(
                example, attachments_key="attachment_urls", api_url=self.api_url
            )

            yield ls_schemas.Example(
                **{k: v for k, v in example.items() if k != "attachment_urls"},
                attachments=attachments,
                _host_url=self._host_url,
                _tenant_id=self._get_optional_tenant_id(),
            )
            if limit is not None and i + 1 >= limit:
                break

    @warn_beta
    def index_dataset(
        self,
        *,
        dataset_id: ID_TYPE,
        tag: str = "latest",
        **kwargs: Any,
    ) -> None:
        """Enable dataset indexing. Examples are indexed by their inputs.

        This enables searching for similar examples by inputs with
        ``client.similar_examples()``.

        Args:
            dataset_id (Union[UUID, str]): The ID of the dataset to index.
            tag (Optional[str]): The version of the dataset to index. If 'latest'
                then any updates to the dataset (additions, updates, deletions of
                examples) will be reflected in the index.
            **kwargs (Any): Additional keyword arguments to pass as part of request body.

        Returns:
            None
        """  # noqa: E501
        dataset_id = _as_uuid(dataset_id, "dataset_id")
        resp = self.request_with_retries(
            "POST",
            f"/datasets/{dataset_id}/index",
            headers=self._headers,
            data=json.dumps({"tag": tag, **kwargs}),
        )
        ls_utils.raise_for_status_with_text(resp)

    @warn_beta
    def sync_indexed_dataset(
        self,
        *,
        dataset_id: ID_TYPE,
        **kwargs: Any,
    ) -> None:
        """Sync dataset index. This already happens automatically every 5 minutes, but you can call this to force a sync.

        Args:
            dataset_id (Union[UUID, str]): The ID of the dataset to sync.

        Returns:
            None
        """  # noqa: E501
        dataset_id = _as_uuid(dataset_id, "dataset_id")
        resp = self.request_with_retries(
            "POST",
            f"/datasets/{dataset_id}/index/sync",
            headers=self._headers,
            data=json.dumps({**kwargs}),
        )
        ls_utils.raise_for_status_with_text(resp)

    # NOTE: dataset_name arg explicitly not supported to avoid extra API calls.
    @warn_beta
    def similar_examples(
        self,
        inputs: dict,
        /,
        *,
        limit: int,
        dataset_id: ID_TYPE,
        filter: Optional[str] = None,
        **kwargs: Any,
    ) -> list[ls_schemas.ExampleSearch]:
        r"""Retrieve the dataset examples whose inputs best match the current inputs.

        **Note**: Must have few-shot indexing enabled for the dataset. See
        `client.index_dataset()`.

        Args:
            inputs (dict): The inputs to use as a search query. Must match the dataset
                input schema. Must be JSON serializable.
            limit (int): The maximum number of examples to return.
            dataset_id (Union[UUID, str]): The ID of the dataset to search over.
            filter (Optional[str]): A filter string to apply to the search results. Uses
                the same syntax as the `filter` parameter in `list_runs()`. Only a subset
                of operations are supported. Defaults to None.

                For example, you can use ``and(eq(metadata.some_tag, 'some_value'), neq(metadata.env, 'dev'))``
                to filter only examples where some_tag has some_value, and the environment is not dev.
            **kwargs: Additional keyword arguments to pass as part of request body.

        Returns:
            list[ExampleSearch]: List of ExampleSearch objects.

        Examples:
            .. code-block:: python

                from langsmith import Client

                client = Client()
                client.similar_examples(
                    {"question": "When would i use the runnable generator"},
                    limit=3,
                    dataset_id="...",
                )

            .. code-block:: python

                [
                    ExampleSearch(
                        inputs={
                            "question": "How do I cache a Chat model? What caches can I use?"
                        },
                        outputs={
                            "answer": "You can use LangChain's caching layer for Chat Models. This can save you money by reducing the number of API calls you make to the LLM provider, if you're often requesting the same completion multiple times, and speed up your application.\n\nfrom langchain.cache import InMemoryCache\nlangchain.llm_cache = InMemoryCache()\n\n# The first time, it is not yet in cache, so it should take longer\nllm.predict('Tell me a joke')\n\nYou can also use SQLite Cache which uses a SQLite database:\n\nrm .langchain.db\n\nfrom langchain.cache import SQLiteCache\nlangchain.llm_cache = SQLiteCache(database_path=\".langchain.db\")\n\n# The first time, it is not yet in cache, so it should take longer\nllm.predict('Tell me a joke') \n"
                        },
                        metadata=None,
                        id=UUID("b2ddd1c4-dff6-49ae-8544-f48e39053398"),
                        dataset_id=UUID("01b6ce0f-bfb6-4f48-bbb8-f19272135d40"),
                    ),
                    ExampleSearch(
                        inputs={"question": "What's a runnable lambda?"},
                        outputs={
                            "answer": "A runnable lambda is an object that implements LangChain's `Runnable` interface and runs a callbale (i.e., a function). Note the function must accept a single argument."
                        },
                        metadata=None,
                        id=UUID("f94104a7-2434-4ba7-8293-6a283f4860b4"),
                        dataset_id=UUID("01b6ce0f-bfb6-4f48-bbb8-f19272135d40"),
                    ),
                    ExampleSearch(
                        inputs={"question": "Show me how to use RecursiveURLLoader"},
                        outputs={
                            "answer": 'The RecursiveURLLoader comes from the langchain.document_loaders.recursive_url_loader module. Here\'s an example of how to use it:\n\nfrom langchain.document_loaders.recursive_url_loader import RecursiveUrlLoader\n\n# Create an instance of RecursiveUrlLoader with the URL you want to load\nloader = RecursiveUrlLoader(url="https://example.com")\n\n# Load all child links from the URL page\nchild_links = loader.load()\n\n# Print the child links\nfor link in child_links:\n    print(link)\n\nMake sure to replace "https://example.com" with the actual URL you want to load. The load() method returns a list of child links found on the URL page. You can iterate over this list to access each child link.'
                        },
                        metadata=None,
                        id=UUID("0308ea70-a803-4181-a37d-39e95f138f8c"),
                        dataset_id=UUID("01b6ce0f-bfb6-4f48-bbb8-f19272135d40"),
                    ),
                ]

        """
        dataset_id = _as_uuid(dataset_id, "dataset_id")
        req = {
            "inputs": inputs,
            "limit": limit,
            **kwargs,
        }
        if filter is not None:
            req["filter"] = filter

        resp = self.request_with_retries(
            "POST",
            f"/datasets/{dataset_id}/search",
            headers=self._headers,
            data=json.dumps(req),
        )
        ls_utils.raise_for_status_with_text(resp)
        examples = []
        for ex in resp.json()["examples"]:
            examples.append(ls_schemas.ExampleSearch(**ex, dataset_id=dataset_id))
        return examples

    def update_example(
        self,
        example_id: ID_TYPE,
        *,
        inputs: Optional[dict[str, Any]] = None,
        outputs: Optional[Mapping[str, Any]] = None,
        metadata: Optional[dict] = None,
        split: Optional[str | list[str]] = None,
        dataset_id: Optional[ID_TYPE] = None,
        attachments_operations: Optional[ls_schemas.AttachmentsOperations] = None,
        attachments: Optional[ls_schemas.Attachments] = None,
    ) -> dict[str, Any]:
        """Update a specific example.

        Args:
            example_id (Union[UUID, str]):
                The ID of the example to update.
            inputs (Optional[Dict[str, Any]]):
                The input values to update.
            outputs (Optional[Mapping[str, Any]]):
                The output values to update.
            metadata (Optional[Dict]):
                The metadata to update.
            split (Optional[str | List[str]]):
                The dataset split to update, such as
                'train', 'test', or 'validation'.
            dataset_id (Optional[Union[UUID, str]]):
                The ID of the dataset to update.
            attachments_operations (Optional[AttachmentsOperations]):
                The attachments operations to perform.
            attachments (Optional[Attachments]):
                The attachments to add to the example.

        Returns:
            Dict[str, Any]: The updated example.
        """
        if attachments_operations is not None:
            if not (self.info.instance_flags or {}).get(
                "dataset_examples_multipart_enabled", False
            ):
                raise ValueError(
                    "Your LangSmith deployment does not allow using the attachment operations, please upgrade your deployment to the latest version."
                )
        example_dict = dict(
            inputs=inputs,
            outputs=outputs,
            id=example_id,
            metadata=metadata,
            split=split,
            attachments_operations=attachments_operations,
            attachments=attachments,
        )
        example = ls_schemas.ExampleUpdate(
            **{k: v for k, v in example_dict.items() if v is not None}
        )

        if dataset_id is None:
            dataset_id = self.read_example(example_id).dataset_id

        if (self.info.instance_flags or {}).get(
            "dataset_examples_multipart_enabled", False
        ):
            return dict(
                self._update_examples_multipart(
                    dataset_id=dataset_id, updates=[example]
                )
            )
        else:
            # fallback to old method
            response = self.request_with_retries(
                "PATCH",
                f"/examples/{_as_uuid(example_id, 'example_id')}",
                headers={**self._headers, "Content-Type": "application/json"},
                data=_dumps_json(
                    {
                        **{
                            k: v
                            for k, v in dump_model(example).items()
                            if v is not None
                        },
                        "dataset_id": str(dataset_id),
                    }
                ),
            )
            ls_utils.raise_for_status_with_text(response)
            return response.json()

    def update_examples(
        self,
        *,
        dataset_name: str | None = None,
        dataset_id: ID_TYPE | None = None,
        updates: Optional[Sequence[ls_schemas.ExampleUpdate | dict]] = None,
        dangerously_allow_filesystem: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Update multiple examples.

         Examples are expected to all be part of the same dataset.

        Args:
             dataset_name (str | None):
                 The name of the dataset to update. Should specify exactly one of
                 'dataset_name' or 'dataset_id'.
             dataset_id (UUID | str | None):
                 The ID of the dataset to update. Should specify exactly one of
                 'dataset_name' or 'dataset_id'.
             updates (Sequence[ExampleUpdate | dict] | None):
                 The example updates. Overwrites any specified fields and does not
                 update any unspecified fields.
             dangerously_allow_filesystem (bool):
                 Whether to allow using filesystem paths as attachments.
             **kwargs (Any):
                 Legacy keyword args. Should not be specified if 'updates' is specified.

                 - example_ids (Sequence[UUID | str]): The IDs of the examples to update.
                 - inputs (Sequence[dict | None] | None): The input values for the examples.
                 - outputs (Sequence[dict | None] | None): The output values for the examples.
                 - metadata (Sequence[dict | None] | None): The metadata for the examples.
                 - splits (Sequence[str | list[str] | None] | None): The splits for the examples, which are divisions of your dataset such as 'train', 'test', or 'validation'.
                 - attachments_operations (Sequence[AttachmentsOperations | None] | None): The operations to perform on the attachments.
                 - dataset_ids (Sequence[UUID | str] | None): The IDs of the datasets to move the examples to.

        Returns:
             The LangSmith JSON response. Includes 'message', 'count', and 'example_ids'.

         .. versionchanged:: 0.3.9

             Updated to ...

        Example:

             .. code-block:: python

                 from langsmith import Client

                 client = Client()

                 dataset = client.create_dataset("agent-qa")

                 examples = [
                     {
                         "inputs": {"question": "what's an agent"},
                         "outputs": {"answer": "an agent is..."},
                         "metadata": {"difficulty": "easy"},
                     },
                     {
                         "inputs": {
                             "question": "can you explain the agent architecture in this diagram?"
                         },
                         "outputs": {"answer": "this diagram shows..."},
                         "attachments": {"diagram": {"mime_type": "image/png", "data": b"..."}},
                         "metadata": {"difficulty": "medium"},
                     },
                     # more examples...
                 ]

                 response = client.create_examples(dataset_name="agent-qa", examples=examples)
                 example_ids = response["example_ids"]

                 updates = [
                     {
                         "id": example_ids[0],
                         "inputs": {"question": "what isn't an agent"},
                         "outputs": {"answer": "an agent is not..."},
                     },
                     {
                         "id": example_ids[1],
                         "attachments_operations": [
                             {"rename": {"diagram": "agent_diagram"}, "retain": []}
                         ],
                     },
                 ]
                 response = client.update_examples(dataset_name="agent-qa", updates=updates)
                 # -> {"example_ids": [...
        """  # noqa: E501
        if kwargs and updates:
            raise ValueError(
                f"Must pass in either 'updates' or args {tuple(kwargs)}, not both."
            )
        if not (kwargs or updates):
            raise ValueError("Please pass in a non-empty sequence for arg 'updates'.")

        if dataset_name and dataset_id:
            raise ValueError(
                "Must pass in exactly one of 'dataset_name' or 'dataset_id'."
            )
        elif dataset_name:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id

        if updates:
            updates_obj = [
                ls_schemas.ExampleUpdate(**x) if isinstance(x, dict) else x
                for x in updates
            ]

            if not dataset_id:
                if updates_obj[0].dataset_id:
                    dataset_id = updates_obj[0].dataset_id
                else:
                    raise ValueError(
                        "Must pass in (exactly) one of 'dataset_name' or 'dataset_id'."
                    )

        # For backwards compatibility
        else:
            example_ids = kwargs.get("example_ids", None)
            if not example_ids:
                raise ValueError(
                    "Must pass in (exactly) one of 'updates' or 'example_ids'."
                )
            if not dataset_id:
                if "dataset_ids" not in kwargs:
                    # Assume all examples belong to same dataset
                    dataset_id = self.read_example(example_ids[0]).dataset_id
                elif len(set(kwargs["dataset_ids"])) > 1:
                    raise ValueError("Dataset IDs must be the same for all examples")
                elif not kwargs["dataset_ids"][0]:
                    raise ValueError("If specified, dataset_ids must be non-null.")
                else:
                    dataset_id = kwargs["dataset_ids"][0]

            multipart_enabled = (self.info.instance_flags or {}).get(
                "dataset_examples_multipart_enabled"
            )
            if (
                not multipart_enabled
                and (kwargs.get("attachments_operations") or kwargs.get("attachments"))
                is not None
            ):
                raise ValueError(
                    "Your LangSmith deployment does not allow using the attachment "
                    "operations, please upgrade your deployment to the latest version."
                )
            # Since ids are required, we will check against them
            examples_len = len(example_ids)
            for arg_name, arg_value in kwargs.items():
                if arg_value is not None and len(arg_value) != examples_len:
                    raise ValueError(
                        f"Length of {arg_name} ({len(arg_value)}) does not match"
                        f" length of examples ({examples_len})"
                    )
            updates_obj = [
                ls_schemas.ExampleUpdate(
                    **{
                        "id": id_,
                        "inputs": in_,
                        "outputs": out_,
                        "dataset_id": dataset_id_,
                        "metadata": metadata_,
                        "split": split_,
                        "attachments": attachments_,
                        "attachments_operations": attachments_operations_,
                    }
                )
                for id_, in_, out_, metadata_, split_, dataset_id_, attachments_, attachments_operations_ in zip(
                    example_ids,
                    kwargs.get("inputs", (None for _ in range(examples_len))),
                    kwargs.get("outputs", (None for _ in range(examples_len))),
                    kwargs.get("metadata", (None for _ in range(examples_len))),
                    kwargs.get("splits", (None for _ in range(examples_len))),
                    kwargs.get("dataset_ids", (None for _ in range(examples_len))),
                    kwargs.get("attachments", (None for _ in range(examples_len))),
                    kwargs.get(
                        "attachments_operations", (None for _ in range(examples_len))
                    ),
                )
            ]

        response: Any = None
        if (self.info.instance_flags or {}).get(
            "dataset_examples_multipart_enabled", False
        ):
            response = self._update_examples_multipart(
                dataset_id=cast(uuid.UUID, dataset_id),
                updates=updates_obj,
                dangerously_allow_filesystem=dangerously_allow_filesystem,
            )

            return {
                "message": f"{response.get('count', 0)} examples updated",
                **response,
            }
        else:
            # fallback to old method
            response = self.request_with_retries(
                "PATCH",
                "/examples/bulk",
                headers={**self._headers, "Content-Type": "application/json"},
                data=(
                    _dumps_json(
                        [
                            {
                                k: v
                                for k, v in dump_model(example).items()
                                if v is not None
                            }
                            for example in updates_obj
                        ]
                    )
                ),
            )
            ls_utils.raise_for_status_with_text(response)
            return response.json()

    def delete_example(self, example_id: ID_TYPE) -> None:
        """Delete an example by ID.

        Args:
            example_id (Union[UUID, str]):
                The ID of the example to delete.

        Returns:
            None
        """
        response = self.request_with_retries(
            "DELETE",
            f"/examples/{_as_uuid(example_id, 'example_id')}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def delete_examples(self, example_ids: Sequence[ID_TYPE]) -> None:
        """Delete multiple examples by ID.

        Parameters
        ----------
        example_ids : Sequence[ID_TYPE]
            The IDs of the examples to delete.
        """
        response = self.request_with_retries(
            "DELETE",
            "/examples",
            headers={**self._headers, "Content-Type": "application/json"},
            params={
                "example_ids": [
                    str(_as_uuid(id_, f"example_ids[{i}]"))
                    for i, id_ in enumerate(example_ids)
                ]
            },
        )
        ls_utils.raise_for_status_with_text(response)

    def list_dataset_splits(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        as_of: Optional[Union[str, datetime.datetime]] = None,
    ) -> list[str]:
        """Get the splits for a dataset.

        Args:
            dataset_id (Optional[Union[UUID, str]]): The ID of the dataset.
            dataset_name (Optional[str]): The name of the dataset.
            as_of (Optional[Union[str, datetime.datetime]]): The version
                of the dataset to retrieve splits for. Can be a timestamp or a
                string tag. Defaults to "latest".

        Returns:
            List[str]: The names of this dataset's splits.
        """
        if dataset_id is None:
            if dataset_name is None:
                raise ValueError("Must provide dataset name or ID")
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        params = {}
        if as_of is not None:
            params["as_of"] = (
                as_of.isoformat() if isinstance(as_of, datetime.datetime) else as_of
            )

        response = self.request_with_retries(
            "GET",
            f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}/splits",
            params=params,
        )
        ls_utils.raise_for_status_with_text(response)
        return response.json()

    def update_dataset_splits(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        split_name: str,
        example_ids: list[ID_TYPE],
        remove: bool = False,
    ) -> None:
        """Update the splits for a dataset.

        Args:
            dataset_id (Optional[Union[UUID, str]]): The ID of the dataset to update.
            dataset_name (Optional[str]): The name of the dataset to update.
            split_name (str): The name of the split to update.
            example_ids (List[Union[UUID, str]]): The IDs of the examples to add to or
                remove from the split.
            remove (Optional[bool]): If True, remove the examples from the split.
                If False, add the examples to the split. Defaults to False.

        Returns:
            None
        """
        if dataset_id is None:
            if dataset_name is None:
                raise ValueError("Must provide dataset name or ID")
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        data = {
            "split_name": split_name,
            "examples": [
                str(_as_uuid(id_, f"example_ids[{i}]"))
                for i, id_ in enumerate(example_ids)
            ],
            "remove": remove,
        }

        response = self.request_with_retries(
            "PUT", f"/datasets/{_as_uuid(dataset_id, 'dataset_id')}/splits", json=data
        )
        ls_utils.raise_for_status_with_text(response)

    def _resolve_run_id(
        self,
        run: Union[ls_schemas.Run, ls_schemas.RunBase, str, uuid.UUID],
        load_child_runs: bool,
    ) -> ls_schemas.Run:
        """Resolve the run ID.

        Args:
            run (Union[Run, RunBase, str, UUID]):
                The run to resolve.
            load_child_runs (bool):
                Whether to load child runs.

        Returns:
            Run: The resolved run.

        Raises:
            TypeError: If the run type is invalid.
        """
        if isinstance(run, (str, uuid.UUID)):
            run_ = self.read_run(run, load_child_runs=load_child_runs)
        else:
            run_ = cast(ls_schemas.Run, run)
        return run_

    def _resolve_example_id(
        self,
        example: Union[ls_schemas.Example, str, uuid.UUID, dict, None],
        run: ls_schemas.Run,
    ) -> Optional[ls_schemas.Example]:
        """Resolve the example ID.

        Args:
            example (Optional[Union[Example, str, UUID, dict]]):
                The example to resolve.
            run (Run):
                The run associated with the example.

        Returns:
            Optional[Example]: The resolved example.
        """
        if isinstance(example, (str, uuid.UUID)):
            reference_example_ = self.read_example(example)
        elif isinstance(example, ls_schemas.Example):
            reference_example_ = example
        elif isinstance(example, dict):
            reference_example_ = ls_schemas.Example(
                **example,
                _host_url=self._host_url,
                _tenant_id=self._get_optional_tenant_id(),
            )
        elif run.reference_example_id is not None:
            reference_example_ = self.read_example(run.reference_example_id)
        else:
            reference_example_ = None
        return reference_example_

    def _select_eval_results(
        self,
        results: Union[
            ls_evaluator.EvaluationResult, ls_evaluator.EvaluationResults, dict
        ],
        *,
        fn_name: Optional[str] = None,
    ) -> list[ls_evaluator.EvaluationResult]:
        from langsmith.evaluation import evaluator as ls_evaluator  # noqa: F811

        def _cast_result(
            single_result: Union[ls_evaluator.EvaluationResult, dict],
        ) -> ls_evaluator.EvaluationResult:
            if isinstance(single_result, dict):
                return ls_evaluator.EvaluationResult(
                    **{
                        "key": fn_name,
                        "comment": single_result.get("reasoning"),
                        **single_result,
                    }
                )
            return single_result

        def _is_eval_results(results: Any) -> TypeGuard[ls_evaluator.EvaluationResults]:
            return isinstance(results, dict) and "results" in results

        if isinstance(results, ls_evaluator.EvaluationResult):
            results_ = [results]
        elif _is_eval_results(results):
            results_ = [_cast_result(r) for r in results["results"]]
        elif isinstance(results, dict):
            results_ = [_cast_result(cast(dict, results))]
        else:
            raise ValueError(
                f"Invalid evaluation results type: {type(results)}."
                " Must be EvaluationResult, EvaluationResults."
            )
        return results_

    def evaluate_run(
        self,
        run: Union[ls_schemas.Run, ls_schemas.RunBase, str, uuid.UUID],
        evaluator: ls_evaluator.RunEvaluator,
        *,
        source_info: Optional[dict[str, Any]] = None,
        reference_example: Optional[
            Union[ls_schemas.Example, str, dict, uuid.UUID]
        ] = None,
        load_child_runs: bool = False,
    ) -> ls_evaluator.EvaluationResult:
        """Evaluate a run.

        Args:
            run (Union[Run, RunBase, str, UUID]):
                The run to evaluate.
            evaluator (RunEvaluator):
                The evaluator to use.
            source_info (Optional[Dict[str, Any]]):
                Additional information about the source of the evaluation to log
                as feedback metadata.
            reference_example (Optional[Union[Example, str, dict, UUID]]):
                The example to use as a reference for the evaluation.
                If not provided, the run's reference example will be used.
            load_child_runs (bool, default=False):
                Whether to load child runs when resolving the run ID.

        Returns:
            Feedback: The feedback object created by the evaluation.
        """
        run_ = self._resolve_run_id(run, load_child_runs=load_child_runs)
        reference_example_ = self._resolve_example_id(reference_example, run_)
        evaluator_response = evaluator.evaluate_run(
            run_,
            example=reference_example_,
        )
        results = self._log_evaluation_feedback(
            evaluator_response,
            run_,
            source_info=source_info,
        )
        # TODO: Return all results
        return results[0]

    def _log_evaluation_feedback(
        self,
        evaluator_response: Union[
            ls_evaluator.EvaluationResult, ls_evaluator.EvaluationResults, dict
        ],
        run: Optional[ls_schemas.Run] = None,
        source_info: Optional[dict[str, Any]] = None,
        project_id: Optional[ID_TYPE] = None,
        *,
        _executor: Optional[cf.ThreadPoolExecutor] = None,
    ) -> list[ls_evaluator.EvaluationResult]:
        results = self._select_eval_results(evaluator_response)

        def _submit_feedback(**kwargs):
            if _executor:
                _executor.submit(self.create_feedback, **kwargs)
            else:
                self.create_feedback(**kwargs)

        for res in results:
            source_info_ = source_info or {}
            if res.evaluator_info:
                source_info_ = {**res.evaluator_info, **source_info_}
            run_id_ = None
            if res.target_run_id:
                run_id_ = res.target_run_id
            elif run is not None:
                run_id_ = run.id
            error = res.extra.get("error", None) if res.extra is not None else None

            _submit_feedback(
                run_id=run_id_,
                key=res.key,
                score=res.score,
                value=res.value,
                comment=res.comment,
                correction=res.correction,
                source_info=source_info_,
                source_run_id=res.source_run_id,
                feedback_config=cast(
                    Optional[ls_schemas.FeedbackConfig], res.feedback_config
                ),
                feedback_source_type=ls_schemas.FeedbackSourceType.MODEL,
                project_id=project_id,
                extra=res.extra,
                trace_id=run.trace_id if run else None,
                error=error,
            )
        return results

    async def aevaluate_run(
        self,
        run: Union[ls_schemas.Run, str, uuid.UUID],
        evaluator: ls_evaluator.RunEvaluator,
        *,
        source_info: Optional[dict[str, Any]] = None,
        reference_example: Optional[
            Union[ls_schemas.Example, str, dict, uuid.UUID]
        ] = None,
        load_child_runs: bool = False,
    ) -> ls_evaluator.EvaluationResult:
        """Evaluate a run asynchronously.

        Args:
            run (Union[Run, str, UUID]):
                The run to evaluate.
            evaluator (RunEvaluator):
                The evaluator to use.
            source_info (Optional[Dict[str, Any]]):
                Additional information about the source of the evaluation to log
                as feedback metadata.
            reference_example (Optional[Union[Example, str, dict, UUID]]):
                The example to use as a reference for the evaluation.
                If not provided, the run's reference example will be used.
            load_child_runs (bool, default=False)
                Whether to load child runs when resolving the run ID.

        Returns:
            EvaluationResult: The evaluation result object created by the evaluation.
        """
        run_ = self._resolve_run_id(run, load_child_runs=load_child_runs)
        reference_example_ = self._resolve_example_id(reference_example, run_)
        evaluator_response = await evaluator.aevaluate_run(
            run_,
            example=reference_example_,
        )
        # TODO: Return all results and use async API
        results = self._log_evaluation_feedback(
            evaluator_response,
            run_,
            source_info=source_info,
        )
        return results[0]

    def create_feedback(
        self,
        # TODO: make run_id a kwarg and drop default value for 'key' in breaking release.
        run_id: Optional[ID_TYPE] = None,
        key: str = "unnamed",
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[str, dict, None] = None,
        trace_id: Optional[ID_TYPE] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
        source_info: Optional[dict[str, Any]] = None,
        feedback_source_type: Union[
            ls_schemas.FeedbackSourceType, str
        ] = ls_schemas.FeedbackSourceType.API,
        source_run_id: Optional[ID_TYPE] = None,
        feedback_id: Optional[ID_TYPE] = None,
        feedback_config: Optional[ls_schemas.FeedbackConfig] = None,
        stop_after_attempt: int = 10,
        project_id: Optional[ID_TYPE] = None,
        comparative_experiment_id: Optional[ID_TYPE] = None,
        feedback_group_id: Optional[ID_TYPE] = None,
        extra: Optional[dict] = None,
        error: Optional[bool] = None,
        **kwargs: Any,
    ) -> ls_schemas.Feedback:
        """Create feedback for a run.

        **NOTE**: To enable feedback to be batch uploaded in the background you must
        specify trace_id. *We highly encourage this for latency-sensitive environments.*

        Args:
            key (str):
                The name of the feedback metric.
            score (Optional[Union[float, int, bool]]):
                The score to rate this run on the metric or aspect.
            value (Optional[Union[float, int, bool, str, dict]]):
                The display value or non-numeric value for this feedback.
            run_id (Optional[Union[UUID, str]]):
                The ID of the run to provide feedback for. At least one of run_id,
                trace_id, or project_id must be specified.
            trace_id (Optional[Union[UUID, str]]):
                The ID of the trace (i.e. root parent run) of the run to provide
                feedback for (specified by run_id). If run_id and trace_id are the
                same, only trace_id needs to be specified. **NOTE**: trace_id is
                required feedback ingestion to be batched and backgrounded.
            correction (Optional[dict]):
                The proper ground truth for this run.
            comment (Optional[str]):
                A comment about this feedback, such as a justification for the score or
                chain-of-thought trajectory for an LLM judge.
            source_info (Optional[Dict[str, Any]]):
                Information about the source of this feedback.
            feedback_source_type (Union[FeedbackSourceType, str]):
                The type of feedback source, such as model (for model-generated feedback)
                or API.
            source_run_id (Optional[Union[UUID, str]]):
                The ID of the run that generated this feedback, if a "model" type.
            feedback_id (Optional[Union[UUID, str]]):
                The ID of the feedback to create. If not provided, a random UUID will be
                generated.
            feedback_config (Optional[FeedbackConfig]):
                The configuration specifying how to interpret feedback with this key.
                Examples include continuous (with min/max bounds), categorical,
                or freeform.
            stop_after_attempt (int, default=10):
                The number of times to retry the request before giving up.
            project_id (Optional[Union[UUID, str]]):
                The ID of the project (or experiment) to provide feedback on. This is
                used for creating summary metrics for experiments. Cannot specify
                run_id or trace_id if project_id is specified, and vice versa.
            comparative_experiment_id (Optional[Union[UUID, str]]):
                If this feedback was logged as a part of a comparative experiment, this
                associates the feedback with that experiment.
            feedback_group_id (Optional[Union[UUID, str]]):
                When logging preferences, ranking runs, or other comparative feedback,
                this is used to group feedback together.
            extra (Optional[Dict]):
                Metadata for the feedback.
            **kwargs (Any):
                Additional keyword arguments.

        Returns:
            Feedback: The created feedback object.

        Example:
            .. code-block:: python

                from langsmith import trace, traceable, Client


                @traceable
                def foo(x):
                    return {"y": x * 2}


                @traceable
                def bar(y):
                    return {"z": y - 1}


                client = Client()

                inputs = {"x": 1}
                with trace(name="foobar", inputs=inputs) as root_run:
                    result = foo(**inputs)
                    result = bar(**result)
                    root_run.outputs = result
                    trace_id = root_run.id
                    child_runs = root_run.child_runs

                # Provide feedback for a trace (a.k.a. a root run)
                client.create_feedback(
                    key="user_feedback",
                    score=1,
                    trace_id=trace_id,
                )

                # Provide feedback for a child run
                foo_run_id = [run for run in child_runs if run.name == "foo"][0].id
                client.create_feedback(
                    key="correctness",
                    score=0,
                    run_id=foo_run_id,
                    # trace_id= is optional but recommended to enable batched and backgrounded
                    # feedback ingestion.
                    trace_id=trace_id,
                )

        """
        run_id = run_id or trace_id
        if run_id is None and project_id is None:
            raise ValueError("One of run_id, trace_id, or project_id  must be provided")
        if run_id is not None and project_id is not None:
            raise ValueError(
                "project_id cannot be provided if run_id or trace_id is provided"
            )
        if kwargs:
            warnings.warn(
                "The following arguments are no longer used in the create_feedback"
                f" endpoint: {sorted(kwargs)}",
                DeprecationWarning,
            )
        try:
            if not isinstance(feedback_source_type, ls_schemas.FeedbackSourceType):
                feedback_source_type = ls_schemas.FeedbackSourceType(
                    feedback_source_type
                )
            if feedback_source_type == ls_schemas.FeedbackSourceType.API:
                feedback_source: ls_schemas.FeedbackSourceBase = (
                    ls_schemas.APIFeedbackSource(metadata=source_info)
                )
            elif feedback_source_type == ls_schemas.FeedbackSourceType.MODEL:
                feedback_source = ls_schemas.ModelFeedbackSource(metadata=source_info)
            else:
                raise ValueError(f"Unknown feedback source type {feedback_source_type}")
            feedback_source.metadata = (
                feedback_source.metadata if feedback_source.metadata is not None else {}
            )
            if source_run_id is not None and "__run" not in feedback_source.metadata:
                feedback_source.metadata["__run"] = {"run_id": str(source_run_id)}
            if feedback_source.metadata and "__run" in feedback_source.metadata:
                # Validate that the linked run ID is a valid UUID
                # Run info may be a base model or dict.
                _run_meta: Union[dict, Any] = feedback_source.metadata["__run"]
                if hasattr(_run_meta, "dict") and callable(_run_meta):
                    _run_meta = _run_meta.dict()
                if "run_id" in _run_meta:
                    _run_meta["run_id"] = str(
                        _as_uuid(
                            feedback_source.metadata["__run"]["run_id"],
                            "feedback_source.metadata['__run']['run_id']",
                        )
                    )
                feedback_source.metadata["__run"] = _run_meta
            feedback = ls_schemas.FeedbackCreate(
                id=_ensure_uuid(feedback_id),
                # If run_id is None, this is interpreted as session-level
                # feedback.
                run_id=_ensure_uuid(run_id, accept_null=True),
                trace_id=_ensure_uuid(trace_id, accept_null=True),
                key=key,
                score=_format_feedback_score(score),
                value=value,
                correction=correction,
                comment=comment,
                feedback_source=feedback_source,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                modified_at=datetime.datetime.now(datetime.timezone.utc),
                feedback_config=feedback_config,
                session_id=_ensure_uuid(project_id, accept_null=True),
                comparative_experiment_id=_ensure_uuid(
                    comparative_experiment_id, accept_null=True
                ),
                feedback_group_id=_ensure_uuid(feedback_group_id, accept_null=True),
                extra=extra,
                error=error,
            )

            use_multipart = (self.info.batch_ingest_config or {}).get(
                "use_multipart_endpoint", False
            )

            if (
                use_multipart
                and self.info.version  # TODO: Remove version check once versions have updated
                and ls_utils.is_version_greater_or_equal(self.info.version, "0.8.10")
                and (
                    self.tracing_queue is not None or self.compressed_traces is not None
                )
                and feedback.trace_id is not None
                and self.otel_exporter is None
            ):
                serialized_op = serialize_feedback_dict(feedback)
                if self.compressed_traces is not None:
                    multipart_form = (
                        serialized_feedback_operation_to_multipart_parts_and_context(
                            serialized_op
                        )
                    )
                    with self.compressed_traces.lock:
                        compress_multipart_parts_and_context(
                            multipart_form,
                            self.compressed_traces,
                            _BOUNDARY,
                        )
                        self.compressed_traces.trace_count += 1
                        if self._data_available_event:
                            self._data_available_event.set()
                elif self.tracing_queue is not None:
                    self.tracing_queue.put(
                        TracingQueueItem(str(feedback.id), serialized_op)
                    )
            else:
                feedback_block = _dumps_json(feedback.dict(exclude_none=True))
                self.request_with_retries(
                    "POST",
                    "/feedback",
                    request_kwargs={
                        "data": feedback_block,
                    },
                    stop_after_attempt=stop_after_attempt,
                    retry_on=(ls_utils.LangSmithNotFoundError,),
                )
            return ls_schemas.Feedback(**feedback.dict())
        except Exception as e:
            logger.error("Error creating feedback", exc_info=True)
            raise e

    def update_feedback(
        self,
        feedback_id: ID_TYPE,
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
    ) -> None:
        """Update a feedback in the LangSmith API.

        Args:
            feedback_id (Union[UUID, str]):
                The ID of the feedback to update.
            score (Optional[Union[float, int, bool]]):
                The score to update the feedback with.
            value (Optional[Union[float, int, bool, str, dict]]):
                The value to update the feedback with.
            correction (Optional[dict]):
                The correction to update the feedback with.
            comment (Optional[str]):
                The comment to update the feedback with.

        Returns:
            None
        """
        feedback_update: dict[str, Any] = {}
        if score is not None:
            feedback_update["score"] = _format_feedback_score(score)
        if value is not None:
            feedback_update["value"] = value
        if correction is not None:
            feedback_update["correction"] = correction
        if comment is not None:
            feedback_update["comment"] = comment
        response = self.request_with_retries(
            "PATCH",
            f"/feedback/{_as_uuid(feedback_id, 'feedback_id')}",
            headers={**self._headers, "Content-Type": "application/json"},
            data=_dumps_json(feedback_update),
        )
        ls_utils.raise_for_status_with_text(response)

    def read_feedback(self, feedback_id: ID_TYPE) -> ls_schemas.Feedback:
        """Read a feedback from the LangSmith API.

        Args:
            feedback_id (Union[UUID, str]):
                The ID of the feedback to read.

        Returns:
            Feedback: The feedback.
        """
        response = self.request_with_retries(
            "GET",
            f"/feedback/{_as_uuid(feedback_id, 'feedback_id')}",
        )
        return ls_schemas.Feedback(**response.json())

    def list_feedback(
        self,
        *,
        run_ids: Optional[Sequence[ID_TYPE]] = None,
        feedback_key: Optional[Sequence[str]] = None,
        feedback_source_type: Optional[Sequence[ls_schemas.FeedbackSourceType]] = None,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[ls_schemas.Feedback]:
        """List the feedback objects on the LangSmith API.

        Args:
            run_ids (Optional[Sequence[Union[UUID, str]]]):
                The IDs of the runs to filter by.
            feedback_key (Optional[Sequence[str]]):
                The feedback key(s) to filter by. Examples: 'correctness'
                The query performs a union of all feedback keys.
            feedback_source_type (Optional[Sequence[FeedbackSourceType]]):
                The type of feedback source, such as model or API.
            limit (Optional[int]):
                The maximum number of feedback to return.
            **kwargs (Any):
                Additional keyword arguments.

        Yields:
            The feedback objects.
        """
        params: dict = {
            "run": run_ids,
            "limit": min(limit, 100) if limit is not None else 100,
            **kwargs,
        }
        if feedback_key is not None:
            params["key"] = feedback_key
        if feedback_source_type is not None:
            params["source"] = feedback_source_type
        for i, feedback in enumerate(
            self._get_paginated_list("/feedback", params=params)
        ):
            yield ls_schemas.Feedback(**feedback)
            if limit is not None and i + 1 >= limit:
                break

    def delete_feedback(self, feedback_id: ID_TYPE) -> None:
        """Delete a feedback by ID.

        Args:
            feedback_id (Union[UUID, str]):
                The ID of the feedback to delete.

        Returns:
            None
        """
        response = self.request_with_retries(
            "DELETE",
            f"/feedback/{_as_uuid(feedback_id, 'feedback_id')}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def create_feedback_from_token(
        self,
        token_or_url: Union[str, uuid.UUID],
        score: Union[float, int, bool, None] = None,
        *,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Create feedback from a presigned token or URL.

        Args:
            token_or_url (Union[str, uuid.UUID]): The token or URL from which to create
                 feedback.
            score (Optional[Union[float, int, bool]]): The score of the feedback.
                Defaults to None.
            value (Optional[Union[float, int, bool, str, dict]]): The value of the
                feedback. Defaults to None.
            correction (Optional[dict]): The correction of the feedback.
                Defaults to None.
            comment (Optional[str]): The comment of the feedback. Defaults
                to None.
            metadata (Optional[dict]): Additional metadata for the feedback.
                Defaults to None.

        Raises:
            ValueError: If the source API URL is invalid.

        Returns:
            None
        """
        source_api_url, token_uuid = _parse_token_or_url(
            token_or_url, self.api_url, num_parts=1
        )
        if source_api_url != self.api_url:
            raise ValueError(f"Invalid source API URL. {source_api_url}")
        response = self.request_with_retries(
            "POST",
            f"/feedback/tokens/{_as_uuid(token_uuid)}",
            data=_dumps_json(
                {
                    "score": score,
                    "value": value,
                    "correction": correction,
                    "comment": comment,
                    "metadata": metadata,
                    # TODO: Add ID once the API supports it.
                }
            ),
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def create_presigned_feedback_token(
        self,
        run_id: ID_TYPE,
        feedback_key: str,
        *,
        expiration: Optional[datetime.datetime | datetime.timedelta] = None,
        feedback_config: Optional[ls_schemas.FeedbackConfig] = None,
        feedback_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.FeedbackIngestToken:
        """Create a pre-signed URL to send feedback data to.

        This is useful for giving browser-based clients a way to upload
        feedback data directly to LangSmith without accessing the
        API key.

        Args:
            run_id (Union[UUID, str]):
                The ID of the run.
            feedback_key (str):
                The key of the feedback to create.
            expiration (Optional[datetime.datetime | datetime.timedelta]): The expiration time of the pre-signed URL.
                Either a datetime or a timedelta offset from now.
                Default to 3 hours.
            feedback_config (Optional[FeedbackConfig]):
                If creating a feedback_key for the first time,
                this defines how the metric should be interpreted,
                such as a continuous score (w/ optional bounds),
                or distribution over categorical values.
            feedback_id (Optional[Union[UUID, str]): The ID of the feedback to create. If not provided, a new
                feedback will be created.

        Returns:
            FeedbackIngestToken: The pre-signed URL for uploading feedback data.
        """
        body: dict[str, Any] = {
            "run_id": run_id,
            "feedback_key": feedback_key,
            "feedback_config": feedback_config,
            "id": feedback_id or str(uuid.uuid4()),
        }
        if expiration is None:
            body["expires_in"] = ls_schemas.TimeDeltaInput(
                days=0,
                hours=3,
                minutes=0,
            )
        elif isinstance(expiration, datetime.datetime):
            body["expires_at"] = expiration.isoformat()
        elif isinstance(expiration, datetime.timedelta):
            body["expires_in"] = ls_schemas.TimeDeltaInput(
                days=expiration.days,
                hours=expiration.seconds // 3600,
                minutes=(expiration.seconds // 60) % 60,
            )
        else:
            raise ValueError(f"Unknown expiration type: {type(expiration)}")

        response = self.request_with_retries(
            "POST",
            "/feedback/tokens",
            data=_dumps_json(body),
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.FeedbackIngestToken(**response.json())

    def create_presigned_feedback_tokens(
        self,
        run_id: ID_TYPE,
        feedback_keys: Sequence[str],
        *,
        expiration: Optional[datetime.datetime | datetime.timedelta] = None,
        feedback_configs: Optional[
            Sequence[Optional[ls_schemas.FeedbackConfig]]
        ] = None,
    ) -> Sequence[ls_schemas.FeedbackIngestToken]:
        """Create a pre-signed URL to send feedback data to.

        This is useful for giving browser-based clients a way to upload
        feedback data directly to LangSmith without accessing the
        API key.

        Args:
            run_id (Union[UUID, str]):
                The ID of the run.
            feedback_keys (Sequence[str]):
                The key of the feedback to create.
            expiration (Optional[datetime.datetime | datetime.timedelta]): The expiration time of the pre-signed URL.
                Either a datetime or a timedelta offset from now.
                Default to 3 hours.
            feedback_configs (Optional[Sequence[Optional[FeedbackConfig]]]):
                If creating a feedback_key for the first time,
                this defines how the metric should be interpreted,
                such as a continuous score (w/ optional bounds),
                or distribution over categorical values.

        Returns:
            Sequence[FeedbackIngestToken]: The pre-signed URL for uploading feedback data.
        """
        # validate
        if feedback_configs is not None and len(feedback_keys) != len(feedback_configs):
            raise ValueError(
                "The length of feedback_keys and feedback_configs must be the same."
            )
        if not feedback_configs:
            feedback_configs = [None] * len(feedback_keys)
        # build expiry option
        expires_in, expires_at = None, None
        if expiration is None:
            expires_in = ls_schemas.TimeDeltaInput(
                days=0,
                hours=3,
                minutes=0,
            )
        elif isinstance(expiration, datetime.datetime):
            expires_at = expiration.isoformat()
        elif isinstance(expiration, datetime.timedelta):
            expires_in = ls_schemas.TimeDeltaInput(
                days=expiration.days,
                hours=expiration.seconds // 3600,
                minutes=(expiration.seconds // 60) % 60,
            )
        else:
            raise ValueError(f"Unknown expiration type: {type(expiration)}")
        # assemble body, one entry per key
        body = _dumps_json(
            [
                {
                    "run_id": run_id,
                    "feedback_key": feedback_key,
                    "feedback_config": feedback_config,
                    "expires_in": expires_in,
                    "expires_at": expires_at,
                }
                for feedback_key, feedback_config in zip(
                    feedback_keys, feedback_configs
                )
            ]
        )

        def req(api_url: str, api_key: Optional[str]) -> list:
            response = self.request_with_retries(
                "POST",
                f"{api_url}/feedback/tokens",
                request_kwargs={
                    "data": body,
                    "headers": {
                        **self._headers,
                        X_API_KEY: api_key or self.api_key,
                    },
                },
            )
            ls_utils.raise_for_status_with_text(response)
            return response.json()

        tokens = []
        with cf.ThreadPoolExecutor(max_workers=len(self._write_api_urls)) as executor:
            futs = [
                executor.submit(req, api_url, api_key)
                for api_url, api_key in self._write_api_urls.items()
            ]
            for fut in cf.as_completed(futs):
                response = fut.result()
                tokens.extend(
                    [ls_schemas.FeedbackIngestToken(**part) for part in response]
                )
        return tokens

    def list_presigned_feedback_tokens(
        self,
        run_id: ID_TYPE,
        *,
        limit: Optional[int] = None,
    ) -> Iterator[ls_schemas.FeedbackIngestToken]:
        """List the feedback ingest tokens for a run.

        Args:
            run_id (Union[UUID, str]): The ID of the run to filter by.
            limit (Optional[int]): The maximum number of tokens to return.

        Yields:
            The feedback ingest tokens.
        """
        params = {
            "run_id": _as_uuid(run_id, "run_id"),
            "limit": min(limit, 100) if limit is not None else 100,
        }
        for i, token in enumerate(
            self._get_paginated_list("/feedback/tokens", params=params)
        ):
            yield ls_schemas.FeedbackIngestToken(**token)
            if limit is not None and i + 1 >= limit:
                break

    # Annotation Queue API

    def list_annotation_queues(
        self,
        *,
        queue_ids: Optional[list[ID_TYPE]] = None,
        name: Optional[str] = None,
        name_contains: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[ls_schemas.AnnotationQueue]:
        """List the annotation queues on the LangSmith API.

        Args:
            queue_ids (Optional[List[Union[UUID, str]]]):
                The IDs of the queues to filter by.
            name (Optional[str]):
                The name of the queue to filter by.
            name_contains (Optional[str]):
                The substring that the queue name should contain.
            limit (Optional[int]):
                The maximum number of queues to return.

        Yields:
            The annotation queues.
        """
        params: dict = {
            "ids": (
                [_as_uuid(id_, f"queue_ids[{i}]") for i, id_ in enumerate(queue_ids)]
                if queue_ids is not None
                else None
            ),
            "name": name,
            "name_contains": name_contains,
            "limit": min(limit, 100) if limit is not None else 100,
        }
        for i, queue in enumerate(
            self._get_paginated_list("/annotation-queues", params=params)
        ):
            yield ls_schemas.AnnotationQueue(
                **queue,
            )
            if limit is not None and i + 1 >= limit:
                break

    def create_annotation_queue(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        queue_id: Optional[ID_TYPE] = None,
        rubric_instructions: Optional[str] = None,
    ) -> ls_schemas.AnnotationQueueWithDetails:
        """Create an annotation queue on the LangSmith API.

        Args:
            name (str):
                The name of the annotation queue.
            description (Optional[str]):
                The description of the annotation queue.
            queue_id (Optional[Union[UUID, str]]):
                The ID of the annotation queue.
            rubric_instructions (Optional[str]):
                The rubric instructions for the annotation queue.

        Returns:
            AnnotationQueue: The created annotation queue object.
        """
        body = {
            "name": name,
            "description": description,
            "id": str(queue_id) if queue_id is not None else str(uuid.uuid4()),
            "rubric_instructions": rubric_instructions,
        }
        response = self.request_with_retries(
            "POST",
            "/annotation-queues",
            json={k: v for k, v in body.items() if v is not None},
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.AnnotationQueueWithDetails(
            **response.json(),
        )

    def read_annotation_queue(self, queue_id: ID_TYPE) -> ls_schemas.AnnotationQueue:
        """Read an annotation queue with the specified queue ID.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue to read.

        Returns:
            AnnotationQueue: The annotation queue object.
        """
        base_url = f"/annotation-queues/{_as_uuid(queue_id, 'queue_id')}"
        response = self.request_with_retries(
            "GET",
            f"{base_url}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.AnnotationQueueWithDetails(**response.json())

    def update_annotation_queue(
        self,
        queue_id: ID_TYPE,
        *,
        name: str,
        description: Optional[str] = None,
        rubric_instructions: Optional[str] = None,
    ) -> None:
        """Update an annotation queue with the specified queue_id.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue to update.
            name (str): The new name for the annotation queue.
            description (Optional[str]): The new description for the
                annotation queue. Defaults to None.
            rubric_instructions (Optional[str]): The new rubric instructions for the
                annotation queue. Defaults to None.

        Returns:
            None
        """
        response = self.request_with_retries(
            "PATCH",
            f"/annotation-queues/{_as_uuid(queue_id, 'queue_id')}",
            json={
                "name": name,
                "description": description,
                "rubric_instructions": rubric_instructions,
            },
        )
        ls_utils.raise_for_status_with_text(response)

    def delete_annotation_queue(self, queue_id: ID_TYPE) -> None:
        """Delete an annotation queue with the specified queue ID.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue to delete.

        Returns:
            None
        """
        response = self.request_with_retries(
            "DELETE",
            f"/annotation-queues/{_as_uuid(queue_id, 'queue_id')}",
            headers={"Accept": "application/json", **self._headers},
        )
        ls_utils.raise_for_status_with_text(response)

    def add_runs_to_annotation_queue(
        self, queue_id: ID_TYPE, *, run_ids: list[ID_TYPE]
    ) -> None:
        """Add runs to an annotation queue with the specified queue ID.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue.
            run_ids (List[Union[UUID, str]]): The IDs of the runs to be added to the annotation
                queue.

        Returns:
            None
        """
        response = self.request_with_retries(
            "POST",
            f"/annotation-queues/{_as_uuid(queue_id, 'queue_id')}/runs",
            json=[str(_as_uuid(id_, f"run_ids[{i}]")) for i, id_ in enumerate(run_ids)],
        )
        ls_utils.raise_for_status_with_text(response)

    def delete_run_from_annotation_queue(
        self, queue_id: ID_TYPE, *, run_id: ID_TYPE
    ) -> None:
        """Delete a run from an annotation queue with the specified queue ID and run ID.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue.
            run_id (Union[UUID, str]): The ID of the run to be added to the annotation
                queue.

        Returns:
            None
        """
        response = self.request_with_retries(
            "DELETE",
            f"/annotation-queues/{_as_uuid(queue_id, 'queue_id')}/runs/{_as_uuid(run_id, 'run_id')}",
        )
        ls_utils.raise_for_status_with_text(response)

    def get_run_from_annotation_queue(
        self, queue_id: ID_TYPE, *, index: int
    ) -> ls_schemas.RunWithAnnotationQueueInfo:
        """Get a run from an annotation queue at the specified index.

        Args:
            queue_id (Union[UUID, str]): The ID of the annotation queue.
            index (int): The index of the run to retrieve.

        Returns:
            RunWithAnnotationQueueInfo: The run at the specified index.

        Raises:
            LangSmithNotFoundError: If the run is not found at the given index.
            LangSmithError: For other API-related errors.
        """
        base_url = f"/annotation-queues/{_as_uuid(queue_id, 'queue_id')}/run"
        response = self.request_with_retries(
            "GET",
            f"{base_url}/{index}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.RunWithAnnotationQueueInfo(**response.json())

    def create_comparative_experiment(
        self,
        name: str,
        experiments: Sequence[ID_TYPE],
        *,
        reference_dataset: Optional[ID_TYPE] = None,
        description: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
        id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.ComparativeExperiment:
        """Create a comparative experiment on the LangSmith API.

        These experiments compare 2 or more experiment results over a shared dataset.

        Args:
            name (str): The name of the comparative experiment.
            experiments (Sequence[Union[UUID, str]]): The IDs of the experiments to compare.
            reference_dataset (Optional[Union[UUID, str]]): The ID of the dataset these experiments are compared on.
            description (Optional[str]): The description of the comparative experiment.
            created_at (Optional[datetime.datetime]): The creation time of the comparative experiment.
            metadata (Optional[Dict[str, Any]]): Additional metadata for the comparative experiment.
            id (Optional[Union[UUID, str]]): The ID of the comparative experiment.

        Returns:
            ComparativeExperiment: The created comparative experiment object.
        """
        if not experiments:
            raise ValueError("At least one experiment is required.")
        if reference_dataset is None:
            # Get one of the experiments' reference dataset
            reference_dataset = self.read_project(
                project_id=experiments[0]
            ).reference_dataset_id
        if not reference_dataset:
            raise ValueError("A reference dataset is required.")
        body: dict[str, Any] = {
            "id": id or str(uuid.uuid4()),
            "name": name,
            "experiment_ids": experiments,
            "reference_dataset_id": reference_dataset,
            "description": description,
            "created_at": created_at or datetime.datetime.now(datetime.timezone.utc),
            "extra": {},
        }
        if metadata is not None:
            body["extra"]["metadata"] = metadata
        ser = _dumps_json({k: v for k, v in body.items()})  # if v is not None})
        response = self.request_with_retries(
            "POST",
            "/datasets/comparative",
            request_kwargs={
                "data": ser,
            },
        )
        ls_utils.raise_for_status_with_text(response)
        response_d = response.json()
        return ls_schemas.ComparativeExperiment(**response_d)

    async def arun_on_dataset(
        self,
        dataset_name: str,
        llm_or_chain_factory: Any,
        *,
        evaluation: Optional[Any] = None,
        concurrency_level: int = 5,
        project_name: Optional[str] = None,
        project_metadata: Optional[dict[str, Any]] = None,
        dataset_version: Optional[Union[datetime.datetime, str]] = None,
        verbose: bool = False,
        input_mapper: Optional[Callable[[dict], Any]] = None,
        revision_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Asynchronously run the Chain or language model on a dataset.

        .. deprecated:: 0.1.0

           This method is deprecated. Use :func:`langsmith.aevaluate` instead.
        """  # noqa: E501
        warnings.warn(
            "The `arun_on_dataset` method is deprecated and"
            " will be removed in a future version."
            "Please use the `aevaluate` method instead.",
            DeprecationWarning,
        )
        try:
            from langchain.smith import arun_on_dataset as _arun_on_dataset
        except ImportError:
            raise ImportError(
                "The client.arun_on_dataset function requires the langchain"
                "package to run.\nInstall with pip install langchain"
            )
        return await _arun_on_dataset(
            dataset_name=dataset_name,
            llm_or_chain_factory=llm_or_chain_factory,
            client=self,
            evaluation=evaluation,
            concurrency_level=concurrency_level,
            project_name=project_name,
            project_metadata=project_metadata,
            verbose=verbose,
            input_mapper=input_mapper,
            revision_id=revision_id,
            dataset_version=dataset_version,
            **kwargs,
        )

    def run_on_dataset(
        self,
        dataset_name: str,
        llm_or_chain_factory: Any,
        *,
        evaluation: Optional[Any] = None,
        concurrency_level: int = 5,
        project_name: Optional[str] = None,
        project_metadata: Optional[dict[str, Any]] = None,
        dataset_version: Optional[Union[datetime.datetime, str]] = None,
        verbose: bool = False,
        input_mapper: Optional[Callable[[dict], Any]] = None,
        revision_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run the Chain or language model on a dataset.

        .. deprecated:: 0.1.0

           This method is deprecated. Use :func:`langsmith.aevaluate` instead.
        """  # noqa: E501  # noqa: E501
        warnings.warn(
            "The `run_on_dataset` method is deprecated and"
            " will be removed in a future version."
            "Please use the `evaluate` method instead.",
            DeprecationWarning,
        )
        try:
            from langchain.smith import (
                run_on_dataset as _run_on_dataset,  # type: ignore
            )
        except ImportError:
            raise ImportError(
                "The client.run_on_dataset function requires the langchain"
                "package to run.\nInstall with pip install langchain"
            )
        return _run_on_dataset(
            dataset_name=dataset_name,
            llm_or_chain_factory=llm_or_chain_factory,
            concurrency_level=concurrency_level,
            client=self,
            evaluation=evaluation,
            project_name=project_name,
            project_metadata=project_metadata,
            verbose=verbose,
            input_mapper=input_mapper,
            revision_id=revision_id,
            dataset_version=dataset_version,
            **kwargs,
        )

    def _current_tenant_is_owner(self, owner: str) -> bool:
        """Check if the current workspace has the same handle as owner.

        Args:
            owner (str): The owner to check against.

        Returns:
            bool: True if the current tenant is the owner, False otherwise.
        """
        settings = self._get_settings()
        return owner == "-" or settings.tenant_handle == owner

    def _owner_conflict_error(
        self, action: str, owner: str
    ) -> ls_utils.LangSmithUserError:
        return ls_utils.LangSmithUserError(
            f"Cannot {action} for another tenant.\n"
            f"Current tenant: {self._get_settings().tenant_handle},\n"
            f"Requested tenant: {owner}"
        )

    def _get_latest_commit_hash(
        self, prompt_owner_and_name: str, limit: int = 1, offset: int = 0
    ) -> Optional[str]:
        """Get the latest commit hash for a prompt.

        Args:
            prompt_owner_and_name (str): The owner and name of the prompt.
            limit (int, default=1): The maximum number of commits to fetch. Defaults to 1.
            offset (int, default=0): The number of commits to skip. Defaults to 0.

        Returns:
            Optional[str]: The latest commit hash, or None if no commits are found.
        """
        response = self.request_with_retries(
            "GET",
            f"/commits/{prompt_owner_and_name}/",
            params={"limit": limit, "offset": offset},
        )
        commits = response.json()["commits"]
        return commits[0]["commit_hash"] if commits else None

    def _like_or_unlike_prompt(
        self, prompt_identifier: str, like: bool
    ) -> dict[str, int]:
        """Like or unlike a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.
            like (bool): True to like the prompt, False to unlike it.

        Returns:
            A dictionary with the key 'likes' and the count of likes as the value.

        Raises:
            requests.exceptions.HTTPError: If the prompt is not found or
            another error occurs.
        """
        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        response = self.request_with_retries(
            "POST", f"/likes/{owner}/{prompt_name}", json={"like": like}
        )
        response.raise_for_status()
        return response.json()

    def _get_prompt_url(self, prompt_identifier: str) -> str:
        """Get a URL for a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            str: The URL for the prompt.

        """
        owner, prompt_name, commit_hash = ls_utils.parse_prompt_identifier(
            prompt_identifier
        )

        if not self._current_tenant_is_owner(owner):
            return f"{self._host_url}/hub/{owner}/{prompt_name}:{commit_hash[:8]}"

        settings = self._get_settings()
        return (
            f"{self._host_url}/prompts/{prompt_name}/{commit_hash[:8]}"
            f"?organizationId={settings.id}"
        )

    def _prompt_exists(self, prompt_identifier: str) -> bool:
        """Check if a prompt exists.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            bool: True if the prompt exists, False otherwise.
        """
        prompt = self.get_prompt(prompt_identifier)
        return True if prompt else False

    def like_prompt(self, prompt_identifier: str) -> dict[str, int]:
        """Like a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            Dict[str, int]: A dictionary with the key 'likes' and the count of likes as the value.

        """
        return self._like_or_unlike_prompt(prompt_identifier, like=True)

    def unlike_prompt(self, prompt_identifier: str) -> dict[str, int]:
        """Unlike a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            Dict[str, int]: A dictionary with the key 'likes' and the count of likes as the value.

        """
        return self._like_or_unlike_prompt(prompt_identifier, like=False)

    def list_prompts(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        is_public: Optional[bool] = None,
        is_archived: Optional[bool] = False,
        sort_field: ls_schemas.PromptSortField = ls_schemas.PromptSortField.updated_at,
        sort_direction: Literal["desc", "asc"] = "desc",
        query: Optional[str] = None,
    ) -> ls_schemas.ListPromptsResponse:
        """List prompts with pagination.

        Args:
            limit (int, default=100): The maximum number of prompts to return. Defaults to 100.
            offset (int, default=0): The number of prompts to skip. Defaults to 0.
            is_public (Optional[bool]): Filter prompts by if they are public.
            is_archived (Optional[bool]): Filter prompts by if they are archived.
            sort_field (PromptSortField): The field to sort by.
              Defaults to "updated_at".
            sort_direction (Literal["desc", "asc"], default="desc"): The order to sort by.
              Defaults to "desc".
            query (Optional[str]): Filter prompts by a search query.

        Returns:
            ListPromptsResponse: A response object containing
            the list of prompts.
        """
        params = {
            "limit": limit,
            "offset": offset,
            "is_public": (
                "true" if is_public else "false" if is_public is not None else None
            ),
            "is_archived": "true" if is_archived else "false",
            "sort_field": sort_field,
            "sort_direction": sort_direction,
            "query": query,
            "match_prefix": "true" if query else None,
        }

        response = self.request_with_retries("GET", "/repos/", params=params)
        return ls_schemas.ListPromptsResponse(**response.json())

    def get_prompt(self, prompt_identifier: str) -> Optional[ls_schemas.Prompt]:
        """Get a specific prompt by its identifier.

        Args:
            prompt_identifier (str): The identifier of the prompt.
                The identifier should be in the format "prompt_name" or "owner/prompt_name".

        Returns:
            Optional[Prompt]: The prompt object.

        Raises:
            requests.exceptions.HTTPError: If the prompt is not found or
                another error occurs.
        """
        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        try:
            response = self.request_with_retries("GET", f"/repos/{owner}/{prompt_name}")
            return ls_schemas.Prompt(**response.json()["repo"])
        except ls_utils.LangSmithNotFoundError:
            return None

    def create_prompt(
        self,
        prompt_identifier: str,
        *,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        is_public: bool = False,
    ) -> ls_schemas.Prompt:
        """Create a new prompt.

        Does not attach prompt object, just creates an empty prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.
                The identifier should be in the formatof owner/name:hash, name:hash, owner/name, or name
            description (Optional[str]): A description of the prompt.
            readme (Optional[str]): A readme for the prompt.
            tags (Optional[Sequence[str]]): A list of tags for the prompt.
            is_public (bool): Whether the prompt should be public. Defaults to False.

        Returns:
            Prompt: The created prompt object.

        Raises:
            ValueError: If the current tenant is not the owner.
            HTTPError: If the server request fails.
        """
        settings = self._get_settings()
        if is_public and not settings.tenant_handle:
            raise ls_utils.LangSmithUserError(
                "Cannot create a public prompt without first\n"
                "creating a LangChain Hub handle. "
                "You can add a handle by creating a public prompt at:\n"
                "https://smith.langchain.com/prompts"
            )

        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        if not self._current_tenant_is_owner(owner=owner):
            raise self._owner_conflict_error("create a prompt", owner)

        json: dict[str, Union[str, bool, Sequence[str]]] = {
            "repo_handle": prompt_name,
            "description": description or "",
            "readme": readme or "",
            "tags": tags or [],
            "is_public": is_public,
        }

        response = self.request_with_retries("POST", "/repos/", json=json)
        response.raise_for_status()
        return ls_schemas.Prompt(**response.json()["repo"])

    def create_commit(
        self,
        prompt_identifier: str,
        object: Any,
        *,
        parent_commit_hash: Optional[str] = None,
    ) -> str:
        """Create a commit for an existing prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt.
            object (Any): The LangChain object to commit.
            parent_commit_hash (Optional[str]): The hash of the parent commit.
                Defaults to latest commit.

        Returns:
            str: The url of the prompt commit.

        Raises:
            HTTPError: If the server request fails.
            ValueError: If the prompt does not exist.
        """
        if not self._prompt_exists(prompt_identifier):
            raise ls_utils.LangSmithNotFoundError(
                "Prompt does not exist, you must create it first."
            )

        try:
            from langchain_core.load.dump import dumps
        except ImportError:
            raise ImportError(
                "The client.create_commit function requires the langchain_core"
                "package to run.\nInstall with `pip install langchain_core`"
            )

        json_object = dumps(object)
        manifest_dict = json.loads(json_object)

        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        prompt_owner_and_name = f"{owner}/{prompt_name}"

        if parent_commit_hash == "latest" or parent_commit_hash is None:
            parent_commit_hash = self._get_latest_commit_hash(prompt_owner_and_name)

        request_dict = {"parent_commit": parent_commit_hash, "manifest": manifest_dict}
        response = self.request_with_retries(
            "POST", f"/commits/{prompt_owner_and_name}", json=request_dict
        )

        commit_hash = response.json()["commit"]["commit_hash"]

        return self._get_prompt_url(f"{prompt_owner_and_name}:{commit_hash}")

    def update_prompt(
        self,
        prompt_identifier: str,
        *,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        is_public: Optional[bool] = None,
        is_archived: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Update a prompt's metadata.

        To update the content of a prompt, use push_prompt or create_commit instead.

        Args:
            prompt_identifier (str): The identifier of the prompt to update.
            description (Optional[str]): New description for the prompt.
            readme (Optional[str]): New readme for the prompt.
            tags (Optional[Sequence[str]]): New list of tags for the prompt.
            is_public (Optional[bool]): New public status for the prompt.
            is_archived (Optional[bool]): New archived status for the prompt.

        Returns:
            Dict[str, Any]: The updated prompt data as returned by the server.

        Raises:
            ValueError: If the prompt_identifier is empty.
            HTTPError: If the server request fails.
        """
        settings = self._get_settings()
        if is_public and not settings.tenant_handle:
            raise ValueError(
                "Cannot create a public prompt without first\n"
                "creating a LangChain Hub handle. "
                "You can add a handle by creating a public prompt at:\n"
                "https://smith.langchain.com/prompts"
            )

        json: dict[str, Union[str, bool, Sequence[str]]] = {}

        if description is not None:
            json["description"] = description
        if readme is not None:
            json["readme"] = readme
        if is_public is not None:
            json["is_public"] = is_public
        if is_archived is not None:
            json["is_archived"] = is_archived
        if tags is not None:
            json["tags"] = tags

        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        response = self.request_with_retries(
            "PATCH", f"/repos/{owner}/{prompt_name}", json=json
        )
        response.raise_for_status()
        return response.json()

    def delete_prompt(self, prompt_identifier: str) -> None:
        """Delete a prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt to delete.

        Returns:
            bool: True if the prompt was successfully deleted, False otherwise.

        Raises:
            ValueError: If the current tenant is not the owner of the prompt.
        """
        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)
        if not self._current_tenant_is_owner(owner):
            raise self._owner_conflict_error("delete a prompt", owner)

        response = self.request_with_retries("DELETE", f"/repos/{owner}/{prompt_name}")
        response.raise_for_status()

    def pull_prompt_commit(
        self,
        prompt_identifier: str,
        *,
        include_model: Optional[bool] = False,
    ) -> ls_schemas.PromptCommit:
        """Pull a prompt object from the LangSmith API.

        Args:
            prompt_identifier (str): The identifier of the prompt.

        Returns:
            PromptCommit: The prompt object.

        Raises:
            ValueError: If no commits are found for the prompt.
        """
        owner, prompt_name, commit_hash = ls_utils.parse_prompt_identifier(
            prompt_identifier
        )
        response = self.request_with_retries(
            "GET",
            (
                f"/commits/{owner}/{prompt_name}/{commit_hash}"
                f"{'?include_model=true' if include_model else ''}"
            ),
        )
        return ls_schemas.PromptCommit(
            **{"owner": owner, "repo": prompt_name, **response.json()}
        )

    def list_prompt_commits(
        self,
        prompt_identifier: str,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
        include_model: bool = False,
    ) -> Iterator[ls_schemas.ListedPromptCommit]:
        """List commits for a given prompt.

        Args:
            prompt_identifier (str): The identifier of the prompt in the format 'owner/repo_name'.
            limit (Optional[int]): The maximum number of commits to return. If None, returns all commits. Defaults to None.
            offset (int, default=0): The number of commits to skip before starting to return results. Defaults to 0.
            include_model (bool, default=False): Whether to include the model information in the commit data. Defaults to False.

        Yields:
            A ListedPromptCommit object for each commit.

        Note:
            This method uses pagination to retrieve commits. It will make multiple API calls if necessary to retrieve all commits
            or up to the specified limit.
        """
        owner, prompt_name, _ = ls_utils.parse_prompt_identifier(prompt_identifier)

        params = {
            "limit": min(100, limit) if limit is not None else limit,
            "offset": offset,
            "include_model": include_model,
        }
        i = 0
        while True:
            params["offset"] = offset
            response = self.request_with_retries(
                "GET",
                f"/commits/{owner}/{prompt_name}/",
                params=params,
            )
            val = response.json()
            items = val["commits"]
            total = val["total"]

            if not items:
                break
            for it in items:
                if limit is not None and i >= limit:
                    return  # Stop iteration if we've reached the limit
                yield ls_schemas.ListedPromptCommit(
                    **{"owner": owner, "repo": prompt_name, **it}
                )
                i += 1

            offset += len(items)
            if offset >= total:
                break

    def pull_prompt(
        self, prompt_identifier: str, *, include_model: Optional[bool] = False
    ) -> Any:
        """Pull a prompt and return it as a LangChain PromptTemplate.

        This method requires `langchain_core`.

        Args:
            prompt_identifier (str): The identifier of the prompt.
            include_model (Optional[bool], default=False): Whether to include the model information in the prompt data.

        Returns:
            Any: The prompt object in the specified format.
        """
        try:
            from langchain_core.language_models.base import BaseLanguageModel
            from langchain_core.load.load import loads
            from langchain_core.output_parsers import BaseOutputParser
            from langchain_core.prompts import BasePromptTemplate
            from langchain_core.prompts.structured import StructuredPrompt
            from langchain_core.runnables.base import RunnableBinding, RunnableSequence
        except ImportError:
            raise ImportError(
                "The client.pull_prompt function requires the langchain_core"
                "package to run.\nInstall with `pip install langchain_core`"
            )
        try:
            from langchain_core._api import suppress_langchain_beta_warning
        except ImportError:

            @contextlib.contextmanager
            def suppress_langchain_beta_warning():
                yield

        prompt_object = self.pull_prompt_commit(
            prompt_identifier, include_model=include_model
        )
        with suppress_langchain_beta_warning():
            prompt = loads(json.dumps(prompt_object.manifest))

        if (
            isinstance(prompt, BasePromptTemplate)
            or isinstance(prompt, RunnableSequence)
            and isinstance(prompt.first, BasePromptTemplate)
        ):
            prompt_template = (
                prompt
                if isinstance(prompt, BasePromptTemplate)
                else (
                    prompt.first
                    if isinstance(prompt, RunnableSequence)
                    and isinstance(prompt.first, BasePromptTemplate)
                    else None
                )
            )
            if prompt_template is None:
                raise ls_utils.LangSmithError(
                    "Prompt object is not a valid prompt template."
                )

            if prompt_template.metadata is None:
                prompt_template.metadata = {}
            prompt_template.metadata.update(
                {
                    "lc_hub_owner": prompt_object.owner,
                    "lc_hub_repo": prompt_object.repo,
                    "lc_hub_commit_hash": prompt_object.commit_hash,
                }
            )
        if (
            include_model
            and isinstance(prompt, RunnableSequence)
            and isinstance(prompt.first, StructuredPrompt)
            # Make forward-compatible in case we let update the response type
            and (
                len(prompt.steps) == 2 and not isinstance(prompt.last, BaseOutputParser)
            )
        ):
            if isinstance(prompt.last, RunnableBinding) and isinstance(
                prompt.last.bound, BaseLanguageModel
            ):
                seq = cast(RunnableSequence, prompt.first | prompt.last.bound)
                if len(seq.steps) == 3:  # prompt | bound llm | output parser
                    rebound_llm = seq.steps[1]
                    prompt = RunnableSequence(
                        prompt.first,
                        rebound_llm.bind(**{**prompt.last.kwargs}),
                        seq.last,
                    )
                else:
                    prompt = seq  # Not sure

            elif isinstance(prompt.last, BaseLanguageModel):
                prompt: RunnableSequence = prompt.first | prompt.last  # type: ignore[no-redef, assignment]
            else:
                pass

        return prompt

    def push_prompt(
        self,
        prompt_identifier: str,
        *,
        object: Optional[Any] = None,
        parent_commit_hash: str = "latest",
        is_public: Optional[bool] = None,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> str:
        """Push a prompt to the LangSmith API.

        Can be used to update prompt metadata or prompt content.

        If the prompt does not exist, it will be created.
        If the prompt exists, it will be updated.

        Args:
            prompt_identifier (str): The identifier of the prompt.
            object (Optional[Any]): The LangChain object to push.
            parent_commit_hash (str): The parent commit hash.
              Defaults to "latest".
            is_public (Optional[bool]): Whether the prompt should be public.
                If None (default), the current visibility status is maintained for existing prompts.
                For new prompts, None defaults to private.
                Set to True to make public, or False to make private.
            description (Optional[str]): A description of the prompt.
              Defaults to an empty string.
            readme (Optional[str]): A readme for the prompt.
              Defaults to an empty string.
            tags (Optional[Sequence[str]]): A list of tags for the prompt.
              Defaults to an empty list.

        Returns:
            str: The URL of the prompt.
        """
        # Create or update prompt metadata
        if self._prompt_exists(prompt_identifier):
            if any(
                param is not None for param in [is_public, description, readme, tags]
            ):
                self.update_prompt(
                    prompt_identifier,
                    description=description,
                    readme=readme,
                    tags=tags,
                    is_public=is_public,
                )
        else:
            self.create_prompt(
                prompt_identifier,
                is_public=is_public if is_public is not None else False,
                description=description,
                readme=readme,
                tags=tags,
            )

        if object is None:
            return self._get_prompt_url(prompt_identifier=prompt_identifier)

        # Create a commit with the new manifest
        url = self.create_commit(
            prompt_identifier,
            object,
            parent_commit_hash=parent_commit_hash,
        )
        return url

    def cleanup(self) -> None:
        """Manually trigger cleanup of the background thread."""
        self._manual_cleanup = True

    @overload
    def evaluate(
        self,
        target: Union[TARGET_T, Runnable, EXPERIMENT_T],
        /,
        data: Optional[DATA_T] = None,
        evaluators: Optional[Sequence[EVALUATOR_T]] = None,
        summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
        metadata: Optional[dict] = None,
        experiment_prefix: Optional[str] = None,
        description: Optional[str] = None,
        max_concurrency: Optional[int] = 0,
        num_repetitions: int = 1,
        blocking: bool = True,
        experiment: Optional[EXPERIMENT_T] = None,
        upload_results: bool = True,
        **kwargs: Any,
    ) -> ExperimentResults: ...

    @overload
    def evaluate(
        self,
        target: Union[tuple[EXPERIMENT_T, EXPERIMENT_T]],
        /,
        data: Optional[DATA_T] = None,
        evaluators: Optional[Sequence[COMPARATIVE_EVALUATOR_T]] = None,
        summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
        metadata: Optional[dict] = None,
        experiment_prefix: Optional[str] = None,
        description: Optional[str] = None,
        max_concurrency: Optional[int] = 0,
        num_repetitions: int = 1,
        blocking: bool = True,
        experiment: Optional[EXPERIMENT_T] = None,
        upload_results: bool = True,
        **kwargs: Any,
    ) -> ComparativeExperimentResults: ...

    def evaluate(
        self,
        target: Union[
            TARGET_T, Runnable, EXPERIMENT_T, tuple[EXPERIMENT_T, EXPERIMENT_T]
        ],
        /,
        data: Optional[DATA_T] = None,
        evaluators: Optional[
            Union[Sequence[EVALUATOR_T], Sequence[COMPARATIVE_EVALUATOR_T]]
        ] = None,
        summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
        metadata: Optional[dict] = None,
        experiment_prefix: Optional[str] = None,
        description: Optional[str] = None,
        max_concurrency: Optional[int] = 0,
        num_repetitions: int = 1,
        blocking: bool = True,
        experiment: Optional[EXPERIMENT_T] = None,
        upload_results: bool = True,
        error_handling: Literal["log", "ignore"] = "log",
        **kwargs: Any,
    ) -> Union[ExperimentResults, ComparativeExperimentResults]:
        r"""Evaluate a target system on a given dataset.

        Args:
            target (Union[TARGET_T, Runnable, EXPERIMENT_T, Tuple[EXPERIMENT_T, EXPERIMENT_T]]):
                The target system or experiment(s) to evaluate. Can be a function
                that takes a dict and returns a dict, a langchain Runnable, an
                existing experiment ID, or a two-tuple of experiment IDs.
            data (DATA_T): The dataset to evaluate on. Can be a dataset name, a list of
                examples, or a generator of examples.
            evaluators (Optional[Union[Sequence[EVALUATOR_T], Sequence[COMPARATIVE_EVALUATOR_T]]]):
                A list of evaluators to run on each example. The evaluator signature
                depends on the target type. Default to None.
            summary_evaluators (Optional[Sequence[SUMMARY_EVALUATOR_T]]): A list of summary
                evaluators to run on the entire dataset. Should not be specified if
                comparing two existing experiments. Defaults to None.
            metadata (Optional[dict]): Metadata to attach to the experiment.
                Defaults to None.
            experiment_prefix (Optional[str]): A prefix to provide for your experiment name.
                Defaults to None.
            description (Optional[str]): A free-form text description for the experiment.
            max_concurrency (Optional[int], default=0): The maximum number of concurrent
                evaluations to run. If None then no limit is set. If 0 then no concurrency.
                Defaults to 0.
            blocking (bool, default=True): Whether to block until the evaluation is complete.
                Defaults to True.
            num_repetitions (int, default=1): The number of times to run the evaluation.
                Each item in the dataset will be run and evaluated this many times.
                Defaults to 1.
            experiment (Optional[EXPERIMENT_T]): An existing experiment to
                extend. If provided, experiment_prefix is ignored. For advanced
                usage only. Should not be specified if target is an existing experiment or
                two-tuple fo experiments.
            upload_results (bool, default=True): Whether to upload the results to LangSmith.
                Defaults to True.
            error_handling (str, default="log"): How to handle individual run errors. 'log'
                will trace the runs with the error message as part of the experiment,
                'ignore' will not count the run as part of the experiment at all.
            **kwargs (Any): Additional keyword arguments to pass to the evaluator.

        Returns:
            ExperimentResults: If target is a function, Runnable, or existing experiment.
            ComparativeExperimentResults: If target is a two-tuple of existing experiments.

        Examples:
            Prepare the dataset:

            .. code-block:: python

                from langsmith import Client

                client = Client()
                dataset = client.clone_public_dataset(
                    "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
                )
                dataset_name = "Evaluate Examples"

            Basic usage:

            .. code-block:: python

                def accuracy(outputs: dict, reference_outputs: dict) -> dict:
                    # Row-level evaluator for accuracy.
                    pred = outputs["response"]
                    expected = reference_outputs["answer"]
                    return {"score": expected.lower() == pred.lower()}

            .. code-block:: python

                def precision(outputs: list[dict], reference_outputs: list[dict]) -> dict:
                    # Experiment-level evaluator for precision.
                    # TP / (TP + FP)
                    predictions = [out["response"].lower() for out in outputs]
                    expected = [ref["answer"].lower() for ref in reference_outputs]
                    # yes and no are the only possible answers
                    tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
                    fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
                    return {"score": tp / (tp + fp)}


                def predict(inputs: dict) -> dict:
                    # This can be any function or just an API call to your app.
                    return {"response": "Yes"}


                results = client.evaluate(
                    predict,
                    data=dataset_name,
                    evaluators=[accuracy],
                    summary_evaluators=[precision],
                    experiment_prefix="My Experiment",
                    description="Evaluating the accuracy of a simple prediction model.",
                    metadata={
                        "my-prompt-version": "abcd-1234",
                    },
                )

            Evaluating over only a subset of the examples

            .. code-block:: python

                experiment_name = results.experiment_name
                examples = client.list_examples(dataset_name=dataset_name, limit=5)
                results = client.evaluate(
                    predict,
                    data=examples,
                    evaluators=[accuracy],
                    summary_evaluators=[precision],
                    experiment_prefix="My Experiment",
                    description="Just testing a subset synchronously.",
                )

            Streaming each prediction to more easily + eagerly debug.

            .. code-block:: python

                results = client.evaluate(
                    predict,
                    data=dataset_name,
                    evaluators=[accuracy],
                    summary_evaluators=[precision],
                    description="I don't even have to block!",
                    blocking=False,
                )
                for i, result in enumerate(results):  # doctest: +ELLIPSIS
                    pass

            Using the `evaluate` API with an off-the-shelf LangChain evaluator:

            .. code-block:: python

                from langsmith.evaluation import LangChainStringEvaluator
                from langchain.chat_models import init_chat_model


                def prepare_criteria_data(run: Run, example: Example):
                    return {
                        "prediction": run.outputs["output"],
                        "reference": example.outputs["answer"],
                        "input": str(example.inputs),
                    }


                results = client.evaluate(
                    predict,
                    data=dataset_name,
                    evaluators=[
                        accuracy,
                        LangChainStringEvaluator("embedding_distance"),
                        LangChainStringEvaluator(
                            "labeled_criteria",
                            config={
                                "criteria": {
                                    "usefulness": "The prediction is useful if it is correct"
                                    " and/or asks a useful followup question."
                                },
                                "llm": init_chat_model("gpt-4o"),
                            },
                            prepare_data=prepare_criteria_data,
                        ),
                    ],
                    description="Evaluating with off-the-shelf LangChain evaluators.",
                    summary_evaluators=[precision],
                )

            View the evaluation results for experiment:...
            Evaluating a LangChain object:

            .. code-block:: python

                from langchain_core.runnables import chain as as_runnable


                @as_runnable
                def nested_predict(inputs):
                    return {"response": "Yes"}


                @as_runnable
                def lc_predict(inputs):
                    return nested_predict.invoke(inputs)


                results = client.evaluate(
                    lc_predict,
                    data=dataset_name,
                    evaluators=[accuracy],
                    description="This time we're evaluating a LangChain object.",
                    summary_evaluators=[precision],
                )

            Comparative evaluation:

            .. code-block:: python

                results = client.evaluate(
                    # The target is a tuple of the experiment IDs to compare
                    target=(
                        "12345678-1234-1234-1234-123456789012",
                        "98765432-1234-1234-1234-123456789012",
                    ),
                    evaluators=[accuracy],
                    summary_evaluators=[precision],
                )

            Evaluate an existing experiment:

            .. code-block:: python

                results = client.evaluate(
                    # The target is the ID of the experiment we are evaluating
                    target="12345678-1234-1234-1234-123456789012",
                    evaluators=[accuracy],
                    summary_evaluators=[precision],
                )


        .. versionadded:: 0.2.0
        """  # noqa: E501
        from langsmith.evaluation._runner import evaluate as evaluate_

        # Need to ignore because it fails when there are too many union types +
        # overloads.
        return evaluate_(  # type: ignore[misc]
            target,  # type: ignore[arg-type]
            data=data,
            evaluators=evaluators,  # type: ignore[arg-type]
            summary_evaluators=summary_evaluators,
            metadata=metadata,
            experiment_prefix=experiment_prefix,
            description=description,
            max_concurrency=max_concurrency,
            num_repetitions=num_repetitions,
            client=self,
            blocking=blocking,
            experiment=experiment,
            upload_results=upload_results,
            error_handling=error_handling,
            **kwargs,
        )

    async def aevaluate(
        self,
        target: Union[
            ATARGET_T,
            AsyncIterable[dict],
            Runnable,
            str,
            uuid.UUID,
            schemas.TracerSession,
        ],
        /,
        data: Union[
            DATA_T, AsyncIterable[schemas.Example], Iterable[schemas.Example], None
        ] = None,
        evaluators: Optional[Sequence[Union[EVALUATOR_T, AEVALUATOR_T]]] = None,
        summary_evaluators: Optional[Sequence[SUMMARY_EVALUATOR_T]] = None,
        metadata: Optional[dict] = None,
        experiment_prefix: Optional[str] = None,
        description: Optional[str] = None,
        max_concurrency: Optional[int] = 0,
        num_repetitions: int = 1,
        blocking: bool = True,
        experiment: Optional[Union[schemas.TracerSession, str, uuid.UUID]] = None,
        upload_results: bool = True,
        error_handling: Literal["log", "ignore"] = "log",
        **kwargs: Any,
    ) -> AsyncExperimentResults:
        r"""Evaluate an async target system on a given dataset.

        Args:
            target (Union[ATARGET_T, AsyncIterable[dict], Runnable, str, uuid.UUID, TracerSession]):
                The target system or experiment(s) to evaluate. Can be an async function
                that takes a dict and returns a dict, a langchain Runnable, an
                existing experiment ID, or a two-tuple of experiment IDs.
            data (Union[DATA_T, AsyncIterable[Example]]): The dataset to evaluate on. Can be a dataset name, a list of
                examples, an async generator of examples, or an async iterable of examples.
            evaluators (Optional[Sequence[EVALUATOR_T]]): A list of evaluators to run
                on each example. Defaults to None.
            summary_evaluators (Optional[Sequence[SUMMARY_EVALUATOR_T]]): A list of summary
                evaluators to run on the entire dataset. Defaults to None.
            metadata (Optional[dict]): Metadata to attach to the experiment.
                Defaults to None.
            experiment_prefix (Optional[str]): A prefix to provide for your experiment name.
                Defaults to None.
            description (Optional[str]): A description of the experiment.
            max_concurrency (Optional[int], default=0): The maximum number of concurrent
                evaluations to run. If None then no limit is set. If 0 then no concurrency.
                Defaults to 0.
            num_repetitions (int, default=1): The number of times to run the evaluation.
                Each item in the dataset will be run and evaluated this many times.
                Defaults to 1.
            blocking (bool, default=True): Whether to block until the evaluation is complete.
                Defaults to True.
            experiment (Optional[TracerSession]): An existing experiment to
                extend. If provided, experiment_prefix is ignored. For advanced
                usage only.
            upload_results (bool, default=True): Whether to upload the results to LangSmith.
                Defaults to True.
            error_handling (str, default="log"): How to handle individual run errors. 'log'
                will trace the runs with the error message as part of the experiment,
                'ignore' will not count the run as part of the experiment at all.
            **kwargs (Any): Additional keyword arguments to pass to the evaluator.

        Returns:
            AsyncIterator[ExperimentResultRow]: An async iterator over the experiment results.

        Environment:
            - LANGSMITH_TEST_CACHE: If set, API calls will be cached to disk to save time and
                cost during testing. Recommended to commit the cache files to your repository
                for faster CI/CD runs.
                Requires the 'langsmith[vcr]' package to be installed.

        Examples:
            Prepare the dataset:

            .. code-block:: python

                import asyncio
                from langsmith import Client

                client = Client()
                dataset = client.clone_public_dataset(
                    "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
                )
                dataset_name = "Evaluate Examples"

            Basic usage:

            .. code-block:: python

                def accuracy(outputs: dict, reference_outputs: dict) -> dict:
                    # Row-level evaluator for accuracy.
                    pred = outputs["resposen"]
                    expected = reference_outputs["answer"]
                    return {"score": expected.lower() == pred.lower()}


                def precision(outputs: list[dict], reference_outputs: list[dict]) -> dict:
                    # Experiment-level evaluator for precision.
                    # TP / (TP + FP)
                    predictions = [out["response"].lower() for out in outputs]
                    expected = [ref["answer"].lower() for ref in reference_outputs]
                    # yes and no are the only possible answers
                    tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
                    fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
                    return {"score": tp / (tp + fp)}


                async def apredict(inputs: dict) -> dict:
                    # This can be any async function or just an API call to your app.
                    await asyncio.sleep(0.1)
                    return {"response": "Yes"}


                results = asyncio.run(
                    client.aevaluate(
                        apredict,
                        data=dataset_name,
                        evaluators=[accuracy],
                        summary_evaluators=[precision],
                        experiment_prefix="My Experiment",
                        description="Evaluate the accuracy of the model asynchronously.",
                        metadata={
                            "my-prompt-version": "abcd-1234",
                        },
                    )
                )

            Evaluating over only a subset of the examples using an async generator:

            .. code-block:: python

                async def example_generator():
                    examples = client.list_examples(dataset_name=dataset_name, limit=5)
                    for example in examples:
                        yield example


                results = asyncio.run(
                    client.aevaluate(
                        apredict,
                        data=example_generator(),
                        evaluators=[accuracy],
                        summary_evaluators=[precision],
                        experiment_prefix="My Subset Experiment",
                        description="Evaluate a subset of examples asynchronously.",
                    )
                )

            Streaming each prediction to more easily + eagerly debug.

            .. code-block:: python

                results = asyncio.run(
                    client.aevaluate(
                        apredict,
                        data=dataset_name,
                        evaluators=[accuracy],
                        summary_evaluators=[precision],
                        experiment_prefix="My Streaming Experiment",
                        description="Streaming predictions for debugging.",
                        blocking=False,
                    )
                )


                async def aenumerate(iterable):
                    async for elem in iterable:
                        print(elem)


                asyncio.run(aenumerate(results))

            Running without concurrency:

            .. code-block:: python

                results = asyncio.run(
                    client.aevaluate(
                        apredict,
                        data=dataset_name,
                        evaluators=[accuracy],
                        summary_evaluators=[precision],
                        experiment_prefix="My Experiment Without Concurrency",
                        description="This was run without concurrency.",
                        max_concurrency=0,
                    )
                )

            Using Async evaluators:

            .. code-block:: python

                async def helpfulness(outputs: dict) -> dict:
                    # Row-level evaluator for helpfulness.
                    await asyncio.sleep(5)  # Replace with your LLM API call
                    return {"score": outputs["output"] == "Yes"}


                results = asyncio.run(
                    client.aevaluate(
                        apredict,
                        data=dataset_name,
                        evaluators=[helpfulness],
                        summary_evaluators=[precision],
                        experiment_prefix="My Helpful Experiment",
                        description="Applying async evaluators example.",
                    )
                )

            Evaluate an existing experiment:

            .. code-block:: python

                results = asyncio.run(
                    client.aevaluate(
                        # The target is the ID of the experiment we are evaluating
                        target="419dcab2-1d66-4b94-8901-0357ead390df",
                        evaluators=[accuracy, helpfulness],
                        summary_evaluators=[precision],
                    )
                )

        .. versionadded:: 0.2.0

        """  # noqa: E501
        from langsmith.evaluation._arunner import aevaluate as aevaluate_

        return await aevaluate_(
            target,
            data=data,
            evaluators=evaluators,
            summary_evaluators=summary_evaluators,
            metadata=metadata,
            experiment_prefix=experiment_prefix,
            description=description,
            max_concurrency=max_concurrency,
            num_repetitions=num_repetitions,
            client=self,
            blocking=blocking,
            experiment=experiment,
            upload_results=upload_results,
            error_handling=error_handling,
            **kwargs,
        )


def convert_prompt_to_openai_format(
    messages: Any,
    model_kwargs: Optional[dict[str, Any]] = None,
) -> dict:
    """Convert a prompt to OpenAI format.

    Requires the `langchain_openai` package to be installed.

    Args:
        messages (Any): The messages to convert.
        model_kwargs (Optional[Dict[str, Any]]): Model configuration arguments including
            `stop` and any other required arguments. Defaults to None.

    Returns:
        dict: The prompt in OpenAI format.

    Raises:
        ImportError: If the `langchain_openai` package is not installed.
        ls_utils.LangSmithError: If there is an error during the conversion process.
    """
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
    except ImportError:
        raise ImportError(
            "The convert_prompt_to_openai_format function requires the langchain_openai"
            "package to run.\nInstall with `pip install langchain_openai`"
        )

    openai = ChatOpenAI()

    model_kwargs = model_kwargs or {}
    stop = model_kwargs.pop("stop", None)

    try:
        return openai._get_request_payload(messages, stop=stop, **model_kwargs)
    except Exception as e:
        raise ls_utils.LangSmithError(f"Error converting to OpenAI format: {e}")


def convert_prompt_to_anthropic_format(
    messages: Any,
    model_kwargs: Optional[dict[str, Any]] = None,
) -> dict:
    """Convert a prompt to Anthropic format.

    Requires the `langchain_anthropic` package to be installed.

    Args:
        messages (Any): The messages to convert.
        model_kwargs (Optional[Dict[str, Any]]):
            Model configuration arguments including `model_name` and `stop`.
            Defaults to None.

    Returns:
        dict: The prompt in Anthropic format.
    """
    try:
        from langchain_anthropic import ChatAnthropic  # type: ignore
    except ImportError:
        raise ImportError(
            "The convert_prompt_to_anthropic_format function requires the "
            "langchain_anthropic package to run.\n"
            "Install with `pip install langchain_anthropic`"
        )

    model_kwargs = model_kwargs or {}
    model_name = model_kwargs.pop("model_name", "claude-3-haiku-20240307")
    stop = model_kwargs.pop("stop", None)
    timeout = model_kwargs.pop("timeout", None)

    anthropic = ChatAnthropic(
        model_name=model_name, timeout=timeout, stop=stop, **model_kwargs
    )

    try:
        return anthropic._get_request_payload(messages, stop=stop)
    except Exception as e:
        raise ls_utils.LangSmithError(f"Error converting to Anthropic format: {e}")


def _convert_stored_attachments_to_attachments_dict(
    data: dict, *, attachments_key: str, api_url: Optional[str] = None
) -> dict[str, AttachmentInfo]:
    """Convert attachments from the backend database format to the user facing format."""
    attachments_dict = {}
    if attachments_key in data and data[attachments_key]:
        for key, value in data[attachments_key].items():
            if not key.startswith("attachment."):
                continue
            if api_url is not None:
                full_url = _construct_url(api_url, value["presigned_url"])
            else:
                full_url = value["presigned_url"]
            response = requests.get(full_url, stream=True)
            response.raise_for_status()
            reader = io.BytesIO(response.content)
            attachments_dict[key.removeprefix("attachment.")] = AttachmentInfo(
                **{
                    "presigned_url": value["presigned_url"],
                    "reader": reader,
                    "mime_type": value.get("mime_type"),
                }
            )
    return attachments_dict


def _close_files(files: list[io.BufferedReader]) -> None:
    """Close all opened files used in multipart requests."""
    for file in files:
        try:
            file.close()
        except Exception:
            logger.debug("Could not close file: %s", file.name)
            pass


def _dataset_examples_path(api_url: str, dataset_id: ID_TYPE) -> str:
    if api_url.rstrip("/").endswith("/v1"):
        return f"/platform/datasets/{dataset_id}/examples"
    else:
        return f"/v1/platform/datasets/{dataset_id}/examples"


def _construct_url(api_url: str, pathname: str) -> str:
    if pathname.startswith("http"):
        return pathname
    elif pathname.startswith("/"):
        return api_url.rstrip("/") + pathname
    else:
        return api_url.rstrip("/") + "/" + pathname


def dump_model(model) -> dict[str, Any]:
    """Dump model depending on pydantic version."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    elif hasattr(model, "dict"):
        return model.dict()
    else:
        raise TypeError("Unsupported model type")
