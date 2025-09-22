"""Provide the EditableMixin class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....const import API_PATH

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class EditableMixin:
    """Interface for classes that can be edited and deleted."""

    def delete(self):
        """Delete the object.

        Example usage:

        .. code-block:: python

            comment = reddit.comment("dkk4qjd")
            comment.delete()

            submission = reddit.submission("8dmv8z")
            submission.delete()

        """
        self._reddit.post(API_PATH["del"], data={"id": self.fullname})

    def edit(self, body: str) -> praw.models.Comment | praw.models.Submission:
        """Replace the body of the object with ``body``.

        :param body: The Markdown formatted content for the updated object.

        :returns: The current instance after updating its attributes.

        Example usage:

        .. code-block:: python

            comment = reddit.comment("dkk4qjd")

            # construct the text of an edited comment
            # by appending to the old body:
            edited_body = comment.body + "Edit: thanks for the gold!"
            comment.edit(edited_body)

        """
        data = {
            "text": body,
            "thing_id": self.fullname,
            "validate_on_submit": self._reddit.validate_on_submit,
        }
        updated = self._reddit.post(API_PATH["edit"], data=data)[0]
        for attribute in [
            "_fetched",
            "_reddit",
            "_submission",
            "replies",
            "subreddit",
        ]:
            if attribute in updated.__dict__:
                delattr(updated, attribute)
        self.__dict__.update(updated.__dict__)
        return self
