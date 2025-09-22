"""Caching utilities."""

from __future__ import annotations

from typing import Any, Callable


class cachedproperty:  # noqa: N801
    """A decorator for caching a property's result.

    Similar to :py:class:`property`, but the wrapped method's result is cached on the
    instance. This is achieved by setting an entry in the object's instance dictionary
    with the same name as the property. When the name is later accessed, the value in
    the instance dictionary takes precedence over the (non-data descriptor) property.

    This is useful for implementing lazy-loaded properties.

    The cache can be invalidated via :py:meth:`delattr`, or by modifying ``__dict__``
    directly. It will be repopulated on next access.

    .. versionadded:: 6.3.0

    """

    # This to make sphinx run properly
    def __call__(self, *args: Any, **kwargs: Any):  # pragma: no cover
        """Empty method to make sphinx run properly."""

    def __get__(self, obj: Any | None, objtype: Any | None = None) -> Any:
        """Implement descriptor getter.

        Calculate the property's value and then store it in the associated object's
        instance dictionary.

        """
        if obj is None:
            return self

        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value

    def __init__(self, func: Callable[[Any], Any], doc: str | None = None):
        """Initialize a :class:`.cachedproperty` instance."""
        self.func = self.__wrapped__ = func

        if doc is None:
            doc = func.__doc__
        self.__doc__ = doc

    def __repr__(self) -> str:
        """Return an object initialization representation of the instance."""
        return f"<{self.__class__.__name__} {self.func}>"
