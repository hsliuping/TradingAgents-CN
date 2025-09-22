"""Provide the Auth class."""

from __future__ import annotations

from prawcore import Authorizer, ImplicitAuthorizer, UntrustedAuthenticator, session

from ..exceptions import InvalidImplicitAuth, MissingRequiredAttributeException
from ..util import _deprecate_args
from .base import PRAWBase


class Auth(PRAWBase):
    """Auth provides an interface to Reddit's authorization."""

    @property
    def limits(self) -> dict[str, str | int | None]:
        """Return a dictionary containing the rate limit info.

        The keys are:

        :remaining: The number of requests remaining to be made in the current rate
            limit window.
        :reset_timestamp: A unix timestamp providing an upper bound on when the rate
            limit counters will reset.
        :used: The number of requests made in the current rate limit window.

        All values are initially ``None`` as these values are set in response to issued
        requests.

        The ``reset_timestamp`` value is an upper bound as the real timestamp is
        computed on Reddit's end in preparation for sending the response. This value may
        change slightly within a given window due to slight changes in response times
        and rounding.

        """
        data = self._reddit._core._rate_limiter
        return {
            "remaining": data.remaining,
            "reset_timestamp": data.reset_timestamp,
            "used": data.used,
        }

    def authorize(self, code: str) -> str | None:
        """Complete the web authorization flow and return the refresh token.

        :param code: The code obtained through the request to the redirect uri.

        :returns: The obtained refresh token, if available, otherwise ``None``.

        The session's active authorization will be updated upon success.

        """
        authenticator = self._reddit._read_only_core._authorizer._authenticator
        authorizer = Authorizer(authenticator)
        authorizer.authorize(code)
        authorized_session = session(
            authorizer=authorizer, window_size=self._reddit.config.window_size
        )
        self._reddit._core = self._reddit._authorized_core = authorized_session
        return authorizer.refresh_token

    @_deprecate_args("access_token", "expires_in", "scope")
    def implicit(self, *, access_token: str, expires_in: int, scope: str):
        """Set the active authorization to be an implicit authorization.

        :param access_token: The access_token obtained from Reddit's callback.
        :param expires_in: The number of seconds the ``access_token`` is valid for. The
            origin of this value was returned from Reddit's callback. You may need to
            subtract an offset before passing in this number to account for a delay
            between when Reddit prepared the response, and when you make this function
            call.
        :param scope: A space-delimited string of Reddit OAuth2 scope names as returned
            from Reddit's callback.

        :raises: :class:`.InvalidImplicitAuth` if :class:`.Reddit` was initialized for a
            non-installed application type.

        """
        authenticator = self._reddit._read_only_core._authorizer._authenticator
        if not isinstance(authenticator, UntrustedAuthenticator):
            raise InvalidImplicitAuth
        implicit_session = session(
            authorizer=ImplicitAuthorizer(
                authenticator, access_token, expires_in, scope
            ),
            window_size=self._reddit.config.window_size,
        )
        self._reddit._core = self._reddit._authorized_core = implicit_session

    def scopes(self) -> set[str]:
        """Return a set of scopes included in the current authorization.

        For read-only authorizations this should return ``{"*"}``.

        """
        authorizer = self._reddit._core._authorizer
        if not authorizer.is_valid():
            authorizer.refresh()
        return authorizer.scopes

    @_deprecate_args("scopes", "state", "duration", "implicit")
    def url(
        self,
        *,
        duration: str = "permanent",
        implicit: bool = False,
        scopes: list[str],
        state: str,
    ) -> str:
        """Return the URL used out-of-band to grant access to your application.

        :param duration: Either ``"permanent"`` or ``"temporary"`` (default:
            ``"permanent"``). ``"temporary"`` authorizations generate access tokens that
            last only 1 hour. ``"permanent"`` authorizations additionally generate a
            refresh token that expires 1 year after the last use and can be used
            indefinitely to generate new hour-long access tokens. This value is ignored
            when ``implicit=True``.
        :param implicit: For **installed** applications, this value can be set to use
            the implicit, rather than the code flow. When ``True``, the ``duration``
            argument has no effect as only temporary tokens can be retrieved.
        :param scopes: A list of OAuth scopes to request authorization for.
        :param state: A string that will be reflected in the callback to
            ``redirect_uri``. This value should be temporarily unique to the client for
            whom the URL was generated for.

        """
        authenticator = self._reddit._read_only_core._authorizer._authenticator
        if authenticator.redirect_uri is self._reddit.config.CONFIG_NOT_SET:
            msg = "redirect_uri must be provided"
            raise MissingRequiredAttributeException(msg)
        if isinstance(authenticator, UntrustedAuthenticator):
            return authenticator.authorize_url(
                "temporary" if implicit else duration,
                scopes,
                state,
                implicit=implicit,
            )
        if implicit:
            raise InvalidImplicitAuth
        return authenticator.authorize_url(duration, scopes, state)
