# Copyright 2024-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You
# may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.


"""Constants and types shared across multiple auth types."""
from __future__ import annotations

import os
import typing
from base64 import standard_b64encode
from collections import namedtuple
from typing import Any, Dict, Mapping, Optional

from bson import Binary
from pymongo.auth_oidc_shared import (
    _OIDCAzureCallback,
    _OIDCGCPCallback,
    _OIDCK8SCallback,
    _OIDCProperties,
    _OIDCTestCallback,
)
from pymongo.errors import ConfigurationError

MECHANISMS = frozenset(
    [
        "GSSAPI",
        "MONGODB-OIDC",
        "MONGODB-X509",
        "MONGODB-AWS",
        "PLAIN",
        "SCRAM-SHA-1",
        "SCRAM-SHA-256",
        "DEFAULT",
    ]
)
"""The authentication mechanisms supported by PyMongo."""


class _Cache:
    __slots__ = ("data",)

    _hash_val = hash("_Cache")

    def __init__(self) -> None:
        self.data = None

    def __eq__(self, other: object) -> bool:
        # Two instances must always compare equal.
        if isinstance(other, _Cache):
            return True
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, _Cache):
            return False
        return NotImplemented

    def __hash__(self) -> int:
        return self._hash_val


MongoCredential = namedtuple(
    "MongoCredential",
    ["mechanism", "source", "username", "password", "mechanism_properties", "cache"],
)
"""A hashable namedtuple of values used for authentication."""


GSSAPIProperties = namedtuple(
    "GSSAPIProperties", ["service_name", "canonicalize_host_name", "service_realm", "service_host"]
)
"""Mechanism properties for GSSAPI authentication."""


_AWSProperties = namedtuple("_AWSProperties", ["aws_session_token"])
"""Mechanism properties for MONGODB-AWS authentication."""


def _validate_canonicalize_host_name(value: str | bool) -> str | bool:
    valid_names = [False, True, "none", "forward", "forwardAndReverse"]
    if value in ["true", "false", True, False]:
        return value in ["true", True]

    if value not in valid_names:
        raise ValueError(f"CANONICALIZE_HOST_NAME '{value}' not in valid options: {valid_names}")
    return value


