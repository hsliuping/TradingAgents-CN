"""Provide the RateLimiter class."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Mapping

if TYPE_CHECKING:
    from requests.models import Response

log = logging.getLogger(__package__)


class RateLimiter:
    """Facilitates the rate limiting of requests to Reddit.

    Rate limits are controlled based on feedback from requests to Reddit.

    """

    def __init__(self, *, window_size: int) -> None:
        """Create an instance of the RateLimit class."""
        self.remaining: float | None = None
        self.next_request_timestamp: float | None = None
        self.reset_timestamp: float | None = None
        self.used: int | None = None
        self.window_size: int = window_size

    def call(
        self,
        request_function: Callable[[Any], Response],
        set_header_callback: Callable[[], dict[str, str]],
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Rate limit the call to ``request_function``.

        :param request_function: A function call that returns an HTTP response object.
        :param set_header_callback: A callback function used to set the request headers.
            This callback is called after any necessary sleep time occurs.
        :param args: The positional arguments to ``request_function``.
        :param kwargs: The keyword arguments to ``request_function``.

        """
        self.delay()
        kwargs["headers"] = set_header_callback()
        response = request_function(*args, **kwargs)
        self.update(response.headers)
        return response

    def delay(self) -> None:
        """Sleep for an amount of time to remain under the rate limit."""
        if self.next_request_timestamp is None:
            return
        sleep_seconds = self.next_request_timestamp - time.time()
        if sleep_seconds <= 0:
            return
        message = f"Sleeping: {sleep_seconds:0.2f} seconds prior to call"
        log.debug(message)
        time.sleep(sleep_seconds)

    def update(self, response_headers: Mapping[str, str]) -> None:
        """Update the state of the rate limiter based on the response headers.

        This method should only be called following an HTTP request to Reddit.

        Response headers that do not contain ``x-ratelimit`` fields will be treated as a
        single request. This behavior is to error on the safe-side as such responses
        should trigger exceptions that indicate invalid behavior.

        """
        if "x-ratelimit-remaining" not in response_headers:
            if self.remaining is not None:
                self.remaining -= 1
                self.used += 1
            return

        now = time.time()

        seconds_to_reset = int(response_headers["x-ratelimit-reset"])
        self.remaining = float(response_headers["x-ratelimit-remaining"])
        self.used = int(response_headers["x-ratelimit-used"])
        self.reset_timestamp = now + seconds_to_reset

        if self.remaining <= 0:
            self.next_request_timestamp = self.reset_timestamp
            return

        self.next_request_timestamp = min(
            self.reset_timestamp,
            now
            + min(
                max(
                    seconds_to_reset
                    - (
                        self.window_size
                        - (self.window_size / (self.remaining + self.used) * self.used)
                    ),
                    0,
                ),
                10,
            ),
        )
