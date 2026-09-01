#!/usr/bin/env python3
"""Create and verify the MongoDB user used by the Windows portable package.

The startup script runs this helper once while MongoDB is in no-auth mode and
again after restarting MongoDB with authentication enabled.  Keeping the
database work here makes the PowerShell orchestration independent of a
bundled ``mongosh`` executable.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from pymongo import MongoClient


DEFAULT_AUTH_SOURCE = "admin"
DEFAULT_SERVER_SELECTION_TIMEOUT_MS = 5_000


def _connect(
    host: str,
    port: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    auth_source: str = DEFAULT_AUTH_SOURCE,
) -> MongoClient:
    """Open a client and fail quickly when the local server is unavailable."""
    options = {
        "serverSelectionTimeoutMS": DEFAULT_SERVER_SELECTION_TIMEOUT_MS,
        "connectTimeoutMS": DEFAULT_SERVER_SELECTION_TIMEOUT_MS,
    }
    if username is not None and password is not None:
        options.update(
            username=username,
            password=password,
            authSource=auth_source,
        )
    return MongoClient(host, port, **options)


def verify_authenticated_user(
    host: str,
    port: int,
    username: str,
    password: str,
    auth_source: str = DEFAULT_AUTH_SOURCE,
) -> None:
    """Verify that MongoDB accepts the configured credentials."""
    client = _connect(host, port, username, password, auth_source)
    try:
        # ping is deliberately issued through an authenticated client.  It
        # forces server selection and authentication before returning.
        client.admin.command("ping")
        status = client.admin.command("connectionStatus")
        authenticated_users = status.get("authInfo", {}).get("authenticatedUsers", [])
        if not any(
            user.get("user") == username and user.get("db") == auth_source
            for user in authenticated_users
        ):
            raise RuntimeError(
                f"MongoDB did not authenticate user '{username}' from '{auth_source}'"
            )
    finally:
        client.close()


def initialize_user(
    host: str,
    port: int,
    username: str,
    password: str,
    auth_source: str = DEFAULT_AUTH_SOURCE,
    verify: bool = True,
) -> None:
    """Create the admin user if needed, then optionally verify its credentials."""
    client = _connect(host, port)
    try:
        client.admin.command("ping")
        users = client[auth_source].command("usersInfo", username).get("users", [])
        if users:
            print(f"MongoDB user '{username}' already exists; verifying it")
        else:
            client[auth_source].command(
                "createUser",
                username,
                pwd=password,
                roles=[{"role": "root", "db": "admin"}],
            )
            print(f"MongoDB user '{username}' created")
    finally:
        client.close()

    if verify:
        verify_authenticated_user(host, port, username, password, auth_source)
        print(f"MongoDB authentication verified for user '{username}'")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="MongoDB host")
    parser.add_argument("port", type=int, help="MongoDB port")
    parser.add_argument("username", help="MongoDB username")
    parser.add_argument("password", help="MongoDB password")
    parser.add_argument(
        "--auth-source",
        default=DEFAULT_AUTH_SOURCE,
        help="Database containing the user (default: admin)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify credentials; do not create a user",
    )
    parser.add_argument(
        "--create-only",
        action="store_true",
        help="Create the user without verification (for a no-auth server)",
    )
    args = parser.parse_args(argv)

    try:
        if args.verify_only and args.create_only:
            parser.error("--verify-only and --create-only cannot be combined")
        if args.verify_only:
            verify_authenticated_user(
                args.host,
                args.port,
                args.username,
                args.password,
                args.auth_source,
            )
            print(f"MongoDB authentication verified for user '{args.username}'")
        else:
            initialize_user(
                args.host,
                args.port,
                args.username,
                args.password,
                args.auth_source,
                verify=not args.create_only,
            )
    except Exception as exc:
        print(f"MongoDB user initialization failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
