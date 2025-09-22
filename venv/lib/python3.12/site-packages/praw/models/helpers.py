"""Provide the helper classes."""

from __future__ import annotations

from json import dumps
from typing import TYPE_CHECKING, Any, Generator

from ..const import API_PATH
from ..util import _deprecate_args
from .base import PRAWBase
from .reddit.draft import Draft
from .reddit.live import LiveThread
from .reddit.multi import Multireddit, Subreddit

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class DraftHelper(PRAWBase):
    r"""Provide a set of functions to interact with :class:`.Draft` instances.

    .. note::

        The methods provided by this class will only work on the currently authenticated
        user's :class:`.Draft`\ s.

    """

    def __call__(
        self, draft_id: str | None = None
    ) -> list[praw.models.Draft] | praw.models.Draft:
        """Return a list of :class:`.Draft` instances.

        :param draft_id: When provided, this returns a :class:`.Draft` instance
            (default: ``None``).

        :returns: A :class:`.Draft` instance if ``draft_id`` is provided. Otherwise, a
            list of :class:`.Draft` objects.

        .. note::

            Drafts fetched using a specific draft ID are lazily loaded, so you might
            have to access an attribute to get all the expected attributes.

        This method can be used to fetch a specific draft by ID, like so:

        .. code-block:: python

            draft_id = "124862bc-e1e9-11eb-aa4f-e68667a77cbb"
            draft = reddit.drafts(draft_id)
            print(draft)

        """
        if draft_id is not None:
            return Draft(self._reddit, id=draft_id)
        return self._draft_list()

    def _draft_list(self) -> list[praw.models.Draft]:
        """Get a list of :class:`.Draft` instances.

        :returns: A list of :class:`.Draft` instances.

        """
        return self._reddit.get(API_PATH["drafts"], params={"md_body": True})

    def create(
        self,
        *,
        flair_id: str | None = None,
        flair_text: str | None = None,
        is_public_link: bool = False,
        nsfw: bool = False,
        original_content: bool = False,
        selftext: str | None = None,
        send_replies: bool = True,
        spoiler: bool = False,
        subreddit: (
            str | praw.models.Subreddit | praw.models.UserSubreddit | None
        ) = None,
        title: str | None = None,
        url: str | None = None,
        **draft_kwargs: Any,
    ) -> praw.models.Draft:
        """Create a new :class:`.Draft`.

        :param flair_id: The flair template to select (default: ``None``).
        :param flair_text: If the template's ``flair_text_editable`` value is ``True``,
            this value will set a custom text (default: ``None``). ``flair_id`` is
            required when ``flair_text`` is provided.
        :param is_public_link: Whether to enable public viewing of the draft before it
            is submitted (default: ``False``).
        :param nsfw: Whether the draft should be marked NSFW (default: ``False``).
        :param original_content: Whether the submission should be marked as original
            content (default: ``False``).
        :param selftext: The Markdown formatted content for a text submission draft. Use
            ``None`` to make a title-only submission draft (default: ``None``).
            ``selftext`` can not be provided if ``url`` is provided.
        :param send_replies: When ``True``, messages will be sent to the submission
            author when comments are made to the submission (default: ``True``).
        :param spoiler: Whether the submission should be marked as a spoiler (default:
            ``False``).
        :param subreddit: The subreddit to create the draft for. This accepts a
            subreddit display name, :class:`.Subreddit` object, or
            :class:`.UserSubreddit` object. If ``None``, the :class:`.UserSubreddit` of
            currently authenticated user will be used (default: ``None``).
        :param title: The title of the draft (default: ``None``).
        :param url: The URL for a ``link`` submission draft (default: ``None``). ``url``
            can not be provided if ``selftext`` is provided.

        Additional keyword arguments can be provided to handle new parameters as Reddit
        introduces them.

        :returns: The new :class:`.Draft` object.

        """
        if selftext and url:
            msg = "Exactly one of 'selftext' or 'url' must be provided."
            raise TypeError(msg)
        if isinstance(subreddit, str):
            subreddit = self._reddit.subreddit(subreddit)

        data = Draft._prepare_data(
            flair_id=flair_id,
            flair_text=flair_text,
            is_public_link=is_public_link,
            nsfw=nsfw,
            original_content=original_content,
            selftext=selftext,
            send_replies=send_replies,
            spoiler=spoiler,
            subreddit=subreddit,
            title=title,
            url=url,
            **draft_kwargs,
        )
        return self._reddit.post(API_PATH["draft"], data=data)


