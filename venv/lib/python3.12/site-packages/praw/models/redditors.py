"""Provide the Redditors class."""

from __future__ import annotations

from itertools import islice
from types import SimpleNamespace
from typing import TYPE_CHECKING, Iterable, Iterator

import prawcore

from ..const import API_PATH
from .base import PRAWBase
from .listing.generator import ListingGenerator
from .util import stream_generator

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class PartialRedditor(SimpleNamespace):
    """A namespace object that provides a subset of :class:`.Redditor` attributes."""


class Redditors(PRAWBase):
    """Redditors is a Listing class that provides various :class:`.Redditor` lists."""

    def new(
        self, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Subreddit]:
        """Return a :class:`.ListingGenerator` for new :class:`.Redditors`.

        :returns: :class:`.Redditor` profiles, which are a type of :class:`.Subreddit`.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        """
        return ListingGenerator(self._reddit, API_PATH["users_new"], **generator_kwargs)

    def partial_redditors(self, ids: Iterable[str]) -> Iterator[PartialRedditor]:
        """Get user summary data by redditor IDs.

        :param ids: An iterable of redditor fullname IDs.

        :returns: A iterator producing :class:`.PartialRedditor` objects.

        Each ID must be prefixed with ``t2_``.

        Invalid IDs are ignored by the server.

        """
        iterable = iter(ids)
        while True:
            chunk = list(islice(iterable, 100))
            if not chunk:
                break

            params = {"ids": ",".join(chunk)}
            try:
                results = self._reddit.get(API_PATH["user_by_fullname"], params=params)
            except prawcore.exceptions.NotFound:
                # None of the given IDs matched any Redditor.
                continue

            for fullname, user_data in results.items():
                yield PartialRedditor(fullname=fullname, **user_data)

    def popular(
        self, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Subreddit]:
        """Return a :class:`.ListingGenerator` for popular :class:`.Redditors`.

        :returns: :class:`.Redditor` profiles, which are a type of :class:`.Subreddit`.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        """
        return ListingGenerator(
            self._reddit, API_PATH["users_popular"], **generator_kwargs
        )

    def search(
        self, query: str, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Subreddit]:
        r"""Return a :class:`.ListingGenerator` of Redditors for ``query``.

        :param query: The query string to filter Redditors by.

        :returns: :class:`.Redditor`\ s.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        """
        self._safely_add_arguments(arguments=generator_kwargs, key="params", q=query)
        return ListingGenerator(
            self._reddit, API_PATH["users_search"], **generator_kwargs
        )

    def stream(
        self, **stream_options: str | int | dict[str, str]
    ) -> Iterator[praw.models.Subreddit]:
        """Yield new Redditors as they are created.

        Redditors are yielded oldest first. Up to 100 historical Redditors will
        initially be returned.

        Keyword arguments are passed to :func:`.stream_generator`.

        :returns: :class:`.Redditor` profiles, which are a type of :class:`.Subreddit`.

        """
        return stream_generator(self.new, **stream_options)
