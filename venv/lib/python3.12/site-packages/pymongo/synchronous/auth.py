# Copyright 2013-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Authentication helpers."""
from __future__ import annotations

import functools
import hashlib
import hmac
import socket
from base64 import standard_b64decode, standard_b64encode
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Mapping,
    MutableMapping,
    Optional,
    cast,
)
from urllib.parse import quote

from bson.binary import Binary
from pymongo.auth_shared import (
    MongoCredential,
    _authenticate_scram_start,
    _parse_scram_response,
    _xor,
)
from pymongo.errors import ConfigurationError, OperationFailure
from pymongo.saslprep import saslprep
from pymongo.synchronous.auth_aws import _authenticate_aws
from pymongo.synchronous.auth_oidc import (
    _authenticate_oidc,
    _get_authenticator,
)
from pymongo.synchronous.helpers import _getaddrinfo

if TYPE_CHECKING:
    from pymongo.hello import Hello
    from pymongo.synchronous.pool import Connection

HAVE_KERBEROS = True
_USE_PRINCIPAL = False
try:
    import winkerberos as kerberos  # type:ignore[import]

    if tuple(map(int, kerberos.__version__.split(".")[:2])) >= (0, 5):
        _USE_PRINCIPAL = True
except ImportError:
    try:
        import kerberos  # type:ignore[import]
    except ImportError:
        HAVE_KERBEROS = False


_IS_SYNC = True


def _authenticate_scram(credentials: MongoCredential, conn: Connection, mechanism: str) -> None:
    """Authenticate using SCRAM."""
    username = credentials.username
    if mechanism == "SCRAM-SHA-256":
        digest = "sha256"
        digestmod = hashlib.sha256
        data = saslprep(credentials.password).encode("utf-8")
    else:
        digest = "sha1"
        digestmod = hashlib.sha1
        data = _password_digest(username, credentials.password).encode("utf-8")
    source = credentials.source
    cache = credentials.cache

    # Make local
    _hmac = hmac.HMAC

    ctx = conn.auth_ctx
    if ctx and ctx.speculate_succeeded():
        assert isinstance(ctx, _ScramContext)
        assert ctx.scram_data is not None
        nonce, first_bare = ctx.scram_data
        res = ctx.speculative_authenticate
    else:
        nonce, first_bare, cmd = _authenticate_scram_start(credentials, mechanism)
        res = conn.command(source, cmd)

    assert res is not None
    server_first = res["payload"]
    parsed = _parse_scram_response(server_first)
    iterations = int(parsed[b"i"])
    if iterations < 4096:
        raise OperationFailure("Server returned an invalid iteration count.")
    salt = parsed[b"s"]
    rnonce = parsed[b"r"]
    if not rnonce.startswith(nonce):
        raise OperationFailure("Server returned an invalid nonce.")

    without_proof = b"c=biws,r=" + rnonce
    if cache.data:
        client_key, server_key, csalt, citerations = cache.data
    else:
        client_key, server_key, csalt, citerations = None, None, None, None

    # Salt and / or iterations could change for a number of different
    # reasons. Either changing invalidates the cache.
    if not client_key or salt != csalt or iterations != citerations:
        salted_pass = hashlib.pbkdf2_hmac(digest, data, standard_b64decode(salt), iterations)
        client_key = _hmac(salted_pass, b"Client Key", digestmod).digest()
        server_key = _hmac(salted_pass, b"Server Key", digestmod).digest()
        cache.data = (client_key, server_key, salt, iterations)
    stored_key = digestmod(client_key).digest()
    auth_msg = b",".join((first_bare, server_first, without_proof))
    client_sig = _hmac(stored_key, auth_msg, digestmod).digest()
    client_proof = b"p=" + standard_b64encode(_xor(client_key, client_sig))
    client_final = b",".join((without_proof, client_proof))

    server_sig = standard_b64encode(_hmac(server_key, auth_msg, digestmod).digest())

    cmd = {
        "saslContinue": 1,
        "conversationId": res["conversationId"],
        "payload": Binary(client_final),
    }
    res = conn.command(source, cmd)

    parsed = _parse_scram_response(res["payload"])
    if not hmac.compare_digest(parsed[b"v"], server_sig):
        raise OperationFailure("Server returned an invalid signature.")

    # A third empty challenge may be required if the server does not support
    # skipEmptyExchange: SERVER-44857.
    if not res["done"]:
        cmd = {
            "saslContinue": 1,
            "conversationId": res["conversationId"],
            "payload": Binary(b""),
        }
        res = conn.command(source, cmd)
        if not res["done"]:
            raise OperationFailure("SASL conversation failed to complete.")


