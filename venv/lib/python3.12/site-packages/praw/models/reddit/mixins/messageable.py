"""Provide the MessageableMixin class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....const import API_PATH
from ....util import _deprecate_args

if TYPE_CHECKING:  # pragma: no cover
    import praw


class MessageableMixin:
    """Interface for classes that can be messaged."""

    @_deprecate_args("subject", "message", "from_subreddit")
    def message(
        self,
        *,
        from_subreddit: praw.models.Subreddit | str | None = None,
        message: str,
        subject: str,
    ):
        """Send a message to a :class:`.Redditor` or a :class:`.Subreddit`'s moderators (modmail).

        :param from_subreddit: A :class:`.Subreddit` instance or string to send the
            message from. When provided, messages are sent from the subreddit rather
            than from the authenticated user.

            .. note::

                The authenticated user must be a moderator of the subreddit and have the
                ``mail`` moderator permission.

        :param message: The message content.
        :param subject: The subject of the message.

        For example, to send a private message to u/spez, try:

        .. code-block:: python

            reddit.redditor("spez").message(subject="TEST", message="test message from PRAW")

        To send a message to u/spez from the moderators of r/test try:

        .. code-block:: python

            reddit.redditor("spez").message(
                subject="TEST", message="test message from r/test", from_subreddit="test"
            )

        To send a message to the moderators of r/test, try:

        .. code-block:: python

            reddit.subreddit("test").message(subject="TEST", message="test PM from PRAW")

        """
        data = {
            "subject": subject,
            "text": message,
            "to": f"{getattr(self.__class__, 'MESSAGE_PREFIX', '')}{self}",
        }
        if from_subreddit:
            data["from_sr"] = str(from_subreddit)
        self._reddit.post(API_PATH["compose"], data=data)
