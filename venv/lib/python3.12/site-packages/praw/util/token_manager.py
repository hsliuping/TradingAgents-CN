"""Token Manager classes.

There should be a 1-to-1 mapping between an instance of a subclass of
:class:`.BaseTokenManager` and a :class:`.Reddit` instance.

A few proof of concept token manager classes are provided here, but it is expected that
PRAW users will create their own token manager classes suitable for their needs.

.. deprecated:: 7.4.0

    Tokens managers have been deprecated and will be removed in the near future.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from . import _deprecate_args

if TYPE_CHECKING:  # pragma: no cover
    import prawcore

    import praw


class BaseTokenManager(ABC):
    """An abstract class for all token managers."""

    @abstractmethod
    def post_refresh_callback(self, authorizer: prawcore.auth.BaseAuthorizer):
        """Handle callback that is invoked after a refresh token is used.

        :param authorizer: The ``prawcore.Authorizer`` instance used containing
            ``access_token`` and ``refresh_token`` attributes.

        This function will be called after refreshing the access and refresh tokens.
        This callback can be used for saving the updated ``refresh_token``.

        """

    @abstractmethod
    def pre_refresh_callback(self, authorizer: prawcore.auth.BaseAuthorizer):
        """Handle callback that is invoked before refreshing PRAW's authorization.

        :param authorizer: The ``prawcore.Authorizer`` instance used containing
            ``access_token`` and ``refresh_token`` attributes.

        This callback can be used to inspect and modify the attributes of the
        ``prawcore.Authorizer`` instance, such as setting the ``refresh_token``.

        """

    @property
    def reddit(self) -> praw.Reddit:
        """Return the :class:`.Reddit` instance bound to the token manager."""
        return self._reddit

    @reddit.setter
    def reddit(self, value: praw.Reddit):
        if self._reddit is not None:
            msg = "'reddit' can only be set once and is done automatically"
            raise RuntimeError(msg)
        self._reddit = value

    def __init__(self):
        """Initialize a :class:`.BaseTokenManager` instance."""
        self._reddit = None


class FileTokenManager(BaseTokenManager):
    """Provides a single-file based token manager.

    It is expected that the file with the initial ``refresh_token`` is created prior to
    use.

    .. warning::

        The same ``file`` should not be used by more than one instance of this class
        concurrently. Doing so may result in data corruption. Consider using
        :class:`.SQLiteTokenManager` if you want more than one instance of PRAW to
        concurrently manage a specific ``refresh_token`` chain.

    """

    def __init__(self, filename: str):
        """Initialize a :class:`.FileTokenManager` instance.

        :param filename: The file the contains the refresh token.

        """
        super().__init__()
        self._filename = filename

    def post_refresh_callback(self, authorizer: prawcore.auth.BaseAuthorizer):
        """Update the saved copy of the refresh token."""
        with Path(self._filename).open("w") as fp:
            fp.write(authorizer.refresh_token)

    def pre_refresh_callback(self, authorizer: prawcore.auth.BaseAuthorizer):
        """Load the refresh token from the file."""
        if authorizer.refresh_token is None:
            with Path(self._filename).open() as fp:
                authorizer.refresh_token = fp.read().strip()


class SQLiteTokenManager(BaseTokenManager):
    """Provides a SQLite3 based token manager.

    Unlike, :class:`.FileTokenManager`, the initial database need not be created ahead
    of time, as it'll automatically be created on first use. However, initial refresh
    tokens will need to be registered via :meth:`.register` prior to use.

    .. warning::

        This class is untested on Windows because we encountered file locking issues in
        the test environment.

    """

    @_deprecate_args("database", "key")
    def __init__(self, *, database: str, key: str):
        """Initialize a :class:`.SQLiteTokenManager` instance.

        :param database: The path to the SQLite database.
        :param key: The key used to locate the refresh token. This ``key`` can be
            anything. You might use the ``client_id`` if you expect to have unique a
            refresh token for each ``client_id``, or you might use a redditor's
            ``username`` if you're managing multiple users' authentications.

        """
        super().__init__()
        import sqlite3

        self._connection = sqlite3.connect(database)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS tokens (id, refresh_token, updated_at)"
        )
        self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_tokens_id on tokens(id)"
        )
        self._connection.commit()
        self.key = key

    def _get(self):
        cursor = self._connection.execute(
            "SELECT refresh_token FROM tokens WHERE id=?", (self.key,)
        )
        result = cursor.fetchone()
        if result is None:
            raise KeyError
        return result[0]

    def _set(self, refresh_token: str):
        """Set the refresh token in the database.

        This function will overwrite an existing value if the corresponding ``key``
        already exists.

        """
        self._connection.execute(
            "REPLACE INTO tokens VALUES (?, ?, datetime('now'))",
            (self.key, refresh_token),
        )
        self._connection.commit()

    def is_registered(self) -> bool:
        """Return whether ``key`` already has a ``refresh_token``."""
        cursor = self._connection.execute(
            "SELECT refresh_token FROM tokens WHERE id=?", (self.key,)
        )
        return cursor.fetchone() is not None

    def post_refresh_callback(self, authorizer: prawcore.auth.BaseAuthorizer):
        """Update the refresh token in the database."""
        self._set(authorizer.refresh_token)

        # While the following line is not strictly necessary, it ensures that the
        # refresh token is not used elsewhere. And also forces the pre_refresh_callback
        # to always load the latest refresh_token from the database.
        authorizer.refresh_token = None

    def pre_refresh_callback(self, authorizer: prawcore.auth.BaseAuthorizer):
        """Load the refresh token from the database."""
        assert authorizer.refresh_token is None
        authorizer.refresh_token = self._get()

    def register(self, refresh_token: str) -> bool:
        """Register the initial refresh token in the database.

        :returns: ``True`` if ``refresh_token`` is saved to the database, otherwise,
            ``False`` if there is already a ``refresh_token`` for the associated
            ``key``.

        """
        cursor = self._connection.execute(
            "INSERT OR IGNORE INTO tokens VALUES (?, ?, datetime('now'))",
            (self.key, refresh_token),
        )
        self._connection.commit()
        return cursor.rowcount == 1
