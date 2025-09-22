"""Provide the ModAction class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import PRAWBase

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class ModAction(PRAWBase):
    """Represent a moderator action."""

    @property
    def mod(self) -> praw.models.Redditor:
        """Return the :class:`.Redditor` who the action was issued by."""
        return self._reddit.redditor(self._mod)

    @mod.setter
    def mod(self, value: str | praw.models.Redditor):
        self._mod = value
