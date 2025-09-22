"""Provide the BaseList class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

from ..base import PRAWBase

if TYPE_CHECKING:  # pragma: no cover
    import praw


class BaseList(PRAWBase):
    """An abstract class to coerce a list into a :class:`.PRAWBase`."""

    CHILD_ATTRIBUTE = None

    def __contains__(self, item: Any) -> bool:
        """Test if item exists in the list."""
        return item in getattr(self, self.CHILD_ATTRIBUTE)

    def __getitem__(self, index: int) -> Any:
        """Return the item at position index in the list."""
        return getattr(self, self.CHILD_ATTRIBUTE)[index]

    def __init__(self, reddit: praw.Reddit, _data: dict[str, Any]):
        """Initialize a :class:`.BaseList` instance.

        :param reddit: An instance of :class:`.Reddit`.

        """
        super().__init__(reddit, _data=_data)

        if self.CHILD_ATTRIBUTE is None:
            msg = "BaseList must be extended."
            raise NotImplementedError(msg)

        child_list = getattr(self, self.CHILD_ATTRIBUTE)
        for index, item in enumerate(child_list):
            child_list[index] = reddit._objector.objectify(item)

    def __iter__(self) -> Iterator[Any]:
        """Return an iterator to the list."""
        return getattr(self, self.CHILD_ATTRIBUTE).__iter__()

    def __len__(self) -> int:
        """Return the number of items in the list."""
        return len(getattr(self, self.CHILD_ATTRIBUTE))

    def __str__(self) -> str:
        """Return a string representation of the list."""
        return str(getattr(self, self.CHILD_ATTRIBUTE))