def _password_digest(username: str, password: str) -> str:
    """Get a password digest to use for authentication."""
    if not isinstance(password, str):
        raise TypeError("password must be an instance of str")
    if len(password) == 0:
        raise ValueError("password can't be empty")
    if not isinstance(username, str):
        raise TypeError(f"username must be an instance of str, not {type(username)}")

    md5hash = hashlib.md5()  # noqa: S324
    data = f"{username}:mongo:{password}"
    md5hash.update(data.encode("utf-8"))
    return md5hash.hexdigest()


def _auth_key(nonce: str, username: str, password: str) -> str:
    """Get an auth key to use for authentication."""
    digest = _password_digest(username, password)
    md5hash = hashlib.md5()  # noqa: S324
    data = f"{nonce}{username}{digest}"
    md5hash.update(data.encode("utf-8"))
    return md5hash.hexdigest()


def _canonicalize_hostname(hostname: str, option: str | bool) -> str:
    """Canonicalize hostname following MIT-krb5 behavior."""
    # https://github.com/krb5/krb5/blob/d406afa363554097ac48646a29249c04f498c88e/src/util/k5test.py#L505-L520
    if option in [False, "none"]:
        return hostname

    af, socktype, proto, canonname, sockaddr = (
        _getaddrinfo(
            hostname,
            None,
            family=0,
            type=0,
            proto=socket.IPPROTO_TCP,
            flags=socket.AI_CANONNAME,
        )
    )[0]  # type: ignore[index]

    # For forward just to resolve the cname as dns.lookup() will not return it.
    if option == "forward":
        return canonname.lower()

    try:
        name = socket.getnameinfo(sockaddr, socket.NI_NAMEREQD)
    except socket.gaierror:
        return canonname.lower()

    return name[0].lower()


