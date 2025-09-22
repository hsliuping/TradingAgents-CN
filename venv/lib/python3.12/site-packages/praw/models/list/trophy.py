"""Provide the TrophyList class."""

from .base import BaseList


class TrophyList(BaseList):
    """A list of :class:`.Trophy` objects. Works just like a regular list.

    This class is solely used to parse responses from Reddit, so end users should not
    use this class directly.

    """

    CHILD_ATTRIBUTE = "trophies"