class LiveHelper(PRAWBase):
    r"""Provide a set of functions to interact with :class:`.LiveThread`\ s."""

    def __call__(self, id: str) -> praw.models.LiveThread:
        """Return a new lazy instance of :class:`.LiveThread`.

        This method is intended to be used as:

        .. code-block:: python

            livethread = reddit.live("ukaeu1ik4sw5")

        :param id: A live thread ID, e.g., ``ukaeu1ik4sw5``.

        """
        return LiveThread(self._reddit, id=id)

    @_deprecate_args("title", "description", "nsfw", "resources")
    def create(
        self,
        title: str,
        *,
        description: str | None = None,
        nsfw: bool = False,
        resources: str = None,
    ) -> praw.models.LiveThread:
        """Create a new :class:`.LiveThread`.

        :param title: The title of the new :class:`.LiveThread`.
        :param description: The new :class:`.LiveThread`'s description.
        :param nsfw: Indicate whether this thread is not safe for work (default:
            ``False``).
        :param resources: Markdown formatted information that is useful for the
            :class:`.LiveThread`.

        :returns: The new :class:`.LiveThread` object.

        """
        return self._reddit.post(
            API_PATH["livecreate"],
            data={
                "description": description,
                "nsfw": nsfw,
                "resources": resources,
                "title": title,
            },
        )

    def info(self, ids: list[str]) -> Generator[praw.models.LiveThread, None, None]:
        """Fetch information about each live thread in ``ids``.

        :param ids: A list of IDs for a live thread.

        :returns: A generator that yields :class:`.LiveThread` instances.

        :raises: ``prawcore.ServerError`` if invalid live threads are requested.

        Requests will be issued in batches for each 100 IDs.

        .. note::

            This method doesn't support IDs for live updates.

        .. warning::

            Unlike :meth:`.Reddit.info`, the output of this method may not reflect the
            order of input.

        Usage:

        .. code-block:: python

            ids = ["3rgnbke2rai6hen7ciytwcxadi", "sw7bubeycai6hey4ciytwamw3a", "t8jnufucss07"]
            for thread in reddit.live.info(ids):
                print(thread.title)

        """
        if not isinstance(ids, list):
            msg = "ids must be a list"
            raise TypeError(msg)

        def generator():
            for position in range(0, len(ids), 100):
                ids_chunk = ids[position : position + 100]
                url = API_PATH["live_info"].format(ids=",".join(ids_chunk))
                params = {"limit": 100}  # 25 is used if not specified
                yield from self._reddit.get(url, params=params)

        return generator()

    def now(self) -> praw.models.LiveThread | None:
        """Get the currently featured live thread.

        :returns: The :class:`.LiveThread` object, or ``None`` if there is no currently
            featured live thread.

        Usage:

        .. code-block:: python

            thread = reddit.live.now()  # LiveThread object or None

        """
        return self._reddit.get(API_PATH["live_now"])


