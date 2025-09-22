"""Provide the Front class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from ..const import API_PATH
from ..util import _deprecate_args
from .base import PRAWBase
from .listing.generator import ListingGenerator
from .util import stream_generator

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class Inbox(PRAWBase):
    """Inbox is a Listing class that represents the inbox."""

    def all(  # noqa: A003
        self, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Message | praw.models.Comment]:
        """Return a :class:`.ListingGenerator` for all inbox comments and messages.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        To output the type and ID of all items available via this listing do:

        .. code-block:: python

            for item in reddit.inbox.all(limit=None):
                print(repr(item))

        """
        return ListingGenerator(self._reddit, API_PATH["inbox"], **generator_kwargs)

    def collapse(self, items: list[praw.models.Message]):
        """Mark an inbox message as collapsed.

        :param items: A list containing instances of :class:`.Message`.

        Requests are batched at 25 items (reddit limit).

        For example, to collapse all unread Messages, try:

        .. code-block:: python

            from praw.models import Message

            unread_messages = []
            for item in reddit.inbox.unread(limit=None):
                if isinstance(item, Message):
                    unread_messages.append(item)
            reddit.inbox.collapse(unread_messages)

        .. seealso::

            :meth:`.Message.uncollapse`

        """
        while items:
            data = {"id": ",".join(x.fullname for x in items[:25])}
            self._reddit.post(API_PATH["collapse"], data=data)
            items = items[25:]

    def comment_replies(
        self, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Comment]:
        """Return a :class:`.ListingGenerator` for comment replies.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        To output the author of one request worth of comment replies try:

        .. code-block:: python

            for reply in reddit.inbox.comment_replies():
                print(reply.author)

        """
        return ListingGenerator(
            self._reddit, API_PATH["comment_replies"], **generator_kwargs
        )

    def mark_all_read(self):
        """Mark all messages as read with just one API call.

        Example usage:

        .. code-block:: python

            reddit.inbox.mark_all_read()

        .. note::

            This method returns after Reddit acknowledges your request, instead of after
            the request has been fulfilled.

        """
        self._reddit.post(API_PATH["read_all_messages"])

    def mark_read(self, items: list[praw.models.Comment | praw.models.Message]):
        """Mark Comments or Messages as read.

        :param items: A list containing instances of :class:`.Comment` and/or
            :class:`.Message` to be marked as read relative to the authorized user's
            inbox.

        Requests are batched at 25 items (reddit limit).

        For example, to mark all unread Messages as read, try:

        .. code-block:: python

            from praw.models import Message

            unread_messages = []
            for item in reddit.inbox.unread(limit=None):
                if isinstance(item, Message):
                    unread_messages.append(item)
            reddit.inbox.mark_read(unread_messages)

        .. seealso::

            - :meth:`.Comment.mark_read`
            - :meth:`.Message.mark_read`

        """
        while items:
            data = {"id": ",".join(x.fullname for x in items[:25])}
            self._reddit.post(API_PATH["read_message"], data=data)
            items = items[25:]

    def mark_unread(self, items: list[praw.models.Comment | praw.models.Message]):
        """Unmark Comments or Messages as read.

        :param items: A list containing instances of :class:`.Comment` and/or
            :class:`.Message` to be marked as unread relative to the authorized user's
            inbox.

        Requests are batched at 25 items (Reddit limit).

        For example, to mark the first 10 items as unread try:

        .. code-block:: python

            to_unread = list(reddit.inbox.all(limit=10))
            reddit.inbox.mark_unread(to_unread)

        .. seealso::

            - :meth:`.Comment.mark_unread`
            - :meth:`.Message.mark_unread`

        """
        while items:
            data = {"id": ",".join(x.fullname for x in items[:25])}
            self._reddit.post(API_PATH["unread_message"], data=data)
            items = items[25:]

    def mentions(
        self, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Comment]:
        r"""Return a :class:`.ListingGenerator` for mentions.

        A mention is :class:`.Comment` in which the authorized redditor is named in its
        body like u/spez.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        For example, to output the author and body of the first 25 mentions try:

        .. code-block:: python

            for mention in reddit.inbox.mentions(limit=25):
                print(f"{mention.author}\\n{mention.body}\\n")

        """
        return ListingGenerator(self._reddit, API_PATH["mentions"], **generator_kwargs)

    def message(self, message_id: str) -> praw.models.Message:
        """Return a :class:`.Message` corresponding to ``message_id``.

        :param message_id: The base36 ID of a message.

        For example:

        .. code-block:: python

            message = reddit.inbox.message("7bnlgu")

        """
        listing = self._reddit.get(API_PATH["message"].format(id=message_id))
        messages = {
            message.fullname: message for message in [listing[0]] + listing[0].replies
        }
        for _fullname, message in messages.items():
            message.parent = messages.get(message.parent_id, None)
        return messages[f"t4_{message_id.lower()}"]

    def messages(
        self, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Message]:
        """Return a :class:`.ListingGenerator` for inbox messages.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        For example, to output the subject of the most recent 5 messages try:

        .. code-block:: python

            for message in reddit.inbox.messages(limit=5):
                print(message.subject)

        """
        return ListingGenerator(self._reddit, API_PATH["messages"], **generator_kwargs)

    def sent(
        self, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Message]:
        """Return a :class:`.ListingGenerator` for sent messages.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        For example, to output the recipient of the most recent 15 messages try:

        .. code-block:: python

            for message in reddit.inbox.sent(limit=15):
                print(message.dest)

        """
        return ListingGenerator(self._reddit, API_PATH["sent"], **generator_kwargs)

    def stream(
        self, **stream_options: str | int | dict[str, str]
    ) -> Iterator[praw.models.Comment | praw.models.Message]:
        """Yield new inbox items as they become available.

        Items are yielded oldest first. Up to 100 historical items will initially be
        returned.

        Keyword arguments are passed to :func:`.stream_generator`.

        For example, to retrieve all new inbox items, try:

        .. code-block:: python

            for item in reddit.inbox.stream():
                print(item)

        """
        return stream_generator(self.unread, **stream_options)

    def submission_replies(
        self, **generator_kwargs: str | int | dict[str, str]
    ) -> Iterator[praw.models.Comment]:
        """Return a :class:`.ListingGenerator` for submission replies.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        To output the author of one request worth of submission replies try:

        .. code-block:: python

            for reply in reddit.inbox.submission_replies():
                print(reply.author)

        """
        return ListingGenerator(
            self._reddit, API_PATH["submission_replies"], **generator_kwargs
        )

    def uncollapse(self, items: list[praw.models.Message]):
        """Mark an inbox message as uncollapsed.

        :param items: A list containing instances of :class:`.Message`.

        Requests are batched at 25 items (reddit limit).

        For example, to uncollapse all unread Messages, try:

        .. code-block:: python

            from praw.models import Message

            unread_messages = []
            for item in reddit.inbox.unread(limit=None):
                if isinstance(item, Message):
                    unread_messages.append(item)
            reddit.inbox.uncollapse(unread_messages)

        .. seealso::

            :meth:`.Message.collapse`

        """
        while items:
            data = {"id": ",".join(x.fullname for x in items[:25])}
            self._reddit.post(API_PATH["uncollapse"], data=data)
            items = items[25:]

    @_deprecate_args("mark_read")
    def unread(
        self,
        *,
        mark_read: bool = False,
        **generator_kwargs: str | int | dict[str, str],
    ) -> Iterator[praw.models.Comment | praw.models.Message]:
        """Return a :class:`.ListingGenerator` for unread comments and messages.

        :param mark_read: Marks the inbox as read (default: ``False``).

        .. note::

            This only marks the inbox as read not the messages. Use
            :meth:`.Inbox.mark_read` to mark the messages.

        Additional keyword arguments are passed in the initialization of
        :class:`.ListingGenerator`.

        For example, to output the author of unread comments try:

        .. code-block:: python

            from praw.models import Comment

            for item in reddit.inbox.unread(limit=None):
                if isinstance(item, Comment):
                    print(item.author)

        """
        self._safely_add_arguments(
            arguments=generator_kwargs, key="params", mark=mark_read
        )
        return ListingGenerator(self._reddit, API_PATH["unread"], **generator_kwargs)
