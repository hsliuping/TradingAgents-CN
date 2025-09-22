"""Provide the Reddit class."""

from __future__ import annotations

import asyncio
import configparser
import os
import re
import time
from itertools import islice
from logging import getLogger
from typing import IO, TYPE_CHECKING, Any, Generator, Iterable
from urllib.parse import urlparse
from warnings import warn

from prawcore import (
    Authorizer,
    DeviceIDAuthorizer,
    ReadOnlyAuthorizer,
    Redirect,
    Requestor,
    ScriptAuthorizer,
    TrustedAuthenticator,
    UntrustedAuthenticator,
    session,
)
from prawcore.exceptions import BadRequest

from . import models
from .config import Config
from .const import API_PATH, USER_AGENT_FORMAT, __version__
from .exceptions import (
    ClientException,
    MissingRequiredAttributeException,
    RedditAPIException,
)
from .objector import Objector
from .util import _deprecate_args

try:
    from update_checker import update_check

    UPDATE_CHECKER_MISSING = False
except ImportError:  # pragma: no cover
    update_check = None
    UPDATE_CHECKER_MISSING = True

if TYPE_CHECKING:  # pragma: no cover
    import prawcore

    import praw.models

    from .util.token_manager import BaseTokenManager

Comment = models.Comment
Redditor = models.Redditor
Submission = models.Submission
Subreddit = models.Subreddit

logger = getLogger("praw")