def _build_credentials_tuple(
    mech: str,
    source: Optional[str],
    user: Optional[str],
    passwd: Optional[str],
    extra: Mapping[str, Any],
    database: Optional[str],
) -> MongoCredential:
    """Build and return a mechanism specific credentials tuple."""
    if mech not in ("MONGODB-X509", "MONGODB-AWS", "MONGODB-OIDC") and user is None:
        raise ConfigurationError(f"{mech} requires a username")
    if mech == "GSSAPI":
        if source is not None and source != "$external":
            raise ValueError("authentication source must be $external or None for GSSAPI")
        properties = extra.get("authmechanismproperties", {})
        service_name = properties.get("SERVICE_NAME", "mongodb")
        service_host = properties.get("SERVICE_HOST", None)
        canonicalize = properties.get("CANONICALIZE_HOST_NAME", "false")
        canonicalize = _validate_canonicalize_host_name(canonicalize)
        service_realm = properties.get("SERVICE_REALM")
        props = GSSAPIProperties(
            service_name=service_name,
            canonicalize_host_name=canonicalize,
            service_realm=service_realm,
            service_host=service_host,
        )
        # Source is always $external.
        return MongoCredential(mech, "$external", user, passwd, props, None)
    elif mech == "MONGODB-X509":
        if passwd is not None:
            raise ConfigurationError("Passwords are not supported by MONGODB-X509")
        if source is not None and source != "$external":
            raise ValueError("authentication source must be $external or None for MONGODB-X509")
        # Source is always $external, user can be None.
        return MongoCredential(mech, "$external", user, None, None, None)
    elif mech == "MONGODB-AWS":
        if user is not None and passwd is None:
            raise ConfigurationError("username without a password is not supported by MONGODB-AWS")
        if source is not None and source != "$external":
            raise ConfigurationError(
                "authentication source must be $external or None for MONGODB-AWS"
            )

        properties = extra.get("authmechanismproperties", {})
        aws_session_token = properties.get("AWS_SESSION_TOKEN")
        aws_props = _AWSProperties(aws_session_token=aws_session_token)
        # user can be None for temporary link-local EC2 credentials.
        return MongoCredential(mech, "$external", user, passwd, aws_props, None)
    elif mech == "MONGODB-OIDC":
        properties = extra.get("authmechanismproperties", {})
        callback = properties.get("OIDC_CALLBACK")
        human_callback = properties.get("OIDC_HUMAN_CALLBACK")
        environ = properties.get("ENVIRONMENT")
        token_resource = properties.get("TOKEN_RESOURCE", "")
        default_allowed = [
            "*.mongodb.net",
            "*.mongodb-dev.net",
            "*.mongodb-qa.net",
            "*.mongodbgov.net",
            "localhost",
            "127.0.0.1",
            "::1",
        ]
        allowed_hosts = properties.get("ALLOWED_HOSTS", default_allowed)
        if properties.get("ALLOWED_HOSTS", None) is not None and human_callback is None:
            raise ConfigurationError("ALLOWED_HOSTS is only valid with OIDC_HUMAN_CALLBACK")
        msg = (
            "authentication with MONGODB-OIDC requires providing either a callback or a environment"
        )
        if passwd is not None:
            msg = "password is not supported by MONGODB-OIDC"
            raise ConfigurationError(msg)
        if callback or human_callback:
            if environ is not None:
                raise ConfigurationError(msg)
            if callback and human_callback:
                msg = "cannot set both OIDC_CALLBACK and OIDC_HUMAN_CALLBACK"
                raise ConfigurationError(msg)
        elif environ is not None:
            if environ == "test":
                if user is not None:
                    msg = "test environment for MONGODB-OIDC does not support username"
                    raise ConfigurationError(msg)
                callback = _OIDCTestCallback()
            elif environ == "azure":
                passwd = None
                if not token_resource:
                    raise ConfigurationError(
                        "Azure environment for MONGODB-OIDC requires a TOKEN_RESOURCE auth mechanism property"
                    )
                callback = _OIDCAzureCallback(token_resource)
            elif environ == "gcp":
                passwd = None
                if not token_resource:
                    raise ConfigurationError(
                        "GCP provider for MONGODB-OIDC requires a TOKEN_RESOURCE auth mechanism property"
                    )
                callback = _OIDCGCPCallback(token_resource)
            elif environ == "k8s":
                passwd = None
                callback = _OIDCK8SCallback()
            else:
                raise ConfigurationError(f"unrecognized ENVIRONMENT for MONGODB-OIDC: {environ}")
        else:
            raise ConfigurationError(msg)

        oidc_props = _OIDCProperties(
            callback=callback,
            human_callback=human_callback,
            environment=environ,
            allowed_hosts=allowed_hosts,
            token_resource=token_resource,
            username=user or "",
        )
        return MongoCredential(mech, "$external", user, passwd, oidc_props, _Cache())

    elif mech == "PLAIN":
        source_database = source or database or "$external"
        return MongoCredential(mech, source_database, user, passwd, None, None)
    else:
        source_database = source or database or "admin"
        if passwd is None:
            raise ConfigurationError("A password is required")
        return MongoCredential(mech, source_database, user, passwd, None, _Cache())


def _xor(fir: bytes, sec: bytes) -> bytes:
    """XOR two byte strings together."""
    return b"".join([bytes([x ^ y]) for x, y in zip(fir, sec)])


def _parse_scram_response(response: bytes) -> Dict[bytes, bytes]:
    """Split a scram response into key, value pairs."""
    return dict(
        typing.cast(typing.Tuple[bytes, bytes], item.split(b"=", 1))
        for item in response.split(b",")
    )


def _authenticate_scram_start(
    credentials: MongoCredential, mechanism: str
) -> tuple[bytes, bytes, typing.MutableMapping[str, Any]]:
    username = credentials.username
    user = username.encode("utf-8").replace(b"=", b"=3D").replace(b",", b"=2C")
    nonce = standard_b64encode(os.urandom(32))
    first_bare = b"n=" + user + b",r=" + nonce

    cmd = {
        "saslStart": 1,
        "mechanism": mechanism,
        "payload": Binary(b"n,," + first_bare),
        "autoAuthorize": 1,
        "options": {"skipEmptyExchange": True},
    }
    return nonce, first_bare, cmd
