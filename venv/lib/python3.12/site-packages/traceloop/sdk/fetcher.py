import logging
import os
import threading
import time
import typing
import requests

from threading import Thread, Event
from typing import Dict
from tenacity import (
    RetryError,
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

from traceloop.sdk.prompts.registry import PromptRegistry
from traceloop.sdk.prompts.client import PromptRegistryClient
from traceloop.sdk.tracing.content_allow_list import ContentAllowList
from traceloop.sdk.version import __version__

MAX_RETRIES: int = int(os.getenv("TRACELOOP_PROMPT_MANAGER_MAX_RETRIES") or 3)
POLLING_INTERVAL: int = int(os.getenv("TRACELOOP_PROMPT_MANAGER_POLLING_INTERVAL") or 5)


class Fetcher:
    _prompt_registry: PromptRegistry
    _poller_thread: Thread
    _exit_monitor: Thread
    _stop_polling_thread: Event

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._api_key = api_key
        self._prompt_registry = PromptRegistryClient()._registry
        self._content_allow_list = ContentAllowList()
        self._stop_polling_event = Event()
        self._exit_monitor = Thread(
            target=monitor_exit, args=(self._stop_polling_event,), daemon=True
        )
        self._poller_thread = Thread(
            target=thread_func,
            args=(
                self._prompt_registry,
                self._content_allow_list,
                self._base_url,
                self._api_key,
                self._stop_polling_event,
                POLLING_INTERVAL,
            ),
        )

    def run(self):
        refresh_data(
            self._base_url,
            self._api_key,
            self._prompt_registry,
            self._content_allow_list,
        )
        self._exit_monitor.start()
        self._poller_thread.start()

    def post(self, api: str, body: Dict[str, str]):
        post_url(f"{self._base_url}/v1/traceloop/{api}", self._api_key, body)

    def api_post(self, api: str, body: Dict[str, typing.Any]):
        try:
            post_url(f"{self._base_url}/v2/{api}", self._api_key, body)
        except Exception as e:
            print(e)


class RetryIfServerError(retry_if_exception):
    def __init__(
        self,
        exception_types: typing.Union[
            typing.Type[BaseException],
            typing.Tuple[typing.Type[BaseException], ...],
        ] = Exception,
    ) -> None:
        self.exception_types = exception_types
        super().__init__(lambda e: check_http_error(e))


def check_http_error(e):
    return isinstance(e, requests.exceptions.HTTPError) and (
        500 <= e.response.status_code < 600
    )


@retry(
    wait=wait_exponential(multiplier=1, min=4),
    stop=stop_after_attempt(MAX_RETRIES),
    retry=RetryIfServerError(),
)
def fetch_url(url: str, api_key: str):
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-Traceloop-SDK-Version": __version__,
        },
    )

    if response.status_code != 200:
        if response.status_code == 401 or response.status_code == 403:
            logging.error("Authorization error: Invalid Traceloop API key.")
            raise requests.exceptions.HTTPError(response=response)
        else:
            logging.error("Request failed: %s", response.status_code)
            raise requests.exceptions.HTTPError(response=response)
    else:
        return response.json()


def post_url(url: str, api_key: str, body: Dict[str, typing.Any]):
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-Traceloop-SDK-Version": __version__,
        },
        json=body,
    )

    if response.status_code != 200:
        raise requests.exceptions.HTTPError(response=response)


def thread_func(
    prompt_registry: PromptRegistry,
    content_allow_list: ContentAllowList,
    base_url: str,
    api_key: str,
    stop_polling_event: Event,
    seconds_interval: float = 5.0,
):
    while not stop_polling_event.is_set():
        try:
            refresh_data(base_url, api_key, prompt_registry, content_allow_list)
        except RetryError:
            logging.error("Request failed after retries : stopped polling")
            break

        time.sleep(seconds_interval)


def refresh_data(
    base_url: str,
    api_key: str,
    prompt_registry: PromptRegistry,
    content_allow_list: ContentAllowList,
):
    response = fetch_url(f"{base_url}/v1/traceloop/prompts", api_key)
    prompt_registry.load(response)

    response = fetch_url(f"{base_url}/v1/traceloop/pii/tracing-allow-list", api_key)
    content_allow_list.load(response)


def monitor_exit(exit_event: Event):
    main_thread = threading.main_thread()
    main_thread.join()
    exit_event.set()