class MultiredditHelper(PRAWBase):
    """Provide a set of functions to interact with multireddits."""

    @_deprecate_args("redditor", "name")
    def __call__(
        self, *, name: str, redditor: str | praw.models.Redditor
    ) -> praw.models.Multireddit:
        """Return a lazy instance of :class:`.Multireddit`.

        :param name: The name of the multireddit.
        :param redditor: A redditor name or :class:`.Redditor` instance who owns the
            multireddit.

        """
        path = f"/user/{redditor}/m/{name}"
        return Multireddit(self._reddit, _data={"name": name, "path": path})

    @_deprecate_args(
        "display_name",
        "subreddits",
        "description_md",
        "icon_name",
        "key_color",
        "visibility",
        "weighting_scheme",
    )
    def create(
        self,
        *,
        description_md: str | None = None,
        display_name: str,
        icon_name: str | None = None,
        key_color: str | None = None,
        subreddits: str | praw.models.Subreddit,
        visibility: str = "private",
        weighting_scheme: str = "classic",
    ) -> praw.models.Multireddit:
        """Create a new :class:`.Multireddit`.

        :param display_name: The display name for the new multireddit.
        :param subreddits: Subreddits to add to the new multireddit. Can be a list of
            either :class:`.Subreddit` instances or subreddit display names.
        :param description_md: Description for the new multireddit, formatted in
            markdown.
        :param icon_name: Can be one of: ``"art and design"``, ``"ask"``, ``"books"``,
            ``"business"``, ``"cars"``, ``"comics"``, ``"cute animals"``, ``"diy"``,
            ``"entertainment"``, ``"food and drink"``, ``"funny"``, ``"games"``,
            ``"grooming"``, ``"health"``, ``"life advice"``, ``"military"``, ``"models
            pinup"``, ``"music"``, ``"news"``, ``"philosophy"``, ``"pictures and
            gifs"``, ``"science"``, ``"shopping"``, ``"sports"``, ``"style"``,
            ``"tech"``, ``"travel"``, ``"unusual stories"``, ``"video"``, or ``None``.
        :param key_color: RGB hex color code of the form ``"#FFFFFF"``.
        :param visibility: Can be one of: ``"hidden"``, ``"private"``, or ``"public"``
            (default: ``"private"``).
        :param weighting_scheme: Can be one of: ``"classic"`` or ``"fresh"`` (default:
            ``"classic"``).

        :returns: The new :class:`.Multireddit` object.

        """
        model = {
            "description_md": description_md,
            "display_name": display_name,
            "icon_name": icon_name,
            "key_color": key_color,
            "subreddits": [{"name": str(sub)} for sub in subreddits],
            "visibility": visibility,
            "weighting_scheme": weighting_scheme,
        }
        return self._reddit.post(
            API_PATH["multireddit_base"], data={"model": dumps(model)}
        )


class SubredditHelper(PRAWBase):
    """Provide a set of functions to interact with Subreddits."""

    def __call__(self, display_name: str) -> praw.models.Subreddit:
        """Return a lazy instance of :class:`.Subreddit`.

        :param display_name: The name of the subreddit.

        """
        lower_name = display_name.lower()

        if lower_name == "random":
            return self._reddit.random_subreddit()
        if lower_name == "randnsfw":
            return self._reddit.random_subreddit(nsfw=True)

        return Subreddit(self._reddit, display_name=display_name)

    @_deprecate_args("name", "title", "link_type", "subreddit_type", "wikimode")
    def create(
        self,
        name: str,
        *,
        link_type: str = "any",
        subreddit_type: str = "public",
        title: str | None = None,
        wikimode: str = "disabled",
        **other_settings: str | None,
    ) -> praw.models.Subreddit:
        """Create a new :class:`.Subreddit`.

        :param name: The name for the new subreddit.
        :param link_type: The types of submissions users can make. One of ``"any"``,
            ``"link"``, or ``"self"`` (default: ``"any"``).
        :param subreddit_type: One of ``"archived"``, ``"employees_only"``,
            ``"gold_only"``, ``"gold_restricted"``, ``"private"``, ``"public"``, or
            ``"restricted"`` (default: ``"public"``).
        :param title: The title of the subreddit. When ``None`` or ``""`` use the value
            of ``name``.
        :param wikimode: One of ``"anyone"``, ``"disabled"``, or ``"modonly"`` (default:
            ``"disabled"``).

        Any keyword parameters not provided, or set explicitly to ``None``, will take on
        a default value assigned by the Reddit server.

        .. seealso::

            :meth:`~.SubredditModeration.update` for documentation of other available
            settings.

        """
        Subreddit._create_or_update(
            _reddit=self._reddit,
            link_type=link_type,
            name=name,
            subreddit_type=subreddit_type,
            title=title or name,
            wikimode=wikimode,
            **other_settings,
        )
        return self(name)
