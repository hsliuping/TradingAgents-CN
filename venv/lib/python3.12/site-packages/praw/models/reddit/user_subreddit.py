"""Provide the :class:`.UserSubreddit` class."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable
from warnings import warn

from ...util.cache import cachedproperty
from .subreddit import Subreddit, SubredditModeration

if TYPE_CHECKING:  # pragma: no cover
    import praw.models


class UserSubreddit(Subreddit):
    """A class for :class:`.User` Subreddits.

    To obtain an instance of this class execute:

    .. code-block:: python

        subreddit = reddit.user.me().subreddit

    .. include:: ../../typical_attributes.rst

    ========================= ==========================================================
    Attribute                 Description
    ========================= ==========================================================
    ``can_assign_link_flair`` Whether users can assign their own link flair.
    ``can_assign_user_flair`` Whether users can assign their own user flair.
    ``created_utc``           Time the subreddit was created, represented in `Unix
                              Time`_.
    ``description``           Subreddit description, in Markdown.
    ``description_html``      Subreddit description, in HTML.
    ``display_name``          Name of the subreddit.
    ``id``                    ID of the subreddit.
    ``name``                  Fullname of the subreddit.
    ``over18``                Whether the subreddit is NSFW.
    ``public_description``    Description of the subreddit, shown in searches and on the
                              "You must be invited to visit this community" page (if
                              applicable).
    ``spoilers_enabled``      Whether the spoiler tag feature is enabled.
    ``subscribers``           Count of subscribers. This will be ``0`` unless unless the
                              authenticated user is a moderator.
    ``user_is_banned``        Whether the authenticated user is banned.
    ``user_is_moderator``     Whether the authenticated user is a moderator.
    ``user_is_subscriber``    Whether the authenticated user is subscribed.
    ========================= ==========================================================

    .. _unix time: https://en.wikipedia.org/wiki/Unix_time

    """

    @staticmethod
    def _dict_deprecated_wrapper(func: Callable) -> Callable:
        """Show deprecation notice for dict only methods."""

        def wrapper(*args: Any, **kwargs: Any):
            warn(
                "'Redditor.subreddit' is no longer a dict and is now an UserSubreddit"
                f" object. Using '{func.__name__}' is deprecated and will be removed in"
                " PRAW 8.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapper

    @cachedproperty
    def mod(self) -> praw.models.reddit.user_subreddit.UserSubredditModeration:
        """Provide an instance of :class:`.UserSubredditModeration`.

        For example, to update the authenticated user's display name:

        .. code-block:: python

            reddit.user.me().subreddit.mod.update(title="New display name")

        """
        return UserSubredditModeration(self)

    def __getitem__(self, item: str) -> Any:
        """Show deprecation notice for dict method ``__getitem__``."""
        warn(
            "'Redditor.subreddit' is no longer a dict and is now an UserSubreddit"
            " object. Accessing attributes using string indices is deprecated.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return getattr(self, item)

    def __init__(self, reddit: praw.Reddit, *args: Any, **kwargs: Any):
        """Initialize an :class:`.UserSubreddit` instance.

        :param reddit: An instance of :class:`.Reddit`.

        .. note::

            This class should not be initialized directly. Instead, obtain an instance
            via: ``reddit.user.me().subreddit`` or
            ``reddit.redditor("redditor_name").subreddit``.

        """

        def predicate(item: str):
            name = getattr(item, "__name__", None)
            return name not in dir(object) + dir(Subreddit) and name in dir(dict)

        for name, _member in inspect.getmembers(dict, predicate=predicate):
            if name != "__getitem__":
                setattr(
                    self,
                    name,
                    self._dict_deprecated_wrapper(getattr(self.__dict__, name)),
                )

        super().__init__(reddit, *args, **kwargs)


# noinspection PyIncorrectDocstring
class UserSubredditModeration(SubredditModeration):
    """Provides a set of moderation functions to a :class:`.UserSubreddit`.

    For example, to accept a moderation invite from the user subreddit of u/spez:

    .. code-block:: python

        reddit.subreddit("test").mod.accept_invite()

    """

    def update(self, **settings: str | int | bool) -> dict[str, str | int | bool]:
        """Update the :class:`.Subreddit`'s settings.

        :param all_original_content: Mandate all submissions to be original content
            only.
        :param allow_chat_post_creation: Allow users to create chat submissions.
        :param allow_images: Allow users to upload images using the native image
            hosting.
        :param allow_polls: Allow users to post polls to the subreddit.
        :param allow_post_crossposts: Allow users to crosspost submissions from other
            subreddits.
        :param allow_top: Allow the subreddit to appear on r/all as well as the default
            and trending lists.
        :param allow_videos: Allow users to upload videos using the native image
            hosting.
        :param collapse_deleted_comments: Collapse deleted and removed comments on
            comments pages by default.
        :param crowd_control_chat_level: Controls the crowd control level for chat
            rooms. Goes from 0-3.
        :param crowd_control_level: Controls the crowd control level for submissions.
            Goes from 0-3.
        :param crowd_control_mode: Enables/disables crowd control.
        :param comment_score_hide_mins: The number of minutes to hide comment scores.
        :param description: Shown in the sidebar of your subreddit.
        :param disable_contributor_requests: Specifies whether redditors may send
            automated modmail messages requesting approval as a submitter.
        :param exclude_banned_modqueue: Exclude posts by site-wide banned users from
            modqueue/unmoderated.
        :param free_form_reports: Allow users to specify custom reasons in the report
            menu.
        :param header_hover_text: The text seen when hovering over the snoo.
        :param hide_ads: Don't show ads within this subreddit. Only applies to
            Premium-user only subreddits.
        :param key_color: A 6-digit rgb hex color (e.g., ``"#AABBCC"``), used as a
            thematic color for your subreddit on mobile.
        :param lang: A valid IETF language tag (underscore separated).
        :param link_type: The types of submissions users can make. One of ``"any"``,
            ``"link"``, or ``"self"``.
        :param original_content_tag_enabled: Enables the use of the ``original content``
            label for submissions.
        :param over_18: Viewers must be over 18 years old (i.e., NSFW).
        :param public_description: Public description blurb. Appears in search results
            and on the landing page for private subreddits.
        :param public_traffic: Make the traffic stats page public.
        :param restrict_commenting: Specifies whether approved users have the ability to
            comment.
        :param restrict_posting: Specifies whether approved users have the ability to
            submit posts.
        :param show_media: Show thumbnails on submissions.
        :param show_media_preview: Expand media previews on comments pages.
        :param spam_comments: Spam filter strength for comments. One of ``"all"``,
            ``"low"``, or ``"high"``.
        :param spam_links: Spam filter strength for links. One of ``"all"``, ``"low"``,
            or ``"high"``.
        :param spam_selfposts: Spam filter strength for selfposts. One of ``"all"``,
            ``"low"``, or ``"high"``.
        :param spoilers_enabled: Enable marking posts as containing spoilers.
        :param submit_link_label: Custom label for submit link button (None for
            default).
        :param submit_text: Text to show on submission page.
        :param submit_text_label: Custom label for submit text post button (None for
            default).
        :param subreddit_type: The string ``"user"``.
        :param suggested_comment_sort: All comment threads will use this sorting method
            by default. Leave ``None``, or choose one of ``confidence``,
            ``"controversial"``, ``"live"``, ``"new"``, ``"old"``, ``"qa"``,
            ``"random"``, or ``"top"``.
        :param title: The title of the subreddit.
        :param welcome_message_enabled: Enables the subreddit welcome message.
        :param welcome_message_text: The text to be used as a welcome message. A welcome
            message is sent to all new subscribers by a Reddit bot.
        :param wiki_edit_age: Account age, in days, required to edit and create wiki
            pages.
        :param wiki_edit_karma: Subreddit karma required to edit and create wiki pages.
        :param wikimode: One of ``"anyone"``, ``"disabled"``, or ``"modonly"``.

        Additional keyword arguments can be provided to handle new settings as Reddit
        introduces them.

        Settings that are documented here and aren't explicitly set by you in a call to
        :meth:`.SubredditModeration.update` should retain their current value. If they
        do not please file a bug.

        .. warning::

            Undocumented settings, or settings that were very recently documented, may
            not retain their current value when updating. This often occurs when Reddit
            adds a new setting but forgets to add that setting to the API endpoint that
            is used to fetch the current settings.

        """
        current_settings = self.settings()

        # These attributes come out using different names than they go in.
        remap = {
            "allow_top": "default_set",
            "header_title": "header_hover_text",
            "lang": "language",
            "link_type": "content_options",
            "sr": "subreddit_id",
            "type": "subreddit_type",
        }
        for new, old in remap.items():
            current_settings[new] = current_settings.pop(old)

        current_settings.update(settings)
        return UserSubreddit._create_or_update(
            _reddit=self.subreddit._reddit, **current_settings
        )
