"""Provide Collections functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...const import API_PATH
from ...exceptions import ClientException
from ...util import _deprecate_args
from ...util.cache import cachedproperty
from ..base import PRAWBase
from .base import RedditBase
from .submission import Submission
from .subreddit import Subreddit

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator

    import praw.models


class CollectionModeration(PRAWBase):
    """Class to support moderation actions on a :class:`.Collection`.

    Obtain an instance via:

    .. code-block:: python

        reddit.subreddit("test").collections("some_uuid").mod

    """

    def __init__(self, reddit: praw.Reddit, collection_id: str):
        """Initialize a :class:`.CollectionModeration` instance.

        :param collection_id: The ID of a :class:`.Collection`.

        """
        super().__init__(reddit, _data=None)
        self.collection_id = collection_id

    def _post_fullname(self, post: str | praw.models.Submission) -> str:
        """Get a post's fullname.

        :param post: A fullname, a :class:`.Submission`, a permalink, or an ID.

        :returns: The fullname of the post.

        """
        if isinstance(post, Submission):
            return post.fullname
        if not isinstance(post, str):
            msg = f"Cannot get fullname from object of type {type(post)}."
            raise TypeError(msg)
        if post.startswith(f"{self._reddit.config.kinds['submission']}_"):
            return post
        try:
            return self._reddit.submission(url=post).fullname
        except ClientException:
            return self._reddit.submission(post).fullname

    def add_post(self, submission: praw.models.Submission):
        """Add a post to the collection.

        :param submission: The post to add, a :class:`.Submission`, its permalink as a
            ``str``, its fullname as a ``str``, or its ID as a ``str``.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            collection.mod.add_post("bgibu9")

        .. seealso::

            :meth:`.remove_post`

        """
        link_fullname = self._post_fullname(submission)

        self._reddit.post(
            API_PATH["collection_add_post"],
            data={"collection_id": self.collection_id, "link_fullname": link_fullname},
        )

    def delete(self):
        """Delete this collection.

        Example usage:

        .. code-block:: python

            reddit.subreddit("test").collections("some_uuid").mod.delete()

        .. seealso::

            :meth:`~.SubredditCollectionsModeration.create`

        """
        self._reddit.post(
            API_PATH["collection_delete"], data={"collection_id": self.collection_id}
        )

    def remove_post(self, submission: praw.models.Submission):
        """Remove a post from the collection.

        :param submission: The post to remove, a :class:`.Submission`, its permalink as
            a ``str``, its fullname as a ``str``, or its ID as a ``str``.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            collection.mod.remove_post("bgibu9")

        .. seealso::

            :meth:`.add_post`

        """
        link_fullname = self._post_fullname(submission)

        self._reddit.post(
            API_PATH["collection_remove_post"],
            data={"collection_id": self.collection_id, "link_fullname": link_fullname},
        )

    def reorder(self, links: list[str | praw.models.Submission]):
        r"""Reorder posts in the collection.

        :param links: A list of :class:`.Submission`\ s or a ``str`` that is either a
            fullname or an ID.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            current_order = collection.link_ids
            new_order = reversed(current_order)
            collection.mod.reorder(new_order)

        """
        link_ids = ",".join(self._post_fullname(post) for post in links)
        self._reddit.post(
            API_PATH["collection_reorder"],
            data={"collection_id": self.collection_id, "link_ids": link_ids},
        )

    def update_description(self, description: str):
        """Update the collection's description.

        :param description: The new description.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            collection.mod.update_description("Please enjoy these links!")

        .. seealso::

            :meth:`.update_title`

        """
        self._reddit.post(
            API_PATH["collection_desc"],
            data={"collection_id": self.collection_id, "description": description},
        )

    def update_display_layout(self, display_layout: str):
        """Update the collection's display layout.

        :param display_layout: Either ``"TIMELINE"`` for events or discussions or
            ``"GALLERY"`` for images or memes. Passing ``None`` will clear the set
            layout and ``collection.display_layout`` will be ``None``, however, the
            collection will appear on Reddit as if ``display_layout`` is set to
            ``"TIMELINE"``.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            collection.mod.update_display_layout("GALLERY")

        """
        self._reddit.post(
            API_PATH["collection_layout"],
            data={
                "collection_id": self.collection_id,
                "display_layout": display_layout,
            },
        )

    def update_title(self, title: str):
        """Update the collection's title.

        :param title: The new title.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            collection.mod.update_title("Titley McTitleface")

        .. seealso::

            :meth:`.update_description`

        """
        self._reddit.post(
            API_PATH["collection_title"],
            data={"collection_id": self.collection_id, "title": title},
        )


class SubredditCollectionsModeration(PRAWBase):
    r"""Class to represent moderator actions on a :class:`.Subreddit`'s :class:`.Collection`\ s.

    Obtain an instance via:

    .. code-block:: python

        reddit.subreddit("test").collections.mod

    """

    def __init__(
        self,
        reddit: praw.Reddit,
        sub_fullname: str,
        _data: dict[str, Any] | None = None,
    ):
        """Initialize a :class:`.SubredditCollectionsModeration` instance."""
        super().__init__(reddit, _data)
        self.subreddit_fullname = sub_fullname

    @_deprecate_args("title", "description", "display_layout")
    def create(
        self, *, description: str, display_layout: str | None = None, title: str
    ) -> Collection:
        """Create a new :class:`.Collection`.

        The authenticated account must have appropriate moderator permissions in the
        subreddit this collection belongs to.

        :param description: The description, up to 500 characters.
        :param display_layout: Either ``"TIMELINE"`` for events or discussions or
            ``"GALLERY"`` for images or memes. Passing ``""`` or ``None`` will make the
            collection appear on Reddit as if this is set to ``"TIMELINE"`` (default:
            ``None``).
        :param title: The title of the collection, up to 300 characters.

        :returns: The newly created :class:`.Collection`.

        Example usage:

        .. code-block:: python

            my_sub = reddit.subreddit("test")
            new_collection = my_sub.collections.mod.create(title="Title", description="desc")
            new_collection.mod.add_post("bgibu9")

        To specify the display layout as ``"GALLERY"`` when creating the collection:

        .. code-block:: python

            my_sub = reddit.subreddit("test")
            new_collection = my_sub.collections.mod.create(
                title="Title", description="desc", display_layout="GALLERY"
            )
            new_collection.mod.add_post("bgibu9")

        .. seealso::

            :meth:`~.CollectionModeration.delete`

        """
        data = {
            "sr_fullname": self.subreddit_fullname,
            "title": title,
            "description": description,
        }
        if display_layout:
            data["display_layout"] = display_layout
        return self._reddit.post(
            API_PATH["collection_create"],
            data=data,
        )


class SubredditCollections(PRAWBase):
    r"""Class to represent a :class:`.Subreddit`'s :class:`.Collection`\ s.

    Obtain an instance via:

    .. code-block:: python

        reddit.subreddit("test").collections

    """

    @cachedproperty
    def mod(self) -> SubredditCollectionsModeration:
        """Get an instance of :class:`.SubredditCollectionsModeration`.

        Provides :meth:`~SubredditCollectionsModeration.create`:

        .. code-block:: python

            my_sub = reddit.subreddit("test")
            new_collection = my_sub.collections.mod.create(title="Title", description="desc")

        """
        return SubredditCollectionsModeration(self._reddit, self.subreddit.fullname)

    def __call__(
        self,
        collection_id: str | None = None,
        permalink: str | None = None,
    ) -> Collection:
        """Return the :class:`.Collection` with the specified ID.

        :param collection_id: The ID of a :class:`.Collection` (default: ``None``).
        :param permalink: The permalink of a collection (default: ``None``).

        :returns: The specified :class:`.Collection`.

        Exactly one of ``collection_id`` or ``permalink`` is required.

        Example usage:

        .. code-block:: python

            subreddit = reddit.subreddit("test")

            uuid = "847e4548-a3b5-4ad7-afb4-edbfc2ed0a6b"
            collection = subreddit.collections(uuid)
            print(collection.title)
            print(collection.description)

            permalink = "https://www.reddit.com/r/SUBREDDIT/collection/" + uuid
            collection = subreddit.collections(permalink=permalink)
            print(collection.title)
            print(collection.description)

        """
        if (collection_id is None) == (permalink is None):
            msg = "Exactly one of 'collection_id' or 'permalink' must be provided."
            raise TypeError(msg)
        return Collection(
            self._reddit, collection_id=collection_id, permalink=permalink
        )

    def __init__(
        self,
        reddit: praw.Reddit,
        subreddit: praw.models.Subreddit,
        _data: dict[str, Any] | None = None,
    ):
        """Initialize a :class:`.SubredditCollections` instance."""
        super().__init__(reddit, _data)
        self.subreddit = subreddit

    def __iter__(self):
        r"""Iterate over the :class:`.Subreddit`'s :class:`.Collection`\ s.

        Example usage:

        .. code-block:: python

            for collection in reddit.subreddit("test").collections:
                print(collection.permalink)

        """
        request = self._reddit.get(
            API_PATH["collection_subreddit"],
            params={"sr_fullname": self.subreddit.fullname},
        )
        yield from request


class Collection(RedditBase):
    """Class to represent a :class:`.Collection`.

    Obtain an instance via:

    .. code-block:: python

        collection = reddit.subreddit("test").collections("some_uuid")

    or

    .. code-block:: python

        collection = reddit.subreddit("test").collections(
            permalink="https://reddit.com/r/SUBREDDIT/collection/some_uuid"
        )

    .. include:: ../../typical_attributes.rst

    =================== =============================================================
    Attribute           Description
    =================== =============================================================
    ``author``          The :class:`.Redditor` who created the collection.
    ``collection_id``   The UUID of the collection.
    ``created_at_utc``  Time the collection was created, represented in `Unix Time`_.
    ``description``     The collection description.
    ``display_layout``  The collection display layout.
    ``last_update_utc`` Time the collection was last updated, represented in `Unix
                        Time`_.
    ``link_ids``        A list of :class:`.Submission` fullnames.
    ``permalink``       The collection's permalink (to view on the web).
    ``sorted_links``    An iterable listing of the posts in this collection.
    ``title``           The title of the collection.
    =================== =============================================================

    .. _unix time: https://en.wikipedia.org/wiki/Unix_time

    """

    STR_FIELD = "collection_id"

    @cachedproperty
    def mod(self) -> CollectionModeration:
        """Get an instance of :class:`.CollectionModeration`.

        Provides access to various methods, including
        :meth:`~.CollectionModeration.add_post`, :meth:`~.CollectionModeration.delete`,
        :meth:`~.CollectionModeration.reorder`, and
        :meth:`~.CollectionModeration.update_title`.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            collection.mod.update_title("My new title!")

        """
        return CollectionModeration(self._reddit, self.collection_id)

    @cachedproperty
    def subreddit(self) -> praw.models.Subreddit:
        """Get the subreddit that this collection belongs to.

        For example:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            subreddit = collection.subreddit

        """
        return next(self._reddit.info(fullnames=[self.subreddit_id]))

    def __init__(
        self,
        reddit: praw.Reddit,
        _data: dict[str, Any] = None,
        collection_id: str | None = None,
        permalink: str | None = None,
    ):
        """Initialize a :class:`.Collection` instance.

        :param reddit: An instance of :class:`.Reddit`.
        :param _data: Any data associated with the :class:`.Collection`.
        :param collection_id: The ID of the :class:`.Collection`.
        :param permalink: The permalink of the :class:`.Collection`.

        """
        if (_data, collection_id, permalink).count(None) != 2:
            msg = "Exactly one of '_data', 'collection_id', or 'permalink' must be provided."
            raise TypeError(msg)

        if permalink:
            collection_id = self._url_parts(permalink)[4]

        if collection_id:
            self.collection_id = collection_id  # set from _data otherwise

        super().__init__(reddit, _data)

        self._info_params = {
            "collection_id": self.collection_id,
            "include_links": True,
        }

    def __iter__(self) -> Iterator:
        """Provide a way to iterate over the posts in this :class:`.Collection`.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            for submission in collection:
                print(submission.title, submission.permalink)

        """
        yield from self.sorted_links

    def __len__(self) -> int:
        """Get the number of posts in this :class:`.Collection`.

        Example usage:

        .. code-block:: python

            collection = reddit.subreddit("test").collections("some_uuid")
            print(len(collection))

        """
        return len(self.link_ids)

    def __setattr__(self, attribute: str, value: Any):
        """Objectify author, subreddit, and sorted_links attributes."""
        if attribute == "author_name":
            self.author = self._reddit.redditor(value)
        elif attribute == "sorted_links":
            value = self._reddit._objector.objectify(value)
        super().__setattr__(attribute, value)

    def _fetch(self):
        data = self._fetch_data()
        try:
            self._reddit._objector.check_error(data)
        except ClientException:
            # A well-formed but invalid Collections ID during fetch time
            # causes Reddit to return something that looks like an error
            # but with no content.
            msg = f"Error during fetch. Check collection ID {self.collection_id!r} is correct."
            raise ClientException(msg) from None

        other = type(self)(self._reddit, _data=data)
        self.__dict__.update(other.__dict__)
        super()._fetch()

    def _fetch_info(self):
        return "collection", {}, self._info_params

    def follow(self):
        """Follow this :class:`.Collection`.

        Example usage:

        .. code-block:: python

            reddit.subreddit("test").collections("some_uuid").follow()

        .. seealso::

            :meth:`.unfollow`

        """
        self._reddit.post(
            API_PATH["collection_follow"],
            data={"collection_id": self.collection_id, "follow": True},
        )

    def unfollow(self):
        """Unfollow this :class:`.Collection`.

        Example usage:

        .. code-block:: python

            reddit.subreddit("test").collections("some_uuid").unfollow()

        .. seealso::

            :meth:`.follow`

        """
        self._reddit.post(
            API_PATH["collection_follow"],
            data={"collection_id": self.collection_id, "follow": False},
        )


Subreddit._subreddit_collections_class = SubredditCollections
