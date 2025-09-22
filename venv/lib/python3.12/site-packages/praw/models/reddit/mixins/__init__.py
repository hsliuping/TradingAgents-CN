"""Package providing reddit class mixins."""

from __future__ import annotations

from json import dumps
from typing import TYPE_CHECKING, Optional

from ....const import API_PATH
from ....util import _deprecate_args
from .editable import EditableMixin
from .fullname import FullnameMixin
from .gildable import GildableMixin
from .inboxable import InboxableMixin
from .inboxtoggleable import InboxToggleableMixin
from .messageable import MessageableMixin
from .modnote import ModNoteMixin
from .replyable import ReplyableMixin
from .reportable import ReportableMixin
from .savable import SavableMixin
from .votable import VotableMixin

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class ThingModerationMixin(ModNoteMixin):
    r"""Provides moderation methods for :class:`.Comment`\ s and :class:`.Submission`\ s."""

    REMOVAL_MESSAGE_API = None

    def _add_removal_reason(self, *, mod_note: str = "", reason_id: str | None = None):
        """Add a removal reason for a :class:`.Comment` or :class:`.Submission`.

        :param mod_note: A message for the other moderators.
        :param reason_id: The removal reason ID.

        It is necessary to first call :meth:`.remove` on the :class:`.Comment` or
        :class:`.Submission`.

        If ``reason_id`` is not specified, ``mod_note`` cannot be blank.

        """
        if not reason_id and not mod_note:
            msg = "mod_note cannot be blank if reason_id is not specified"
            raise ValueError(msg)
        # Only the first element of the item_id list is used.
        data = {
            "item_ids": [self.thing.fullname],
            "mod_note": mod_note,
            "reason_id": reason_id,
        }
        self.thing._reddit.post(API_PATH["removal_reasons"], data={"json": dumps(data)})

    def approve(self):
        """Approve a :class:`.Comment` or :class:`.Submission`.

        Approving a comment or submission reverts a removal, resets the report counter,
        adds a green check mark indicator (only visible to other moderators) on the
        website view, and sets the ``approved_by`` attribute to the authenticated user.

        Example usage:

        .. code-block:: python

            # approve a comment:
            comment = reddit.comment("dkk4qjd")
            comment.mod.approve()
            # approve a submission:
            submission = reddit.submission("5or86n")
            submission.mod.approve()

        """
        self.thing._reddit.post(API_PATH["approve"], data={"id": self.thing.fullname})

    @_deprecate_args("how", "sticky")
    def distinguish(self, *, how: str = "yes", sticky: bool = False):
        """Distinguish a :class:`.Comment` or :class:`.Submission`.

        :param how: One of ``"yes"``, ``"no"``, ``"admin"``, or ``"special"``. ``"yes"``
            adds a moderator level distinguish. ``"no"`` removes any distinction.
            ``"admin"`` and ``"special"`` require special user privileges to use
            (default ``"yes"``).
        :param sticky: :class:`.Comment` is stickied if ``True``, placing it at the top
            of the comment page regardless of score. If thing is not a top-level
            comment, this parameter is silently ignored (default ``False``).

        Example usage:

        .. code-block:: python

            # distinguish and sticky a comment:
            comment = reddit.comment("dkk4qjd")
            comment.mod.distinguish(sticky=True)
            # undistinguish a submission:
            submission = reddit.submission("5or86n")
            submission.mod.distinguish(how="no")

        .. seealso::

            :meth:`.undistinguish`

        """
        data = {"how": how, "id": self.thing.fullname}
        if sticky and getattr(self.thing, "is_root", False):
            data["sticky"] = True
        self.thing._reddit.post(API_PATH["distinguish"], data=data)

    def ignore_reports(self):
        """Ignore future reports on a :class:`.Comment` or :class:`.Submission`.

        Calling this method will prevent future reports on this :class:`.Comment` or
        :class:`.Submission` from both triggering notifications and appearing in the
        various moderation listings. The report count will still increment on the
        :class:`.Comment` or :class:`.Submission`.

        Example usage:

        .. code-block:: python

            # ignore future reports on a comment:
            comment = reddit.comment("dkk4qjd")
            comment.mod.ignore_reports()
            # ignore future reports on a submission:
            submission = reddit.submission("5or86n")
            submission.mod.ignore_reports()

        .. seealso::

            :meth:`.unignore_reports`

        """
        self.thing._reddit.post(
            API_PATH["ignore_reports"], data={"id": self.thing.fullname}
        )

    def lock(self):
        """Lock a :class:`.Comment` or :class:`.Submission`.

        Example usage:

        .. code-block:: python

            # lock a comment:
            comment = reddit.comment("dkk4qjd")
            comment.mod.lock()
            # lock a submission:
            submission = reddit.submission("5or86n")
            submission.mod.lock()

        .. seealso::

            :meth:`.unlock`

        """
        self.thing._reddit.post(API_PATH["lock"], data={"id": self.thing.fullname})

    @_deprecate_args("spam", "mod_note", "reason_id")
    def remove(
        self, *, mod_note: str = "", spam: bool = False, reason_id: str | None = None
    ):
        """Remove a :class:`.Comment` or :class:`.Submission`.

        :param mod_note: A message for the other moderators.
        :param spam: When ``True``, use the removal to help train the
            :class:`.Subreddit`'s spam filter (default: ``False``).
        :param reason_id: The removal reason ID.

        If either ``reason_id`` or ``mod_note`` are provided, a second API call is made
        to add the removal reason.

        Example usage:

        .. code-block:: python

            # remove a comment and mark as spam:
            comment = reddit.comment("dkk4qjd")
            comment.mod.remove(spam=True)
            # remove a submission
            submission = reddit.submission("5or86n")
            submission.mod.remove()
            # remove a submission with a removal reason
            reason = reddit.subreddit.mod.removal_reasons["110ni21zo23ql"]
            submission = reddit.submission("5or86n")
            submission.mod.remove(reason_id=reason.id)

        """
        data = {"id": self.thing.fullname, "spam": bool(spam)}
        self.thing._reddit.post(API_PATH["remove"], data=data)
        if any([reason_id, mod_note]):
            self._add_removal_reason(mod_note=mod_note, reason_id=reason_id)

    @_deprecate_args("message", "title", "type")
    def send_removal_message(
        self,
        *,
        message: str,
        title: str = "ignored",
        type: str = "public",
    ) -> praw.models.Comment | None:
        """Send a removal message for a :class:`.Comment` or :class:`.Submission`.

        .. warning::

            The object has to be removed before giving it a removal reason. Remove the
            object with :meth:`.remove`. Trying to add a removal reason without removing
            the object will result in :class:`.RedditAPIException` being thrown with an
            ``INVALID_ID`` error_type.

        Reddit adds human-readable information about the object to the message.

        :param type: One of ``"public"``, ``"public_as_subreddit"``, ``"private"``, or
            ``"private_exposed"``. ``"public"`` leaves a stickied comment on the post.
            ``"public_as_subreddit"`` leaves a stickied comment on the post with the
            u/subreddit-ModTeam account. ``"private"`` sends a modmail message with
            hidden username. ``"private_exposed"`` sends a modmail message without
            hidden username (default: ``"public"``).
        :param title: The short reason given in the message. Ignored if type is
            ``"public"`` or ``"public_as_subreddit"``.
        :param message: The body of the message.

        :returns: The new :class:`.Comment` if ``type`` is ``"public"`` or
            ``"public_as_subreddit"``.

        """
        # The API endpoint used to send removal messages is different for posts and
        # comments, so the derived classes specify which one.
        if self.REMOVAL_MESSAGE_API is None:
            msg = "ThingModerationMixin must be extended."
            raise NotImplementedError(msg)
        url = API_PATH[self.REMOVAL_MESSAGE_API]

        # Only the first element of the item_id list is used.
        data = {
            "item_id": [self.thing.fullname],
            "message": message,
            "title": title,
            "type": type,
        }

        return self.thing._reddit.post(url, data={"json": dumps(data)}) or None

    def undistinguish(self):
        """Remove mod, admin, or special distinguishing from an object.

        Also unstickies the object if applicable.

        Example usage:

        .. code-block:: python

            # undistinguish a comment:
            comment = reddit.comment("dkk4qjd")
            comment.mod.undistinguish()
            # undistinguish a submission:
            submission = reddit.submission("5or86n")
            submission.mod.undistinguish()

        .. seealso::

            :meth:`.distinguish`

        """
        self.distinguish(how="no")

    def unignore_reports(self):
        """Resume receiving future reports on a :class:`.Comment` or :class:`.Submission`.

        Future reports on this :class:`.Comment` or :class:`.Submission` will cause
        notifications, and appear in the various moderation listings.

        Example usage:

        .. code-block:: python

            # accept future reports on a comment:
            comment = reddit.comment("dkk4qjd")
            comment.mod.unignore_reports()
            # accept future reports on a submission:
            submission = reddit.submission("5or86n")
            submission.mod.unignore_reports()

        .. seealso::

            :meth:`.ignore_reports`

        """
        self.thing._reddit.post(
            API_PATH["unignore_reports"], data={"id": self.thing.fullname}
        )

    def unlock(self):
        """Unlock a :class:`.Comment` or :class:`.Submission`.

        Example usage:

        .. code-block:: python

            # unlock a comment:
            comment = reddit.comment("dkk4qjd")
            comment.mod.unlock()
            # unlock a submission:
            submission = reddit.submission("5or86n")
            submission.mod.unlock()

        .. seealso::

            :meth:`.lock`

        """
        self.thing._reddit.post(API_PATH["unlock"], data={"id": self.thing.fullname})


class UserContentMixin(
    EditableMixin,
    GildableMixin,
    InboxToggleableMixin,
    ReplyableMixin,
    ReportableMixin,
    SavableMixin,
    VotableMixin,
):
    """A convenience mixin that applies to both Comments and Submissions."""
