"""Provide the ReportableMixin class."""

from ....const import API_PATH


class ReportableMixin:
    """Interface for :class:`.RedditBase` classes that can be reported."""

    def report(self, reason: str):
        """Report this object to the moderators of its subreddit.

        :param reason: The reason for reporting.

        :raises: :class:`.RedditAPIException` if ``reason`` is longer than 100
            characters.

        Example usage:

        .. code-block:: python

            submission = reddit.submission("5or86n")
            submission.report("report reason")

            comment = reddit.comment("dxolpyc")
            comment.report("report reason")

        """
        self._reddit.post(
            API_PATH["report"], data={"id": self.fullname, "reason": reason}
        )
