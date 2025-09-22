"""PRAW exception classes.

Includes two main exceptions: :class:`.RedditAPIException` for when something goes wrong
on the server side, and :class:`.ClientException` when something goes wrong on the
client side. Both of these classes extend :class:`.PRAWException`.

All other exceptions are subclassed from :class:`.ClientException`.

"""

from __future__ import annotations

from typing import Any
from warnings import warn

from .util import _deprecate_args


class PRAWException(Exception):
    """The base PRAW Exception that all other exception classes extend."""


class RedditErrorItem:
    """Represents a single error returned from Reddit's API."""

    @property
    def error_message(self) -> str:
        """Get the completed error message string."""
        error_str = self.error_type
        if self.message:
            error_str += f": {self.message!r}"
        if self.field:
            error_str += f" on field {self.field!r}"
        return error_str

    def __eq__(self, other: RedditErrorItem | list[str]) -> bool:
        """Check for equality."""
        if isinstance(other, RedditErrorItem):
            return (self.error_type, self.message, self.field) == (
                other.error_type,
                other.message,
                other.field,
            )
        return super().__eq__(other)

    @_deprecate_args("error_type", "message", "field")
    def __init__(
        self,
        error_type: str,
        *,
        field: str | None = None,
        message: str | None = None,
    ):
        """Initialize a :class:`.RedditErrorItem` instance.

        :param error_type: The error type set on Reddit's end.
        :param field: The input field associated with the error, if available.
        :param message: The associated message for the error.

        """
        self.error_type = error_type
        self.message = message
        self.field = field

    def __repr__(self) -> str:
        """Return an object initialization representation of the instance."""
        return (
            f"{self.__class__.__name__}(error_type={self.error_type!r},"
            f" message={self.message!r}, field={self.field!r})"
        )

    def __str__(self) -> str:
        """Get the message returned from str(self)."""
        return self.error_message


class ClientException(PRAWException):
    """Indicate exceptions that don't involve interaction with Reddit's API."""


class DuplicateReplaceException(ClientException):
    """Indicate exceptions that involve the replacement of :class:`.MoreComments`."""

    def __init__(self):
        """Initialize a :class:`.DuplicateReplaceException` instance."""
        super().__init__(
            "A duplicate comment has been detected. Are you attempting to call"
            " 'replace_more_comments' more than once?"
        )


class InvalidFlairTemplateID(ClientException):
    """Indicate exceptions where an invalid flair template ID is given."""

    def __init__(self, template_id: str):
        """Initialize an :class:`.InvalidFlairTemplateID` instance."""
        super().__init__(
            f"The flair template ID '{template_id}' is invalid. If you are trying to"
            " create a flair, please use the 'add' method."
        )


class InvalidImplicitAuth(ClientException):
    """Indicate exceptions where an implicit auth type is used incorrectly."""

    def __init__(self):
        """Initialize an :class:`.InvalidImplicitAuth` instance."""
        super().__init__("Implicit authorization can only be used with installed apps.")


class InvalidURL(ClientException):
    """Indicate exceptions where an invalid URL is entered."""

    @_deprecate_args("url", "message")
    def __init__(self, url: str, *, message: str = "Invalid URL: {}"):
        """Initialize an :class:`.InvalidURL` instance.

        :param url: The invalid URL.
        :param message: The message to display. Must contain a format identifier (``{}``
            or ``{0}``) (default: ``"Invalid URL: {}"``).

        """
        super().__init__(message.format(url))


class MissingRequiredAttributeException(ClientException):
    """Indicate exceptions caused by not including a required attribute."""


class ReadOnlyException(ClientException):
    """Raised when a method call requires :attr:`.read_only` mode to be disabled."""


class TooLargeMediaException(ClientException):
    """Indicate exceptions from uploading media that's too large."""

    @_deprecate_args("maximum_size", "actual")
    def __init__(self, *, actual: int, maximum_size: int):
        """Initialize a :class:`.TooLargeMediaException` instance.

        :param actual: The actual size of the uploaded media.
        :param maximum_size: The maximum size of the uploaded media.

        """
        self.maximum_size = maximum_size
        self.actual = actual
        super().__init__(
            f"The media that you uploaded was too large (maximum size is {maximum_size}"
            f" bytes, uploaded {actual} bytes)"
        )