def _authenticate_gssapi(credentials: MongoCredential, conn: Connection) -> None:
    """Authenticate using GSSAPI."""
    if not HAVE_KERBEROS:
        raise ConfigurationError(
            'The "kerberos" module must be installed to use GSSAPI authentication.'
        )

    try:
        username = credentials.username
        password = credentials.password
        props = credentials.mechanism_properties
        # Starting here and continuing through the while loop below - establish
        # the security context. See RFC 4752, Section 3.1, first paragraph.
        host = props.service_host or conn.address[0]
        host = _canonicalize_hostname(host, props.canonicalize_host_name)
        service = props.service_name + "@" + host
        if props.service_realm is not None:
            service = service + "@" + props.service_realm

        if password is not None:
            if _USE_PRINCIPAL:
                # Note that, though we use unquote_plus for unquoting URI
                # options, we use quote here. Microsoft's UrlUnescape (used
                # by WinKerberos) doesn't support +.
                principal = ":".join((quote(username), quote(password)))
                result, ctx = kerberos.authGSSClientInit(
                    service, principal, gssflags=kerberos.GSS_C_MUTUAL_FLAG
                )
            else:
                if "@" in username:
                    user, domain = username.split("@", 1)
                else:
                    user, domain = username, None
                result, ctx = kerberos.authGSSClientInit(
                    service,
                    gssflags=kerberos.GSS_C_MUTUAL_FLAG,
                    user=user,
                    domain=domain,
                    password=password,
                )
        else:
            result, ctx = kerberos.authGSSClientInit(service, gssflags=kerberos.GSS_C_MUTUAL_FLAG)

        if result != kerberos.AUTH_GSS_COMPLETE:
            raise OperationFailure("Kerberos context failed to initialize.")

        try:
            # pykerberos uses a weird mix of exceptions and return values
            # to indicate errors.
            # 0 == continue, 1 == complete, -1 == error
            # Only authGSSClientStep can return 0.
            if kerberos.authGSSClientStep(ctx, "") != 0:
                raise OperationFailure("Unknown kerberos failure in step function.")

            # Start a SASL conversation with mongod/s
            # Note: pykerberos deals with base64 encoded byte strings.
            # Since mongo accepts base64 strings as the payload we don't
            # have to use bson.binary.Binary.
            payload = kerberos.authGSSClientResponse(ctx)
            cmd = {
                "saslStart": 1,
                "mechanism": "GSSAPI",
                "payload": payload,
                "autoAuthorize": 1,
            }
            response = conn.command("$external", cmd)

            # Limit how many times we loop to catch protocol / library issues
            for _ in range(10):
                result = kerberos.authGSSClientStep(ctx, str(response["payload"]))
                if result == -1:
                    raise OperationFailure("Unknown kerberos failure in step function.")

                payload = kerberos.authGSSClientResponse(ctx) or ""

                cmd = {
                    "saslContinue": 1,
                    "conversationId": response["conversationId"],
                    "payload": payload,
                }
                response = conn.command("$external", cmd)

                if result == kerberos.AUTH_GSS_COMPLETE:
                    break
            else:
                raise OperationFailure("Kerberos authentication failed to complete.")

            # Once the security context is established actually authenticate.
            # See RFC 4752, Section 3.1, last two paragraphs.
            if kerberos.authGSSClientUnwrap(ctx, str(response["payload"])) != 1:
                raise OperationFailure("Unknown kerberos failure during GSS_Unwrap step.")

            if kerberos.authGSSClientWrap(ctx, kerberos.authGSSClientResponse(ctx), username) != 1:
                raise OperationFailure("Unknown kerberos failure during GSS_Wrap step.")

            payload = kerberos.authGSSClientResponse(ctx)
            cmd = {
                "saslContinue": 1,
                "conversationId": response["conversationId"],
                "payload": payload,
            }
            conn.command("$external", cmd)

        finally:
            kerberos.authGSSClientClean(ctx)

    except kerberos.KrbError as exc:
        raise OperationFailure(str(exc)) from None


def _authenticate_plain(credentials: MongoCredential, conn: Connection) -> None:
    """Authenticate using SASL PLAIN (RFC 4616)"""
    source = credentials.source
    username = credentials.username
    password = credentials.password
    payload = (f"\x00{username}\x00{password}").encode()
    cmd = {
        "saslStart": 1,
        "mechanism": "PLAIN",
        "payload": Binary(payload),
        "autoAuthorize": 1,
    }
    conn.command(source, cmd)


def _authenticate_x509(credentials: MongoCredential, conn: Connection) -> None:
    """Authenticate using MONGODB-X509."""
    ctx = conn.auth_ctx
    if ctx and ctx.speculate_succeeded():
        # MONGODB-X509 is done after the speculative auth step.
        return

    cmd = _X509Context(credentials, conn.address).speculate_command()
    conn.command("$external", cmd)


def _authenticate_default(credentials: MongoCredential, conn: Connection) -> None:
    if conn.max_wire_version >= 7:
        if conn.negotiated_mechs:
            mechs = conn.negotiated_mechs
        else:
            source = credentials.source
            cmd = conn.hello_cmd()
            cmd["saslSupportedMechs"] = source + "." + credentials.username
            mechs = (conn.command(source, cmd, publish_events=False)).get("saslSupportedMechs", [])
        if "SCRAM-SHA-256" in mechs:
            return _authenticate_scram(credentials, conn, "SCRAM-SHA-256")
        else:
            return _authenticate_scram(credentials, conn, "SCRAM-SHA-1")
    else:
        return _authenticate_scram(credentials, conn, "SCRAM-SHA-1")


