"""Provide the ModNoteMixin class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class ModNoteMixin:
    """Interface for classes that can have a moderator note set on them."""

    def author_notes(
        self, **generator_kwargs: Any
    ) -> Generator[praw.models.ModNote, None, None]:
        """Get the moderator notes for the author of this object in the subreddit it's posted in.

        :param generator_kwargs: Additional keyword arguments are passed in the
            initialization of the moderator note generator.

        :returns: A generator of :class:`.ModNote`.

        For example, to list all notes the author of a submission, try:

        .. code-block:: python

            for note in reddit.submission("92dd8").mod.author_notes():
                print(f"{note.label}: {note.note}")

        """
        return self.thing.subreddit.mod.notes.redditors(
            self.thing.author, **generator_kwargs
        )

    def create_note(
        self, *, label: str | None = None, note: str, **other_settings: Any
    ) -> praw.models.ModNote:
        """Create a moderator note on the author of this object in the subreddit it's posted in.

        :param label: The label for the note. As of this writing, this can be one of the
            following: ``"ABUSE_WARNING"``, ``"BAN"``, ``"BOT_BAN"``,
            ``"HELPFUL_USER"``, ``"PERMA_BAN"``, ``"SOLID_CONTRIBUTOR"``,
            ``"SPAM_WARNING"``, ``"SPAM_WATCH"``, or ``None`` (default: ``None``).
        :param note: The content of the note. As of this writing, this is limited to 250
            characters.
        :param other_settings: Additional keyword arguments are passed to
            :meth:`~.BaseModNotes.create`.

        :returns: The new :class:`.ModNote` object.

        For example, to create a note on a :class:`.Submission`, try:

        .. code-block:: python

            reddit.submission("92dd8").mod.create_note(label="HELPFUL_USER", note="Test note")

        """
        return self.thing.subreddit.mod.notes.create(
            label=label, note=note, thing=self.thing, **other_settings
        )
