"""Provide the ReplyableMixin class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....const import API_PATH

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class ReplyableMixin:
    """Interface for :class:`.RedditBase` classes that can be replied to."""

    def reply(self, body: str) -> praw.models.Comment | praw.models.Message | None:
        """Reply to the object.

        :param body: The Markdown formatted content for a comment.

        :returns: A :class:`.Comment` or :class:`.Message` object for the newly created
            comment or message or ``None`` if Reddit doesn't provide one.

        :raises: ``prawcore.exceptions.Forbidden`` when attempting to reply to some
            items, such as locked submissions/comments or non-replyable messages.

        A ``None`` value can be returned if the target is a comment or submission in a
        quarantined subreddit and the authenticated user has not opt-ed into viewing the
        content. When this happens the comment will be successfully created on Reddit
        and can be retried by drawing the comment from the user's comment history.

        Example usage:

        .. code-block:: python

            submission = reddit.submission("5or86n")
            submission.reply("reply")

            comment = reddit.comment("dxolpyc")
            comment.reply("reply")

        """
        data = {"text": body, "thing_id": self.fullname}
        comments = self._reddit.post(API_PATH["comment"], data=data)
        try:
            return comments[0]
        except IndexError:
            return None
