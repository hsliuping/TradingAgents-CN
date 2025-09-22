"""Provide classes related to inline media."""

from __future__ import annotations

from ..util import _deprecate_args


class InlineMedia:
    """Provides a way to embed media in self posts."""

    TYPE = None

    def __eq__(self, other: InlineMedia) -> bool:
        """Return whether the other instance equals the current."""
        return all(
            getattr(self, attr) == getattr(other, attr)
            for attr in ["TYPE", "path", "caption", "media_id"]
        )

    @_deprecate_args("path", "caption")
    def __init__(self, *, caption: str = None, path: str):
        """Initialize an :class:`.InlineMedia` instance.

        :param caption: An optional caption to add to the image (default: ``None``).
        :param path: The path to a media file.

        """
        self.path = path
        self.caption = caption
        self.media_id = None

    def __repr__(self) -> str:
        """Return an object initialization representation of the instance."""
        return f"<{self.__class__.__name__} caption={self.caption!r}>"

    def __str__(self) -> str:
        """Return a string representation of the media in Markdown format."""
        return f'\n\n![{self.TYPE}]({self.media_id} "{self.caption if self.caption else ""}")\n\n'


class InlineGif(InlineMedia):
    """Class to provide a gif to embed in text."""

    TYPE = "gif"


class InlineImage(InlineMedia):
    """Class to provide am image to embed in text."""

    TYPE = "img"


class InlineVideo(InlineMedia):
    """Class to provide a video to embed in text."""

    TYPE = "video"