_AUTH_MAP: Mapping[str, Callable[..., None]] = {
    "GSSAPI": _authenticate_gssapi,
    "MONGODB-X509": _authenticate_x509,
    "MONGODB-AWS": _authenticate_aws,
    "MONGODB-OIDC": _authenticate_oidc,  # type:ignore[dict-item]
    "PLAIN": _authenticate_plain,
    "SCRAM-SHA-1": functools.partial(_authenticate_scram, mechanism="SCRAM-SHA-1"),
    "SCRAM-SHA-256": functools.partial(_authenticate_scram, mechanism="SCRAM-SHA-256"),
    "DEFAULT": _authenticate_default,
}


class _AuthContext:
    def __init__(self, credentials: MongoCredential, address: tuple[str, int]) -> None:
        self.credentials = credentials
        self.speculative_authenticate: Optional[Mapping[str, Any]] = None
        self.address = address

    @staticmethod
    def from_credentials(
        creds: MongoCredential, address: tuple[str, int]
    ) -> Optional[_AuthContext]:
        spec_cls = _SPECULATIVE_AUTH_MAP.get(creds.mechanism)
        if spec_cls:
            return cast(_AuthContext, spec_cls(creds, address))
        return None

    def speculate_command(self) -> Optional[MutableMapping[str, Any]]:
        raise NotImplementedError

    def parse_response(self, hello: Hello[Mapping[str, Any]]) -> None:
        self.speculative_authenticate = hello.speculative_authenticate

    def speculate_succeeded(self) -> bool:
        return bool(self.speculative_authenticate)


class _ScramContext(_AuthContext):
    def __init__(
        self, credentials: MongoCredential, address: tuple[str, int], mechanism: str
    ) -> None:
        super().__init__(credentials, address)
        self.scram_data: Optional[tuple[bytes, bytes]] = None
        self.mechanism = mechanism

    def speculate_command(self) -> Optional[MutableMapping[str, Any]]:
        nonce, first_bare, cmd = _authenticate_scram_start(self.credentials, self.mechanism)
        # The 'db' field is included only on the speculative command.
        cmd["db"] = self.credentials.source
        # Save for later use.
        self.scram_data = (nonce, first_bare)
        return cmd


class _X509Context(_AuthContext):
    def speculate_command(self) -> MutableMapping[str, Any]:
        cmd = {"authenticate": 1, "mechanism": "MONGODB-X509"}
        if self.credentials.username is not None:
            cmd["user"] = self.credentials.username
        return cmd


class _OIDCContext(_AuthContext):
    def speculate_command(self) -> Optional[MutableMapping[str, Any]]:
        authenticator = _get_authenticator(self.credentials, self.address)
        cmd = authenticator.get_spec_auth_cmd()
        if cmd is None:
            return None
        cmd["db"] = self.credentials.source
        return cmd


_SPECULATIVE_AUTH_MAP: Mapping[str, Any] = {
    "MONGODB-X509": _X509Context,
    "SCRAM-SHA-1": functools.partial(_ScramContext, mechanism="SCRAM-SHA-1"),
    "SCRAM-SHA-256": functools.partial(_ScramContext, mechanism="SCRAM-SHA-256"),
    "MONGODB-OIDC": _OIDCContext,
    "DEFAULT": functools.partial(_ScramContext, mechanism="SCRAM-SHA-256"),
}


def authenticate(
    credentials: MongoCredential, conn: Connection, reauthenticate: bool = False
) -> None:
    """Authenticate connection."""
    mechanism = credentials.mechanism
    auth_func = _AUTH_MAP[mechanism]
    if mechanism == "MONGODB-OIDC":
        _authenticate_oidc(credentials, conn, reauthenticate)
    else:
        auth_func(credentials, conn)