class WebSocketException(ClientException):
    """Indicate exceptions caused by use of WebSockets."""

    @property
    def original_exception(self) -> Exception:
        """Access the ``original_exception`` attribute (now deprecated)."""
        warn(
            "Accessing the attribute 'original_exception' is deprecated. Please rewrite"
            " your code in such a way that this attribute does not need to be used. It"
            " will be removed in PRAW 8.0.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self._original_exception

    @original_exception.setter
    def original_exception(self, value: Exception):
        self._original_exception = value

    @original_exception.deleter
    def original_exception(self):
        del self._original_exception

    def __init__(self, message: str, exception: Exception | None):
        """Initialize a :class:`.WebSocketException` instance.

        :param message: The exception message.
        :param exception: The exception thrown by the websocket library.

            .. note::

                This parameter is deprecated. It will be removed in PRAW 8.0.

        """
        super().__init__(message)
        self._original_exception = exception


class MediaPostFailed(WebSocketException):
    """Indicate exceptions where media uploads failed.."""

    def __init__(self):
        """Initialize a :class:`.MediaPostFailed` instance."""
        super().__init__(
            "The attempted media upload action has failed. Possible causes include the"
            " corruption of media files. Check that the media file can be opened on"
            " your local machine.",
            None,
        )


class APIException(PRAWException):
    """Old class preserved for alias purposes.

    .. deprecated:: 7.0

        Class :class:`.APIException` has been deprecated in favor of
        :class:`.RedditAPIException`. This class will be removed in PRAW 8.0.

    """

    @staticmethod
    def parse_exception_list(
        exceptions: list[RedditErrorItem | list[str]],
    ) -> list[RedditErrorItem]:
        """Covert an exception list into a :class:`.RedditErrorItem` list."""
        return [
            (
                exception
                if isinstance(exception, RedditErrorItem)
                else RedditErrorItem(
                    error_type=exception[0],
                    field=exception[2] if bool(exception[2]) else "",
                    message=exception[1] if bool(exception[1]) else "",
                )
            )
            for exception in exceptions
        ]

    @property
    def error_type(self) -> str:
        """Get error_type.

        .. deprecated:: 7.0

            Accessing attributes through instances of :class:`.RedditAPIException` is
            deprecated. This behavior will be removed in PRAW 8.0. Check out the
            :ref:`PRAW 7 Migration tutorial <Exception_Handling>` on how to migrate code
            from this behavior.

        """
        return self._get_old_attr("error_type")

    @property
    def field(self) -> str:
        """Get field.

        .. deprecated:: 7.0

            Accessing attributes through instances of :class:`.RedditAPIException` is
            deprecated. This behavior will be removed in PRAW 8.0. Check out the
            :ref:`PRAW 7 Migration tutorial <Exception_Handling>` on how to migrate code
            from this behavior.

        """
        return self._get_old_attr("field")

    @property
    def message(self) -> str:
        """Get message.

        .. deprecated:: 7.0

            Accessing attributes through instances of :class:`.RedditAPIException` is
            deprecated. This behavior will be removed in PRAW 8.0. Check out the
            :ref:`PRAW 7 Migration tutorial <Exception_Handling>` on how to migrate code
            from this behavior.

        """
        return self._get_old_attr("message")

    def __init__(
        self,
        items: list[RedditErrorItem | list[str] | str] | str,
        *optional_args: str,
    ):
        """Initialize a :class:`.RedditAPIException` instance.

        :param items: Either a list of instances of :class:`.RedditErrorItem` or a list
            containing lists of unformed errors.
        :param optional_args: Takes the second and third arguments that
            :class:`.APIException` used to take.

        """
        if isinstance(items, str):
            items = [[items, *optional_args]]
        elif isinstance(items, list) and isinstance(items[0], str):
            items = [items]
        self.items = self.parse_exception_list(items)
        super().__init__(*self.items)

    def _get_old_attr(self, attrname: str) -> Any:
        warn(
            f"Accessing attribute '{attrname}' through APIException is deprecated."
            " This behavior will be removed in PRAW 8.0. Check out"
            " https://praw.readthedocs.io/en/latest/package_info/praw7_migration.html"
            " to learn how to migrate your code.",
            category=DeprecationWarning,
            stacklevel=3,
        )
        return getattr(self.items[0], attrname)


class RedditAPIException(APIException):
    """Container for error messages from Reddit's API."""
