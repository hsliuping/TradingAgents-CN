"""Provide utility for the prawcore package."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .exceptions import Forbidden, InsufficientScope, InvalidToken

if TYPE_CHECKING:
    from requests.models import Response

_auth_error_mapping = {
    403: Forbidden,
    "insufficient_scope": InsufficientScope,
    "invalid_token": InvalidToken,
}


def authorization_error_class(
    response: Response,
) -> InvalidToken | (Forbidden | InsufficientScope):
    """Return an exception instance that maps to the OAuth Error.

    :param response: The HTTP response containing a www-authenticate error.

    """
    message = response.headers.get("www-authenticate")
    error: int | str
    if message:
        error = message.replace('"', "").rsplit("=", 1)[1]
    else:
        error = response.status_code
    return _auth_error_mapping[error](response)
