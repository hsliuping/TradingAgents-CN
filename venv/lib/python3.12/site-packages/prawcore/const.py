"""Constants for the prawcore package."""
import os

__version__ = "2.4.0"

ACCESS_TOKEN_PATH = "/api/v1/access_token"  # noqa: S105
AUTHORIZATION_PATH = "/api/v1/authorize"  # noqa: S105
REVOKE_TOKEN_PATH = "/api/v1/revoke_token"  # noqa: S105
TIMEOUT = float(
    os.environ.get(
        "PRAWCORE_TIMEOUT", os.environ.get("prawcore_timeout", 16)  # noqa: SIM112
    )
)
WINDOW_SIZE = 600
