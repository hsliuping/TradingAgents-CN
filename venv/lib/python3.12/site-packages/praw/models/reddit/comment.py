"""Provide the Comment class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...const import API_PATH
from ...exceptions import ClientException, InvalidURL
from ...util.cache import cachedproperty
from ..comment_forest import CommentForest
from .base import RedditBase
from .mixins import (
    FullnameMixin,
    InboxableMixin,
    ThingModerationMixin,
    UserContentMixin,
)
from .redditor import Redditor

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class Comment(InboxableMixin, UserContentMixin, FullnameMixin, RedditBase):
    """A class that represents a Reddit comment.

    .. include:: ../../typical_attributes.rst

    ================= =================================================================
    Attribute         Description
    ================= =================================================================
    ``author``        Provides an instance of :class:`.Redditor`.
    ``body``          The body of the comment, as Markdown.
    ``body_html``     The body of the comment, as HTML.
    ``created_utc``   Time the comment was created, represented in `Unix Time`_.
    ``distinguished`` Whether or not the comment is distinguished.
    ``edited``        Whether or not the comment has been edited.
    ``id``            The ID of the comment.
    ``is_submitter``  Whether or not the comment author is also the author of the
                      submission.
    ``link_id``       The submission ID that the comment belongs to.
    ``parent_id``     The ID of the parent comment (prefixed with ``t1_``). If it is a
                      top-level comment, this returns the submission ID instead
                      (prefixed with ``t3_``).
    ``permalink``     A permalink for the comment. :class:`.Comment` objects from the
                      inbox have a ``context`` attribute instead.
    ``replies``       Provides an instance of :class:`.CommentForest`.
    ``saved``         Whether or not the comment is saved.
    ``score``         The number of upvotes for the comment.
    ``stickied``      Whether or not the comment is stickied.
    ``submission``    Provides an instance of :class:`.Submission`. The submission that
                      the comment belongs to.
    ``subreddit``     Provides an instance of :class:`.Subreddit`. The subreddit that
                      the comment belongs to.
    ``subreddit_id``  The subreddit ID that the comment belongs to.
    ================= =================================================================

    .. _unix time: https://en.wikipedia.org/wiki/Unix_time

    """

    MISSING_COMMENT_MESSAGE = "This comment does not appear to be in the comment tree"
    STR_FIELD = "id"

    @staticmethod
    def id_from_url(url: str) -> str:
        """Get the ID of a comment from the full URL."""
        parts = RedditBase._url_parts(url)
        try:
            comment_index = parts.index("comments")
        except ValueError:
            raise InvalidURL(url) from None

        if len(parts) - 4 != comment_index:
            raise InvalidURL(url)
        return parts[-1]

    @cachedproperty
    def mod(self) -> praw.models.reddit.comment.CommentModeration:
        """Provide an instance of :class:`.CommentModeration`.

        Example usage:

        .. code-block:: python

            comment = reddit.comment("dkk4qjd")
            comment.mod.approve()

        """
        return CommentModeration(self)

    @property
    def _kind(self):
        """Return the class's kind."""
        return self._reddit.config.kinds["comment"]

    @property
    def is_root(self) -> bool:
        """Return ``True`` when the comment is a top-level comment."""
        parent_type = self.parent_id.split("_", 1)[0]
        return parent_type == self._reddit.config.kinds["submission"]

    @property
    def replies(self) -> CommentForest:
        """Provide an instance of :class:`.CommentForest`.

        This property may return an empty list if the comment has not been refreshed
        with :meth:`.refresh`

        Sort order and reply limit can be set with the ``reply_sort`` and
        ``reply_limit`` attributes before replies are fetched, including any call to
        :meth:`.refresh`:

        .. code-block:: python

            comment.reply_sort = "new"
            comment.refresh()
            replies = comment.replies

        .. note::

            The appropriate values for ``reply_sort`` include ``"confidence"``,
            ``"controversial"``, ``"new"``, ``"old"``, ``"q&a"``, and ``"top"``.

        """
        if isinstance(self._replies, list):
            self._replies = CommentForest(self.submission, self._replies)
        return self._replies

    @property
    def submission(self) -> praw.models.Submission:
        """Return the :class:`.Submission` object this comment belongs to."""
        if not self._submission:  # Comment not from submission
            self._submission = self._reddit.submission(self._extract_submission_id())
        return self._submission

    @submission.setter
    def submission(self, submission: praw.models.Submission):
        """Update the :class:`.Submission` associated with the :class:`.Comment`."""
        submission._comments_by_id[self.fullname] = self
        self._submission = submission
        for reply in getattr(self, "replies", []):
            reply.submission = submission

    def __init__(
        self,
        reddit: praw.Reddit,
        id: str | None = None,
        url: str | None = None,
        _data: dict[str, Any] | None = None,
    ):
        """Initialize a :class:`.Comment` instance."""
        if (id, url, _data).count(None) != 2:
            msg = "Exactly one of 'id', 'url', or '_data' must be provided."
            raise TypeError(msg)
        fetched = False
        self._replies = []
        self._submission = None
        if id:
            self.id = id
        elif url:
            self.id = self.id_from_url(url)
        else:
            fetched = True
        super().__init__(reddit, _data=_data, _fetched=fetched)

    def __setattr__(
        self,
        attribute: str,
        value: str | Redditor | CommentForest | praw.models.Subreddit,
    ):
        """Objectify author, replies, and subreddit."""
        if attribute == "author":
            value = Redditor.from_data(self._reddit, value)
        elif attribute == "replies":
            if value == "":
                value = []
            else:
                value = self._reddit._objector.objectify(value).children
            attribute = "_replies"
        elif attribute == "subreddit":
            value = self._reddit.subreddit(value)
        super().__setattr__(attribute, value)

    def _extract_submission_id(self):
        if "context" in self.__dict__:
            return self.context.rsplit("/", 4)[1]
        return self.link_id.split("_", 1)[1]

    def _fetch(self):
        data = self._fetch_data()
        data = data["data"]

        if not data["children"]:
            msg = f"No data returned for comment {self.fullname}"
            raise ClientException(msg)

        comment_data = data["children"][0]["data"]
        other = type(self)(self._reddit, _data=comment_data)
        self.__dict__.update(other.__dict__)
        super()._fetch()

    def _fetch_info(self):
        return "info", {}, {"id": self.fullname}

    def parent(
        self,
    ) -> Comment | praw.models.Submission:
        """Return the parent of the comment.

        The returned parent will be an instance of either :class:`.Comment`, or
        :class:`.Submission`.

        If this comment was obtained through a :class:`.Submission`, then its entire
        ancestry should be immediately available, requiring no extra network requests.
        However, if this comment was obtained through other means, e.g.,
        ``reddit.comment("COMMENT_ID")``, or ``reddit.inbox.comment_replies``, then the
        returned parent may be a lazy instance of either :class:`.Comment`, or
        :class:`.Submission`.

        Lazy comment example:

        .. code-block:: python

            comment = reddit.comment("cklhv0f")
            parent = comment.parent()
            # 'replies' is empty until the comment is refreshed
            print(parent.replies)  # Output: []
            parent.refresh()
            print(parent.replies)  # Output is at least: [Comment(id="cklhv0f")]

        .. warning::

            Successive calls to :meth:`.parent` may result in a network request per call
            when the comment is not obtained through a :class:`.Submission`. See below
            for an example of how to minimize requests.

        If you have a deeply nested comment and wish to most efficiently discover its
        top-most :class:`.Comment` ancestor you can chain successive calls to
        :meth:`.parent` with calls to :meth:`.refresh` at every 9 levels. For example:

        .. code-block:: python

            comment = reddit.comment("dkk4qjd")
            ancestor = comment
            refresh_counter = 0
            while not ancestor.is_root:
                ancestor = ancestor.parent()
                if refresh_counter % 9 == 0:
                    ancestor.refresh()
                refresh_counter += 1
            print(f"Top-most Ancestor: {ancestor}")

        The above code should result in 5 network requests to Reddit. Without the calls
        to :meth:`.refresh` it would make at least 31 network requests.

        """
        if self.parent_id == self.submission.fullname:
            return self.submission

        if self.parent_id in self.submission._comments_by_id:
            # The Comment already exists, so simply return it
            return self.submission._comments_by_id[self.parent_id]

        parent = Comment(self._reddit, self.parent_id.split("_", 1)[1])
        parent._submission = self.submission
        return parent

    def refresh(self) -> Comment:
        """Refresh the comment's attributes.

        If using :meth:`.Reddit.comment` this method must be called in order to obtain
        the comment's replies.

        Example usage:

        .. code-block:: python

            comment = reddit.comment("dkk4qjd")
            comment.refresh()

        """
        if "context" in self.__dict__:  # Using hasattr triggers a fetch
            comment_path = self.context.split("?", 1)[0]
        else:
            path = API_PATH["submission"].format(id=self.submission.id)
            comment_path = f"{path}_/{self.id}"

        # The context limit appears to be 8, but let's ask for more anyway.
        params = {"context": 100}
        if "reply_limit" in self.__dict__:
            params["limit"] = self.reply_limit
        if "reply_sort" in self.__dict__:
            params["sort"] = self.reply_sort
        comment_list = self._reddit.get(comment_path, params=params)[1].children
        if not comment_list:
            raise ClientException(self.MISSING_COMMENT_MESSAGE)

        # With context, the comment may be nested so we have to find it
        comment = None
        queue = comment_list[:]
        while queue and (comment is None or comment.id != self.id):
            comment = queue.pop()
            if isinstance(comment, Comment):
                queue.extend(comment._replies)

        if comment.id != self.id:
            raise ClientException(self.MISSING_COMMENT_MESSAGE)

        if self._submission is not None:
            del comment.__dict__["_submission"]  # Don't replace if set
        self.__dict__.update(comment.__dict__)

        for reply in comment_list:
            reply.submission = self.submission
        return self


class CommentModeration(ThingModerationMixin):
    """Provide a set of functions pertaining to :class:`.Comment` moderation.

    Example usage:

    .. code-block:: python

        comment = reddit.comment("dkk4qjd")
        comment.mod.approve()

    """

    REMOVAL_MESSAGE_API = "removal_comment_message"

    def __init__(self, comment: praw.models.Comment):
        """Initialize a :class:`.CommentModeration` instance.

        :param comment: The comment to moderate.

        """
        self.thing = comment

    def show(self):
        """Uncollapse a :class:`.Comment` that has been collapsed by Crowd Control.

        Example usage:

        .. code-block:: python

            # Uncollapse a comment:
            comment = reddit.comment("dkk4qjd")
            comment.mod.show()

        """
        url = API_PATH["show_comment"]

        self.thing._reddit.post(url, data={"id": self.thing.fullname})
