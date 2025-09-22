"""Provide the MoreComments class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...const import API_PATH
from ...util import _deprecate_args
from ..base import PRAWBase

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class MoreComments(PRAWBase):
    """A class indicating there are more comments."""

    def __eq__(self, other: str | MoreComments) -> bool:
        """Return ``True`` if these :class:`.MoreComments` instances are the same."""
        if isinstance(other, self.__class__):
            return self.count == other.count and self.children == other.children
        return super().__eq__(other)

    def __init__(self, reddit: praw.Reddit, _data: dict[str, Any]):
        """Initialize a :class:`.MoreComments` instance."""
        self.count = self.parent_id = None
        self.children = []
        super().__init__(reddit, _data=_data)
        self._comments = None
        self.submission = None

    def __lt__(self, other: MoreComments) -> bool:
        """Provide a sort order on the :class:`.MoreComments` object."""
        # To work with heapq a "smaller" item is the one with the most comments. We are
        # intentionally making the biggest element the smallest element to turn the
        # min-heap implementation in heapq into a max-heap.
        return self.count > other.count

    def __repr__(self) -> str:
        """Return an object initialization representation of the instance."""
        children = self.children[:4]
        if len(self.children) > 4:
            children[-1] = "..."
        return f"<{self.__class__.__name__} count={self.count}, children={children!r}>"

    def _continue_comments(self, update: bool):
        assert not self.children, "Please file a bug report with PRAW."
        parent = self._load_comment(self.parent_id.split("_", 1)[1])
        self._comments = parent.replies
        if update:
            for comment in self._comments:
                comment.submission = self.submission
        return self._comments

    def _load_comment(self, comment_id: str):
        path = f"{API_PATH['submission'].format(id=self.submission.id)}_/{comment_id}"
        _, comments = self._reddit.get(
            path,
            params={
                "limit": self.submission.comment_limit,
                "sort": self.submission.comment_sort,
            },
        )
        assert len(comments.children) == 1, "Please file a bug report with PRAW."
        return comments.children[0]

    @_deprecate_args("update")
    def comments(self, *, update: bool = True) -> list[praw.models.Comment]:
        """Fetch and return the comments for a single :class:`.MoreComments` object."""
        if self._comments is None:
            if self.count == 0:  # Handle "continue this thread"
                return self._continue_comments(update)
            assert self.children, "Please file a bug report with PRAW."
            data = {
                "children": ",".join(self.children),
                "link_id": self.submission.fullname,
                "sort": self.submission.comment_sort,
            }
            self._comments = self._reddit.post(API_PATH["morechildren"], data=data)
            if update:
                for comment in self._comments:
                    comment.submission = self.submission
        return self._comments
