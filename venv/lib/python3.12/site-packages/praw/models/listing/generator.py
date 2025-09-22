"""Provide the ListingGenerator class."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Iterator

from ..base import PRAWBase
from .listing import FlairListing, ModNoteListing

if TYPE_CHECKING:  # pragma: no cover
    import praw


class ListingGenerator(PRAWBase, Iterator):
    """Instances of this class generate :class:`.RedditBase` instances.

    .. warning::

        This class should not be directly utilized. Instead, you will find a number of
        methods that return instances of the class here_.

    .. _here: https://praw.readthedocs.io/en/latest/search.html?q=ListingGenerator

    """

    def __init__(
        self,
        reddit: praw.Reddit,
        url: str,
        limit: int = 100,
        params: dict[str, str | int] | None = None,
    ):
        """Initialize a :class:`.ListingGenerator` instance.

        :param reddit: An instance of :class:`.Reddit`.
        :param url: A URL returning a Reddit listing.
        :param limit: The number of content entries to fetch. If ``limit`` is ``None``,
            then fetch as many entries as possible. Most of Reddit's listings contain a
            maximum of 1000 items, and are returned 100 at a time. This class will
            automatically issue all necessary requests (default: ``100``).
        :param params: A dictionary containing additional query string parameters to
            send with the request.

        """
        super().__init__(reddit, _data=None)
        self._exhausted = False
        self._listing = None
        self._list_index = None
        self.limit = limit
        self.params = deepcopy(params) if params else {}
        self.params["limit"] = limit or 1024
        self.url = url
        self.yielded = 0

    def __iter__(self) -> Any:
        """Permit :class:`.ListingGenerator` to operate as an iterator."""
        return self

    def __next__(self) -> Any:
        """Permit :class:`.ListingGenerator` to operate as a generator."""
        if self.limit is not None and self.yielded >= self.limit:
            raise StopIteration

        if self._listing is None or self._list_index >= len(self._listing):
            self._next_batch()

        self._list_index += 1
        self.yielded += 1
        return self._listing[self._list_index - 1]

    def _extract_sublist(self, listing: dict[str, Any] | list[Any]):
        if isinstance(listing, list):
            return listing[1]  # for submission duplicates
        if isinstance(listing, dict):
            classes = [FlairListing, ModNoteListing]

            for listing_type in classes:
                if listing_type.CHILD_ATTRIBUTE in listing:
                    return listing_type(self._reddit, listing)
            else:  # noqa: PLW0120
                msg = "The generator returned a dictionary PRAW didn't recognize. File a bug report at PRAW."
                raise ValueError(msg)
        return listing

    def _next_batch(self):
        if self._exhausted:
            raise StopIteration

        self._listing = self._reddit.get(self.url, params=self.params)
        self._listing = self._extract_sublist(self._listing)
        self._list_index = 0

        if not self._listing:
            raise StopIteration

        if self._listing.after and self._listing.after != self.params.get(
            self._listing.AFTER_PARAM
        ):
            self.params[self._listing.AFTER_PARAM] = self._listing.after
        else:
            self._exhausted = True
