"""Provide CommentForest for submission comments."""

from __future__ import annotations

from heapq import heappop, heappush
from typing import TYPE_CHECKING

from ..exceptions import DuplicateReplaceException
from ..util import _deprecate_args
from .reddit.more import MoreComments

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class CommentForest:
    """A forest of comments starts with multiple top-level comments.

    Each of these comments can be a tree of replies.

    """

    def __getitem__(self, index: int) -> praw.models.Comment:
        """Return the comment at position ``index`` in the list.

        This method is to be used like an array access, such as:

        .. code-block:: python

            first_comment = submission.comments[0]

        Alternatively, the presence of this method enables one to iterate over all top
        level comments, like so:

        .. code-block:: python

            for comment in submission.comments:
                print(comment.body)

        """
        return self._comments[index]

    def __len__(self) -> int:
        """Return the number of top-level comments in the forest."""
        return len(self._comments)

    def _insert_comment(self, comment: praw.models.Comment):
        if comment.name in self._submission._comments_by_id:
            raise DuplicateReplaceException
        comment.submission = self._submission
        if isinstance(comment, MoreComments) or comment.is_root:
            self._comments.append(comment)
        else:
            assert comment.parent_id in self._submission._comments_by_id, (
                "PRAW Error occurred. Please file a bug report and include the code"
                " that caused the error."
            )
            parent = self._submission._comments_by_id[comment.parent_id]
            parent.replies._comments.append(comment)

    def list(  # noqa: A003
        self,
    ) -> list[praw.models.Comment | praw.models.MoreComments]:
        """Return a flattened list of all comments.

        This list may contain :class:`.MoreComments` instances if :meth:`.replace_more`
        was not called first.

        """
        comments = []
        queue = list(self)
        while queue:
            comment = queue.pop(0)
            comments.append(comment)
            if not isinstance(comment, MoreComments):
                queue.extend(comment.replies)
        return comments

    @staticmethod
    def _gather_more_comments(
        tree: list[praw.models.MoreComments],
        *,
        parent_tree: list[praw.models.MoreComments] | None = None,
    ) -> list[MoreComments]:
        """Return a list of :class:`.MoreComments` objects obtained from tree."""
        more_comments = []
        queue = [(None, x) for x in tree]
        while queue:
            parent, comment = queue.pop(0)
            if isinstance(comment, MoreComments):
                heappush(more_comments, comment)
                if parent:
                    comment._remove_from = parent.replies._comments
                else:
                    comment._remove_from = parent_tree or tree
            else:
                for item in comment.replies:
                    queue.append((comment, item))
        return more_comments

    def __init__(
        self,
        submission: praw.models.Submission,
        comments: list[praw.models.Comment] | None = None,
    ):
        """Initialize a :class:`.CommentForest` instance.

        :param submission: An instance of :class:`.Submission` that is the parent of the
            comments.
        :param comments: Initialize the forest with a list of comments (default:
            ``None``).

        """
        self._comments = comments
        self._submission = submission

    def _update(self, comments: list[praw.models.Comment]):
        self._comments = comments
        for comment in comments:
            comment.submission = self._submission

    @_deprecate_args("limit", "threshold")
    def replace_more(
        self, *, limit: int | None = 32, threshold: int = 0
    ) -> list[praw.models.MoreComments]:
        """Update the comment forest by resolving instances of :class:`.MoreComments`.

        :param limit: The maximum number of :class:`.MoreComments` instances to replace.
            Each replacement requires 1 API request. Set to ``None`` to have no limit,
            or to ``0`` to remove all :class:`.MoreComments` instances without
            additional requests (default: ``32``).
        :param threshold: The minimum number of children comments a
            :class:`.MoreComments` instance must have in order to be replaced.
            :class:`.MoreComments` instances that represent "continue this thread" links
            unfortunately appear to have 0 children (default: ``0``).

        :returns: A list of :class:`.MoreComments` instances that were not replaced.

        :raises: ``prawcore.TooManyRequests`` when used concurrently.

        For example, to replace up to 32 :class:`.MoreComments` instances of a
        submission try:

        .. code-block:: python

            submission = reddit.submission("3hahrw")
            submission.comments.replace_more()

        Alternatively, to replace :class:`.MoreComments` instances within the replies of
        a single comment try:

        .. code-block:: python

            comment = reddit.comment("d8r4im1")
            comment.refresh()
            comment.replies.replace_more()

        .. note::

            This method can take a long time as each replacement will discover at most
            100 new :class:`.Comment` instances. As a result, consider looping and
            handling exceptions until the method returns successfully. For example:

            .. code-block:: python

                while True:
                    try:
                        submission.comments.replace_more()
                        break
                    except PossibleExceptions:
                        print("Handling replace_more exception")
                        sleep(1)

        .. warning::

            If this method is called, and the comments are refreshed, calling this
            method again will result in a :class:`.DuplicateReplaceException`.

        """
        remaining = limit
        more_comments = self._gather_more_comments(self._comments)
        skipped = []

        # Fetch largest more_comments until reaching the limit or the threshold
        while more_comments:
            item = heappop(more_comments)
            if remaining is not None and remaining <= 0 or item.count < threshold:
                skipped.append(item)
                item._remove_from.remove(item)
                continue

            new_comments = item.comments(update=False)
            if remaining is not None:
                remaining -= 1

            # Add new MoreComment objects to the heap of more_comments
            for more in self._gather_more_comments(
                new_comments, parent_tree=self._comments
            ):
                more.submission = self._submission
                heappush(more_comments, more)
            # Insert all items into the tree
            for comment in new_comments:
                self._insert_comment(comment)

            # Remove from forest
            item._remove_from.remove(item)

        return more_comments + skipped
