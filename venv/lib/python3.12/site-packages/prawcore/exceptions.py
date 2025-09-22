"""Provide exception classes for the prawcore package."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from requests.models import Response


class PrawcoreException(Exception):  # noqa: N818
    """Base exception class for exceptions that occur within this package."""


class InvalidInvocation(PrawcoreException):
    """Indicate that the code to execute cannot be completed."""


class OAuthException(PrawcoreException):
    """Indicate that there was an OAuth2 related error with the request."""

    def __init__(
        self, response: Response, error: str, description: str | None = None
    ) -> None:
        """Initialize a OAuthException instance.

        :param response: A ``requests.response`` instance.
        :param error: The error type returned by Reddit.
        :param description: A description of the error when provided.

        """
        self.error = error
        self.description = description
        self.response = response
        message = f"{error} error processing request"
        if description:
            message += f" ({description})"
        PrawcoreException.__init__(self, message)


class RequestException(PrawcoreException):
    """Indicate that there was an error with the incomplete HTTP request."""

    def __init__(
        self,
        original_exception: Exception,
        request_args: tuple[Any, ...],
        request_kwargs: dict[
            str, bool | (dict[str, int] | (dict[str, str] | str)) | None
        ],
    ) -> None:
        """Initialize a RequestException instance.

        :param original_exception: The original exception that occurred.
        :param request_args: The arguments to the request function.
        :param request_kwargs: The keyword arguments to the request function.

        """
        self.original_exception = original_exception
        self.request_args = request_args
        self.request_kwargs = request_kwargs
        super().__init__(f"error with request {original_exception}")


class ResponseException(PrawcoreException):
    """Indicate that there was an error with the completed HTTP request."""

    def __init__(self, response: Response) -> None:
        """Initialize a ResponseException instance.

        :param response: A ``requests.response`` instance.

        """
        self.response = response
        super().__init__(f"received {response.status_code} HTTP response")


class BadJSON(ResponseException):
    """Indicate the response did not contain valid JSON."""


class BadRequest(ResponseException):
    """Indicate invalid parameters for the request."""


class Conflict(ResponseException):
    """Indicate a conflicting change in the target resource."""


class Forbidden(ResponseException):
    """Indicate the authentication is not permitted for the request."""


class InsufficientScope(ResponseException):
    """Indicate that the request requires a different scope."""


class InvalidToken(ResponseException):
    """Indicate that the request used an invalid access token."""


class NotFound(ResponseException):
    """Indicate that the requested URL was not found."""


class Redirect(ResponseException):
    """Indicate the request resulted in a redirect.

    This class adds the attribute ``path``, which is the path to which the response
    redirects.

    """

    def __init__(self, response: Response) -> None:
        """Initialize a Redirect exception instance.

        :param response: A ``requests.response`` instance containing a location header.

        """
        path = urlparse(response.headers["location"]).path
        self.path = path[:-5] if path.endswith(".json") else path
        self.response = response
        msg = f"Redirect to {self.path}"
        msg += (
            " (You may be trying to perform a non-read-only action via a "
            "read-only instance.)"
            if "/login/" in self.path
            else ""
        )
        PrawcoreException.__init__(self, msg)


class ServerError(ResponseException):
    """Indicate issues on the server end preventing request fulfillment."""


class SpecialError(ResponseException):
    """Indicate syntax or spam-prevention issues."""

    def __init__(self, response: Response) -> None:
        """Initialize a SpecialError exception instance.

        :param response: A ``requests.response`` instance containing a message and a
            list of special errors.

        """
        self.response = response

        resp_dict = self.response.json()  # assumes valid JSON
        self.message = resp_dict.get("message", "")
        self.reason = resp_dict.get("reason", "")
        self.special_errors = resp_dict.get("special_errors", [])
        PrawcoreException.__init__(self, f"Special error {self.message!r}")


class TooLarge(ResponseException):
    """Indicate that the request data exceeds the allowed limit."""


class TooManyRequests(ResponseException):
    """Indicate that the user has sent too many requests in a given amount of time."""

    def __init__(self, response: Response) -> None:
        """Initialize a TooManyRequests exception instance.

        :param response: A ``requests.response`` instance that may contain a retry-after
            header and a message.

        """
        self.response = response
        self.retry_after = response.headers.get("retry-after")
        self.message = response.text  # Not all response bodies are valid JSON

        msg = f"received {response.status_code} HTTP response"
        if self.retry_after:
            msg += (
                f". Please wait at least {float(self.retry_after)} seconds before"
                f" re-trying this request."
            )
        PrawcoreException.__init__(self, msg)


class URITooLong(ResponseException):
    """Indicate that the length of the request URI exceeds the allowed limit."""


class UnavailableForLegalReasons(ResponseException):
    """Indicate that the requested URL is unavailable due to legal reasons."""
