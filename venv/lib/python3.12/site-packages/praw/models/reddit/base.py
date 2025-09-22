"""Provide the RedditBase class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from ...endpoints import API_PATH
from ...exceptions import InvalidURL
from ..base import PRAWBase

if TYPE_CHECKING:  # pragma: no cover
    import praw


class RedditBase(PRAWBase):
    """Base class that represents actual Reddit objects."""

    @staticmethod
    def _url_parts(url: str) -> list[str]:
        parsed = urlparse(url)
        if not parsed.netloc:
            raise InvalidURL(url)
        return parsed.path.rstrip("/").split("/")

    def __eq__(self, other: Any | str) -> bool:
        """Return whether the other instance equals the current."""
        if isinstance(other, str):
            return other.lower() == str(self).lower()
        return (
            isinstance(other, self.__class__)
            and str(self).lower() == str(other).lower()
        )

    def __getattr__(self, attribute: str) -> Any:
        """Return the value of ``attribute``."""
        if not attribute.startswith("_") and not self._fetched:
            self._fetch()
            return getattr(self, attribute)
        msg = f"{self.__class__.__name__!r} object has no attribute {attribute!r}"
        raise AttributeError(msg)

    def __hash__(self) -> int:
        """Return the hash of the current instance."""
        return hash(self.__class__.__name__) ^ hash(str(self).lower())

    def __init__(
        self,
        reddit: praw.Reddit,
        _data: dict[str, Any] | None,
        _extra_attribute_to_check: str | None = None,
        _fetched: bool = False,
        _str_field: bool = True,
    ):
        """Initialize a :class:`.RedditBase` instance.

        :param reddit: An instance of :class:`.Reddit`.

        """
        super().__init__(reddit, _data=_data)
        self._fetched = _fetched
        if _str_field and self.STR_FIELD not in self.__dict__:
            if (
                _extra_attribute_to_check is not None
                and _extra_attribute_to_check in self.__dict__
            ):
                return
            msg = f"An invalid value was specified for {self.STR_FIELD}. Check that the argument for the {self.STR_FIELD} parameter is not empty."
            raise ValueError(msg)

    def __ne__(self, other: object) -> bool:
        """Return whether the other instance differs from the current."""
        return not self == other

    def __repr__(self) -> str:
        """Return an object initialization representation of the instance."""
        return f"{self.__class__.__name__}({self.STR_FIELD}={str(self)!r})"

    def __str__(self) -> str:
        """Return a string representation of the instance."""
        return getattr(self, self.STR_FIELD)

    def _fetch(self):
        self._fetched = True

    def _fetch_data(self):
        name, fields, params = self._fetch_info()
        path = API_PATH[name].format(**fields)
        return self._reddit.request(method="GET", params=params, path=path)

    def _reset_attributes(self, *attributes: str):
        for attribute in attributes:
            if attribute in self.__dict__:
                del self.__dict__[attribute]
        self._fetched = False
