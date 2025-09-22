"""Provide helper classes used by other models."""

from __future__ import annotations

import random
import time
from collections import OrderedDict
from typing import Any, Callable, Generator

from ..util import _deprecate_args


@_deprecate_args("permissions", "known_permissions")
def permissions_string(
    *, known_permissions: set[str], permissions: list[str] | None
) -> str:
    """Return a comma separated string of permission changes.

    :param known_permissions: A set of strings representing the available permissions.
    :param permissions: A list of strings, or ``None``. These strings can exclusively
        contain ``+`` or ``-`` prefixes, or contain no prefixes at all. When prefixed,
        the resulting string will simply be the joining of these inputs. When not
        prefixed, all permissions are considered to be additions, and all permissions in
        the ``known_permissions`` set that aren't provided are considered to be
        removals. When ``None``, the result is ``"+all"``.

    """
    if permissions is None:
        to_set = ["+all"]
    else:
        to_set = ["-all"]
        omitted = sorted(known_permissions - set(permissions))
        to_set.extend(f"-{x}" for x in omitted)
        to_set.extend(f"+{x}" for x in permissions)
    return ",".join(to_set)


@_deprecate_args(
    "function",
    "pause_after",
    "skip_existing",
    "attribute_name",
    "exclude_before",
    "continue_after_id",
)
def stream_generator(
    function: Callable,
    *,
    attribute_name: str = "fullname",
    continue_after_id: str | None = None,
    exclude_before: bool = False,
    pause_after: int | None = None,
    skip_existing: bool = False,
    **function_kwargs: Any,
) -> Generator[Any, None, None]:
    """Yield new items from ``function`` as they become available.

    :param function: A callable that returns a :class:`.ListingGenerator`, e.g.,
        :meth:`.Subreddit.comments` or :meth:`.Subreddit.new`.
    :param attribute_name: The field to use as an ID (default: ``"fullname"``).
    :param exclude_before: When ``True`` does not pass ``params`` to ``function``
        (default: ``False``).
    :param pause_after: An integer representing the number of requests that result in no
        new items before this function yields ``None``, effectively introducing a pause
        into the stream. A negative value yields ``None`` after items from a single
        response have been yielded, regardless of number of new items obtained in that
        response. A value of ``0`` yields ``None`` after every response resulting in no
        new items, and a value of ``None`` never introduces a pause (default: ``None``).
    :param skip_existing: When ``True``, this does not yield any results from the first
        request thereby skipping any items that existed in the stream prior to starting
        the stream (default: ``False``).
    :param continue_after_id: The initial item ID value to use for ``before`` in
        ``params``. The stream will continue from the item following this one (default:
        ``None``).

    Additional keyword arguments will be passed to ``function``.

    .. note::

        This function internally uses an exponential delay with jitter between
        subsequent responses that contain no new results, up to a maximum delay of just
        over 16 seconds. In practice, that means that the time before pause for
        ``pause_after=N+1`` is approximately twice the time before pause for
        ``pause_after=N``.

    For example, to create a stream of comment replies, try:

    .. code-block:: python

        reply_function = reddit.inbox.comment_replies
        for reply in praw.models.util.stream_generator(reply_function):
            print(reply)

    To pause a comment stream after six responses with no new comments, try:

    .. code-block:: python

        subreddit = reddit.subreddit("test")
        for comment in subreddit.stream.comments(pause_after=6):
            if comment is None:
                break
            print(comment)

    To resume fetching comments after a pause, try:

    .. code-block:: python

        subreddit = reddit.subreddit("test")
        comment_stream = subreddit.stream.comments(pause_after=5)

        for comment in comment_stream:
            if comment is None:
                break
            print(comment)
        # Do any other processing, then try to fetch more data
        for comment in comment_stream:
            if comment is None:
                break
            print(comment)

    To bypass the internal exponential backoff, try the following. This approach is
    useful if you are monitoring a subreddit with infrequent activity, and you want to
    consistently learn about new items from the stream as soon as possible, rather than
    up to a delay of just over sixteen seconds.

    .. code-block:: python

        subreddit = reddit.subreddit("test")
        for comment in subreddit.stream.comments(pause_after=0):
            if comment is None:
                continue
            print(comment)

    """
    before_attribute = continue_after_id
    exponential_counter = ExponentialCounter(max_counter=16)
    seen_attributes = BoundedSet(301)
    without_before_counter = 0
    responses_without_new = 0
    valid_pause_after = pause_after is not None
    while True:
        found = False
        newest_attribute = None
        limit = 100
        if before_attribute is None:
            limit -= without_before_counter
            without_before_counter = (without_before_counter + 1) % 30
        if not exclude_before:
            function_kwargs["params"] = {"before": before_attribute}
        for item in reversed(list(function(limit=limit, **function_kwargs))):
            attribute = getattr(item, attribute_name)
            if attribute in seen_attributes:
                continue
            found = True
            seen_attributes.add(attribute)
            newest_attribute = attribute
            if not skip_existing:
                yield item
        before_attribute = newest_attribute
        skip_existing = False
        if valid_pause_after and pause_after < 0:
            yield None
        elif found:
            exponential_counter.reset()
            responses_without_new = 0
        else:
            responses_without_new += 1
            if valid_pause_after and responses_without_new > pause_after:
                exponential_counter.reset()
                responses_without_new = 0
                yield None
            else:
                time.sleep(exponential_counter.counter())


class BoundedSet:
    """A set with a maximum size that evicts the oldest items when necessary.

    This class does not implement the complete set interface.

    """

    def __contains__(self, item: Any) -> bool:
        """Test if the :class:`.BoundedSet` contains item."""
        self._access(item)
        return item in self._set

    def __init__(self, max_items: int):
        """Initialize a :class:`.BoundedSet` instance."""
        self.max_items = max_items
        self._set = OrderedDict()

    def _access(self, item: Any):
        if item in self._set:
            self._set.move_to_end(item)

    def add(self, item: Any):
        """Add an item to the set discarding the oldest item if necessary."""
        self._access(item)
        self._set[item] = None
        if len(self._set) > self.max_items:
            self._set.popitem(last=False)


class ExponentialCounter:
    """A class to provide an exponential counter with jitter."""

    def __init__(self, max_counter: int):
        """Initialize an :class:`.ExponentialCounter` instance.

        :param max_counter: The maximum base value.

            .. note::

                The computed value may be 3.125% higher due to jitter.

        """
        self._base = 1
        self._max = max_counter

    def counter(self) -> int | float:
        """Increment the counter and return the current value with jitter."""
        max_jitter = self._base / 16.0
        value = self._base + random.random() * max_jitter - max_jitter / 2  # noqa: S311
        self._base = min(self._base * 2, self._max)
        return value

    def reset(self):
        """Reset the counter to 1."""
        self._base = 1