class Reddit:
    """The Reddit class provides convenient access to Reddit's API.

    Instances of this class are the gateway to interacting with Reddit's API through
    PRAW. The canonical way to obtain an instance of this class is via:

    .. code-block:: python

        import praw

        reddit = praw.Reddit(
            client_id="CLIENT_ID",
            client_secret="CLIENT_SECRET",
            password="PASSWORD",
            user_agent="USERAGENT",
            username="USERNAME",
        )

    """

    update_checked = False
    _ratelimit_regex = re.compile(r"([0-9]{1,3}) (milliseconds?|seconds?|minutes?)")

    @property
    def _next_unique(self) -> int:
        value = self._unique_counter
        self._unique_counter += 1
        return value

    @property
    def read_only(self) -> bool:
        """Return ``True`` when using the ``ReadOnlyAuthorizer``."""
        return self._core == self._read_only_core

    @read_only.setter
    def read_only(self, value: bool):
        """Set or unset the use of the ReadOnlyAuthorizer.

        :raises: :class:`.ClientException` when attempting to unset ``read_only`` and
            only the ``ReadOnlyAuthorizer`` is available.

        """
        if value:
            self._core = self._read_only_core
        elif self._authorized_core is None:
            msg = (
                "read_only cannot be unset as only the ReadOnlyAuthorizer is available."
            )
            raise ClientException(msg)
        else:
            self._core = self._authorized_core

    @property
    def validate_on_submit(self) -> bool:
        """Get validate_on_submit.

        .. deprecated:: 7.0

            If property :attr:`.validate_on_submit` is set to ``False``, the behavior is
            deprecated by Reddit. This attribute will be removed around May-June 2020.

        """
        value = self._validate_on_submit
        if value is False:
            warn(
                "Reddit will check for validation on all posts around May-June 2020. It"
                " is recommended to check for validation by setting"
                " reddit.validate_on_submit to True.",
                category=DeprecationWarning,
                stacklevel=3,
            )
        return value

    @validate_on_submit.setter
    def validate_on_submit(self, val: bool):
        self._validate_on_submit = val

    def __enter__(self):  # noqa: ANN204
        """Handle the context manager open."""
        return self

    def __exit__(self, *_: object):
        """Handle the context manager close."""

    @_deprecate_args(
        "site_name",
        "config_interpolation",
        "requestor_class",
        "requestor_kwargs",
        "token_manager",
    )
    def __init__(
        self,
        site_name: str | None = None,
        *,
        config_interpolation: str | None = None,
        requestor_class: type[prawcore.requestor.Requestor] | None = None,
        requestor_kwargs: dict[str, Any] | None = None,
        token_manager: BaseTokenManager | None = None,
        **config_settings: str | bool | int | None,
    ):
        """Initialize a :class:`.Reddit` instance.

        :param site_name: The name of a section in your ``praw.ini`` file from which to
            load settings from. This parameter, in tandem with an appropriately
            configured ``praw.ini``, file is useful if you wish to easily save
            credentials for different applications, or communicate with other servers
            running Reddit. If ``site_name`` is ``None``, then the site name will be
            looked for in the environment variable ``praw_site``. If it is not found
            there, the ``DEFAULT`` site will be used (default: ``None``).
        :param config_interpolation: Config parser interpolation type that will be
            passed to :class:`.Config` (default: ``None``).
        :param requestor_class: A class that will be used to create a requestor. If not
            set, use ``prawcore.Requestor`` (default: ``None``).
        :param requestor_kwargs: Dictionary with additional keyword arguments used to
            initialize the requestor (default: ``None``).
        :param token_manager: When provided, the passed instance, a subclass of
            :class:`.BaseTokenManager`, will manage tokens via two callback functions.
            This parameter must be provided in order to work with refresh tokens
            (default: ``None``).

        Additional keyword arguments will be used to initialize the :class:`.Config`
        object. This can be used to specify configuration settings during instantiation
        of the :class:`.Reddit` instance. For more details, please see
        :ref:`configuration`.

        Required settings are:

        - ``client_id``
        - ``client_secret`` (for installed applications set this value to ``None``)
        - ``user_agent``

        The ``requestor_class`` and ``requestor_kwargs`` allow for customization of the
        requestor :class:`.Reddit` will use. This allows, e.g., easily adding behavior
        to the requestor or wrapping its |Session|_ in a caching layer. Example usage:

        .. |Session| replace:: ``Session``

        .. _session: https://2.python-requests.org/en/master/api/#requests.Session

        .. code-block:: python

            import json

            import betamax
            import requests
            from prawcore import Requestor

            from praw import Reddit


            class JSONDebugRequestor(Requestor):
                def request(self, *args, **kwargs):
                    response = super().request(*args, **kwargs)
                    print(json.dumps(response.json(), indent=4))
                    return response


            my_session = betamax.Betamax(requests.Session())
            reddit = Reddit(
                ..., requestor_class=JSONDebugRequestor, requestor_kwargs={"session": my_session}
            )

        """
        self._core = self._authorized_core = self._read_only_core = None
        self._objector = None
        self._token_manager = token_manager
        self._unique_counter = 0
        self._validate_on_submit = False

        try:
            config_section = (
                site_name or os.getenv("praw_site") or "DEFAULT"  # noqa: SIM112
            )
            self.config = Config(
                config_section, config_interpolation, **config_settings
            )
        except configparser.NoSectionError as exc:
            help_message = (
                "You provided the name of a praw.ini configuration which does not"
                " exist.\n\nFor help with creating a Reddit instance,"
                " visit\nhttps://praw.readthedocs.io/en/latest/code_overview/reddit_instance.html\n\nFor"
                " help on configuring PRAW,"
                " visit\nhttps://praw.readthedocs.io/en/latest/getting_started/configuration.html"
            )
            if site_name is not None:
                exc.message += f"\n{help_message}"
            raise

        required_message = (
            "Required configuration setting {!r} missing. \nThis setting can be"
            " provided in a praw.ini file, as a keyword argument to the Reddit class"
            " constructor, or as an environment variable."
        )
        for attribute in ("client_id", "user_agent"):
            if getattr(self.config, attribute) in (self.config.CONFIG_NOT_SET, None):
                raise MissingRequiredAttributeException(
                    required_message.format(attribute)
                )
        if self.config.client_secret is self.config.CONFIG_NOT_SET:
            msg = f"{required_message.format('client_secret')}\nFor installed applications this value must be set to None via a keyword argument to the Reddit class constructor."
            raise MissingRequiredAttributeException(msg)

        self._check_for_update()
        self._prepare_objector()
        self._prepare_prawcore(
            requestor_class=requestor_class, requestor_kwargs=requestor_kwargs
        )

        self.auth = models.Auth(self, None)
        """An instance of :class:`.Auth`.

        Provides the interface for interacting with installed and web applications.

        .. seealso::

            :ref:`auth_url`

        """

        self.drafts = models.DraftHelper(self, None)
        """An instance of :class:`.DraftHelper`.

        Provides the interface for working with :class:`.Draft` instances.

        For example, to list the currently authenticated user's drafts:

        .. code-block:: python

            drafts = reddit.drafts()

        To create a draft on r/test run:

        .. code-block:: python

            reddit.drafts.create(title="title", selftext="selftext", subreddit="test")

        """

        self.front = models.Front(self)
        """An instance of :class:`.Front`.

        Provides the interface for interacting with front page listings. For example:

        .. code-block:: python

            for submission in reddit.front.hot():
                print(submission)

        """

        self.inbox = models.Inbox(self, None)
        """An instance of :class:`.Inbox`.

        Provides the interface to a user's inbox which produces :class:`.Message`,
        :class:`.Comment`, and :class:`.Submission` instances. For example, to iterate
        through comments which mention the authorized user run:

        .. code-block:: python

            for comment in reddit.inbox.mentions():
                print(comment)

        """

        self.live = models.LiveHelper(self, None)
        """An instance of :class:`.LiveHelper`.

        Provides the interface for working with :class:`.LiveThread` instances. At
        present only new live threads can be created.

        .. code-block:: python

            reddit.live.create(title="title", description="description")

        """

        self.multireddit = models.MultiredditHelper(self, None)
        """An instance of :class:`.MultiredditHelper`.

        Provides the interface to working with :class:`.Multireddit` instances. For
        example, you can obtain a :class:`.Multireddit` instance via:

        .. code-block:: python

            reddit.multireddit(redditor="samuraisam", name="programming")

        """

        self.notes = models.RedditModNotes(self)
        r"""An instance of :class:`.RedditModNotes`.

        Provides the interface for working with :class:`.ModNote`\ s for multiple
        redditors across multiple subreddits.

        .. note::

            The authenticated user must be a moderator of the provided subreddit(s).

        For example, the latest note for u/spez in r/redditdev and r/test, and for
        u/bboe in r/redditdev can be iterated through like so:

        .. code-block:: python

            redditor = reddit.redditor("bboe")
            subreddit = reddit.subreddit("redditdev")

            pairs = [(subreddit, "spez"), ("test", "spez"), (subreddit, redditor)]

            for note in reddit.notes(pairs=pairs):
                print(f"{note.label}: {note.note}")

        """

        self.redditors = models.Redditors(self, None)
        """An instance of :class:`.Redditors`.

        Provides the interface for :class:`.Redditor` discovery. For example, to iterate
        over the newest Redditors, run:

        .. code-block:: python

            for redditor in reddit.redditors.new(limit=None):
                print(redditor)

        """

        self.subreddit = models.SubredditHelper(self, None)
        """An instance of :class:`.SubredditHelper`.

        Provides the interface to working with :class:`.Subreddit` instances. For
        example to create a :class:`.Subreddit` run:

        .. code-block:: python

            reddit.subreddit.create(name="coolnewsubname")

        To obtain a lazy :class:`.Subreddit` instance run:

        .. code-block:: python

            reddit.subreddit("test")

        Multiple subreddits can be combined and filtered views of r/all can also be used
        just like a subreddit:

        .. code-block:: python

            reddit.subreddit("redditdev+learnpython+botwatch")
            reddit.subreddit("all-redditdev-learnpython")

        """

        self.subreddits = models.Subreddits(self, None)
        """An instance of :class:`.Subreddits`.

        Provides the interface for :class:`.Subreddit` discovery. For example, to
        iterate over the set of default subreddits run:

        .. code-block:: python

            for subreddit in reddit.subreddits.default(limit=None):
                print(subreddit)

        """

        self.user = models.User(self)
        """An instance of :class:`.User`.

        Provides the interface to the currently authorized :class:`.Redditor`. For
        example to get the name of the current user run:

        .. code-block:: python

            print(reddit.user.me())

        """

    def _check_for_async(self):
        if self.config.check_for_async:  # pragma: no cover
            try:
                # noinspection PyUnresolvedReferences
                shell = get_ipython().__class__.__name__
                if shell == "ZMQInteractiveShell":
                    return
            except NameError:
                pass
            in_async = False
            try:
                asyncio.get_running_loop()
                in_async = True
            except Exception:  # noqa: BLE001,S110
                pass  # Quietly fail if any exception occurs during the check
            if in_async:
                logger.warning(
                    "It appears that you are using PRAW in an asynchronous"
                    " environment.\nIt is strongly recommended to use Async PRAW:"
                    " https://asyncpraw.readthedocs.io.\nSee"
                    " https://praw.readthedocs.io/en/latest/getting_started/multiple_instances.html#discord-bots-and-"
                    "asynchronous-environments"
                    " for more info.\n",
                )

    def _check_for_update(self):
        if UPDATE_CHECKER_MISSING:
            return
        if not Reddit.update_checked and self.config.check_for_updates:
            update_check(__package__, __version__)
            Reddit.update_checked = True

    def _handle_rate_limit(self, exception: RedditAPIException) -> int | float | None:
        for item in exception.items:
            if item.error_type == "RATELIMIT":
                amount_search = self._ratelimit_regex.search(item.message)
                if not amount_search:
                    break
                seconds = int(amount_search.group(1))
                if amount_search.group(2).startswith("minute"):
                    seconds *= 60
                elif amount_search.group(2).startswith("millisecond"):
                    seconds = 0
                if seconds <= int(self.config.ratelimit_seconds):
                    return seconds + 1
        return None

    def _objectify_request(
        self,
        *,
        data: dict[str, str | Any] | bytes | IO | str | None = None,
        files: dict[str, IO] | None = None,
        json: dict[Any, Any] | list[Any] | None = None,
        method: str = "",
        params: str | dict[str, str] | None = None,
        path: str = "",
    ) -> Any:
        """Run a request through the ``Objector``.

        :param data: Dictionary, bytes, or file-like object to send in the body of the
            request (default: ``None``).
        :param files: Dictionary, filename to file (like) object mapping (default:
            ``None``).
        :param json: JSON-serializable object to send in the body of the request with a
            Content-Type header of application/json (default: ``None``). If ``json`` is
            provided, ``data`` should not be.
        :param method: The HTTP method (e.g., ``"GET"``, ``"POST"``, ``"PUT"``,
            ``"DELETE"``).
        :param params: The query parameters to add to the request (default: ``None``).
        :param path: The path to fetch.

        """
        return self._objector.objectify(
            self.request(
                data=data,
                files=files,
                json=json,
                method=method,
                params=params,
                path=path,
            )
        )

    def _prepare_common_authorizer(
        self, authenticator: prawcore.auth.BaseAuthenticator
    ):
        if self._token_manager is not None:
            warn(
                "Token managers have been deprecated and will be removed in the near"
                " future. See https://www.reddit.com/r/redditdev/comments/olk5e6/"
                "followup_oauth2_api_changes_regarding_refresh/ for more details.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            if self.config.refresh_token:
                msg = "'refresh_token' setting cannot be provided when providing 'token_manager'"
                raise TypeError(msg)

            self._token_manager.reddit = self
            authorizer = Authorizer(
                authenticator,
                post_refresh_callback=self._token_manager.post_refresh_callback,
                pre_refresh_callback=self._token_manager.pre_refresh_callback,
            )
        elif self.config.refresh_token:
            authorizer = Authorizer(
                authenticator, refresh_token=self.config.refresh_token
            )
        else:
            self._core = self._read_only_core
            return
        self._core = self._authorized_core = session(
            authorizer=authorizer, window_size=self.config.window_size
        )

    def _prepare_objector(self):
        mappings = {
            self.config.kinds["comment"]: models.Comment,
            self.config.kinds["message"]: models.Message,
            self.config.kinds["redditor"]: models.Redditor,
            self.config.kinds["submission"]: models.Submission,
            self.config.kinds["subreddit"]: models.Subreddit,
            self.config.kinds["trophy"]: models.Trophy,
            "Button": models.Button,
            "Collection": models.Collection,
            "Draft": models.Draft,
            "DraftList": models.DraftList,
            "Image": models.Image,
            "LabeledMulti": models.Multireddit,
            "Listing": models.Listing,
            "LiveUpdate": models.LiveUpdate,
            "LiveUpdateEvent": models.LiveThread,
            "MenuLink": models.MenuLink,
            "ModeratedList": models.ModeratedList,
            "ModmailAction": models.ModmailAction,
            "ModmailConversation": models.ModmailConversation,
            "ModmailConversations-list": models.ModmailConversationsListing,
            "ModmailMessage": models.ModmailMessage,
            "Submenu": models.Submenu,
            "TrophyList": models.TrophyList,
            "UserList": models.RedditorList,
            "UserSubreddit": models.UserSubreddit,
            "button": models.ButtonWidget,
            "calendar": models.Calendar,
            "community-list": models.CommunityList,
            "custom": models.CustomWidget,
            "id-card": models.IDCard,
            "image": models.ImageWidget,
            "menu": models.Menu,
            "modaction": models.ModAction,
            "moderator-list": models.ModeratorListing,
            "moderators": models.ModeratorsWidget,
            "mod_note": models.ModNote,
            "more": models.MoreComments,
            "post-flair": models.PostFlairWidget,
            "rule": models.Rule,
            "stylesheet": models.Stylesheet,
            "subreddit-rules": models.RulesWidget,
            "textarea": models.TextArea,
            "widget": models.Widget,
        }
        self._objector = Objector(self, mappings)

    def _prepare_prawcore(
        self,
        *,
        requestor_class: type[prawcore.requestor.Requestor] = None,
        requestor_kwargs: Any | None = None,
    ):
        requestor_class = requestor_class or Requestor
        requestor_kwargs = requestor_kwargs or {}

        requestor = requestor_class(
            USER_AGENT_FORMAT.format(self.config.user_agent),
            self.config.oauth_url,
            self.config.reddit_url,
            **requestor_kwargs,
        )

        if self.config.client_secret:
            self._prepare_trusted_prawcore(requestor)
        else:
            self._prepare_untrusted_prawcore(requestor)

    def _prepare_trusted_prawcore(self, requestor: prawcore.requestor.Requestor):
        authenticator = TrustedAuthenticator(
            requestor,
            self.config.client_id,
            self.config.client_secret,
            self.config.redirect_uri,
        )
        read_only_authorizer = ReadOnlyAuthorizer(authenticator)
        self._read_only_core = session(
            authorizer=read_only_authorizer, window_size=self.config.window_size
        )

        if self.config.username and self.config.password:
            script_authorizer = ScriptAuthorizer(
                authenticator, self.config.username, self.config.password
            )
            self._core = self._authorized_core = session(
                authorizer=script_authorizer, window_size=self.config.window_size
            )
        else:
            self._prepare_common_authorizer(authenticator)

    def _prepare_untrusted_prawcore(self, requestor: prawcore.requestor.Requestor):
        authenticator = UntrustedAuthenticator(
            requestor, self.config.client_id, self.config.redirect_uri
        )
        read_only_authorizer = DeviceIDAuthorizer(authenticator)
        self._read_only_core = session(
            authorizer=read_only_authorizer, window_size=self.config.window_size
        )
        self._prepare_common_authorizer(authenticator)

    def _resolve_share_url(self, url: str) -> str:
        """Return the canonical URL for a given share URL."""
        parts = urlparse(url).path.rstrip("/").split("/")
        if "s" in parts:  # handling new share urls from mobile apps
            try:
                self.get(url)
            except Redirect as e:
                return e.response.next.url
        return url

    @_deprecate_args("id", "url")
    def comment(
        self, id: str | None = None, *, url: str | None = None
    ) -> models.Comment:
        """Return a lazy instance of :class:`.Comment`.

        :param id: The ID of the comment.
        :param url: A permalink pointing to the comment.

        .. note::

            If you want to obtain the comment's replies, you will need to call
            :meth:`~.Comment.refresh` on the returned :class:`.Comment`.

        """
        if url:
            url = self._resolve_share_url(url)
        return models.Comment(self, id=id, url=url)

    @_deprecate_args("path", "data", "json", "params")
    def delete(
        self,
        path: str,
        *,
        data: dict[str, str | Any] | bytes | IO | str | None = None,
        json: dict[Any, Any] | list[Any] | None = None,
        params: str | dict[str, str] | None = None,
    ) -> Any:
        """Return parsed objects returned from a DELETE request to ``path``.

        :param path: The path to fetch.
        :param data: Dictionary, bytes, or file-like object to send in the body of the
            request (default: ``None``).
        :param json: JSON-serializable object to send in the body of the request with a
            Content-Type header of application/json (default: ``None``). If ``json`` is
            provided, ``data`` should not be.
        :param params: The query parameters to add to the request (default: ``None``).

        """
        return self._objectify_request(
            data=data, json=json, method="DELETE", params=params, path=path
        )

    def domain(self, domain: str) -> models.DomainListing:
        """Return an instance of :class:`.DomainListing`.

        :param domain: The domain to obtain submission listings for.

        """
        return models.DomainListing(self, domain)

    @_deprecate_args("path", "params")
    def get(
        self,
        path: str,
        *,
        params: str | dict[str, str | int] | None = None,
    ) -> Any:
        """Return parsed objects returned from a GET request to ``path``.

        :param path: The path to fetch.
        :param params: The query parameters to add to the request (default: ``None``).

        """
        return self._objectify_request(method="GET", params=params, path=path)

    @_deprecate_args("fullnames", "url", "subreddits")
    def info(
        self,
        *,
        fullnames: Iterable[str] | None = None,
        subreddits: Iterable[praw.models.Subreddit | str] | None = None,
        url: str | None = None,
    ) -> Generator[
        praw.models.Subreddit | praw.models.Comment | praw.models.Submission,
        None,
        None,
    ]:
        """Fetch information about each item in ``fullnames``, ``url``, or ``subreddits``.

        :param fullnames: A list of fullnames for comments, submissions, and/or
            subreddits.
        :param subreddits: A list of subreddit names or :class:`.Subreddit` objects to
            retrieve subreddits from.
        :param url: A url (as a string) to retrieve lists of link submissions from.

        :returns: A generator that yields found items in their relative order.

        Items that cannot be matched will not be generated. Requests will be issued in
        batches for each 100 fullnames.

        .. note::

            For comments that are retrieved via this method, if you want to obtain its
            replies, you will need to call :meth:`~.Comment.refresh` on the yielded
            :class:`.Comment`.

        .. note::

            When using the URL option, it is important to be aware that URLs are treated
            literally by Reddit's API. As such, the URLs ``"youtube.com"`` and
            ``"https://www.youtube.com"`` will provide a different set of submissions.

        """
        none_count = (fullnames, url, subreddits).count(None)
        if none_count != 2:
            msg = "Either 'fullnames', 'url', or 'subreddits' must be provided."
            raise TypeError(msg)

        is_using_fullnames = fullnames is not None
        ids_or_names = fullnames if is_using_fullnames else subreddits

        if ids_or_names is not None:
            if isinstance(ids_or_names, str):
                msg = "'fullnames' and 'subreddits' must be a non-str iterable."
                raise TypeError(msg)

            api_parameter_name = "id" if is_using_fullnames else "sr_name"

            def generator(names: Iterable[str | praw.models.Subreddit]):
                if is_using_fullnames:
                    iterable = iter(names)
                else:
                    iterable = iter([str(item) for item in names])
                while True:
                    chunk = list(islice(iterable, 100))
                    if not chunk:
                        break
                    params = {api_parameter_name: ",".join(chunk)}
                    yield from self.get(API_PATH["info"], params=params)

            return generator(ids_or_names)

        def generator(_url: str):
            params = {"url": _url}
            yield from self.get(API_PATH["info"], params=params)

        return generator(url)

    @_deprecate_args("path", "data", "json")
    def patch(
        self,
        path: str,
        *,
        data: dict[str, str | Any] | bytes | IO | str | None = None,
        json: dict[Any, Any] | list[Any] | None = None,
        params: str | dict[str, str] | None = None,
    ) -> Any:
        """Return parsed objects returned from a PATCH request to ``path``.

        :param path: The path to fetch.
        :param data: Dictionary, bytes, or file-like object to send in the body of the
            request (default: ``None``).
        :param json: JSON-serializable object to send in the body of the request with a
            Content-Type header of application/json (default: ``None``). If ``json`` is
            provided, ``data`` should not be.
        :param params: The query parameters to add to the request (default: ``None``).

        """
        return self._objectify_request(
            data=data, json=json, method="PATCH", params=params, path=path
        )

    @_deprecate_args("path", "data", "files", "params", "json")
    def post(
        self,
        path: str,
        *,
        data: dict[str, str | Any] | bytes | IO | str | None = None,
        files: dict[str, IO] | None = None,
        json: dict[Any, Any] | list[Any] | None = None,
        params: str | dict[str, str] | None = None,
    ) -> Any:
        """Return parsed objects returned from a POST request to ``path``.

        :param path: The path to fetch.
        :param data: Dictionary, bytes, or file-like object to send in the body of the
            request (default: ``None``).
        :param files: Dictionary, filename to file (like) object mapping (default:
            ``None``).
        :param json: JSON-serializable object to send in the body of the request with a
            Content-Type header of application/json (default: ``None``). If ``json`` is
            provided, ``data`` should not be.
        :param params: The query parameters to add to the request (default: ``None``).

        """
        if json is None:
            data = data or {}

        attempts = 3
        last_exception = None
        while attempts > 0:
            attempts -= 1
            try:
                return self._objectify_request(
                    data=data,
                    files=files,
                    json=json,
                    method="POST",
                    params=params,
                    path=path,
                )
            except RedditAPIException as exception:
                last_exception = exception
                seconds = self._handle_rate_limit(exception=exception)
                if seconds is None:
                    break
                second_string = "second" if seconds == 1 else "seconds"
                logger.debug(
                    "Rate limit hit, sleeping for %d %s", seconds, second_string
                )
                time.sleep(seconds)
        raise last_exception

    @_deprecate_args("path", "data", "json")
    def put(
        self,
        path: str,
        *,
        data: dict[str, str | Any] | bytes | IO | str | None = None,
        json: dict[Any, Any] | list[Any] | None = None,
    ) -> Any:
        """Return parsed objects returned from a PUT request to ``path``.

        :param path: The path to fetch.
        :param data: Dictionary, bytes, or file-like object to send in the body of the
            request (default: ``None``).
        :param json: JSON-serializable object to send in the body of the request with a
            Content-Type header of application/json (default: ``None``). If ``json`` is
            provided, ``data`` should not be.

        """
        return self._objectify_request(data=data, json=json, method="PUT", path=path)

    @_deprecate_args("nsfw")
    def random_subreddit(self, *, nsfw: bool = False) -> praw.models.Subreddit:
        """Return a random lazy instance of :class:`.Subreddit`.

        :param nsfw: Return a random NSFW (not safe for work) subreddit (default:
            ``False``).

        """
        url = API_PATH["subreddit"].format(subreddit="randnsfw" if nsfw else "random")
        path = None
        try:
            self.get(url, params={"unique": self._next_unique})
        except Redirect as redirect:
            path = redirect.path
        return models.Subreddit(self, path.split("/")[2])

    @_deprecate_args("name", "fullname")
    def redditor(
        self, name: str | None = None, *, fullname: str | None = None
    ) -> praw.models.Redditor:
        """Return a lazy instance of :class:`.Redditor`.

        :param name: The name of the redditor.
        :param fullname: The fullname of the redditor, starting with ``t2_``.

        Either ``name`` or ``fullname`` can be provided, but not both.

        """
        return models.Redditor(self, name=name, fullname=fullname)

    @_deprecate_args("method", "path", "params", "data", "files", "json")
    def request(
        self,
        *,
        data: dict[str, str | Any] | bytes | IO | str | None = None,
        files: dict[str, IO] | None = None,
        json: dict[Any, Any] | list[Any] | None = None,
        method: str,
        params: str | dict[str, str | int] | None = None,
        path: str,
    ) -> Any:
        """Return the parsed JSON data returned from a request to URL.

        :param data: Dictionary, bytes, or file-like object to send in the body of the
            request (default: ``None``).
        :param files: Dictionary, filename to file (like) object mapping (default:
            ``None``).
        :param json: JSON-serializable object to send in the body of the request with a
            Content-Type header of application/json (default: ``None``). If ``json`` is
            provided, ``data`` should not be.
        :param method: The HTTP method (e.g., ``"GET"``, ``"POST"``, ``"PUT"``,
            ``"DELETE"``).
        :param params: The query parameters to add to the request (default: ``None``).
        :param path: The path to fetch.

        """
        if self.config.check_for_async:
            self._check_for_async()
        if data and json:
            msg = "At most one of 'data' or 'json' is supported."
            raise ClientException(msg)
        try:
            return self._core.request(
                data=data,
                files=files,
                json=json,
                method=method,
                params=params,
                path=path,
            )
        except BadRequest as exception:
            try:
                data = exception.response.json()
            except ValueError:
                if exception.response.text:
                    data = {"reason": exception.response.text}
                else:
                    raise exception from None
            if set(data) == {"error", "message"}:
                raise
            explanation = data.get("explanation")
            if "fields" in data:
                assert len(data["fields"]) == 1
                field = data["fields"][0]
            else:
                field = None
            raise RedditAPIException(
                [data["reason"], explanation, field]
            ) from exception

    @_deprecate_args("id", "url")
    def submission(
        self, id: str | None = None, *, url: str | None = None
    ) -> praw.models.Submission:
        """Return a lazy instance of :class:`.Submission`.

        :param id: A Reddit base36 submission ID, e.g., ``"2gmzqe"``.
        :param url: A URL supported by :meth:`.Submission.id_from_url`.

        Either ``id`` or ``url`` can be provided, but not both.

        """
        if url:
            url = self._resolve_share_url(url)
        return models.Submission(self, id=id, url=url)

    def username_available(self, name: str) -> bool:
        """Check to see if the username is available.

        For example, to check if the username ``bboe`` is available, try:

        .. code-block:: python

            reddit.username_available("bboe")

        """
        return self._objectify_request(
            method="GET", params={"user": name}, path=API_PATH["username_available"]
        )
