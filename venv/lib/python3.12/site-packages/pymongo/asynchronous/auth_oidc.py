# Copyright 2023-present MongoDB, Inc.
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

"""MONGODB-OIDC Authentication helpers."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping, MutableMapping, Optional, Union

import bson
from bson.binary import Binary
from pymongo._csot import remaining
from pymongo.auth_oidc_shared import (
    CALLBACK_VERSION,
    HUMAN_CALLBACK_TIMEOUT_SECONDS,
    MACHINE_CALLBACK_TIMEOUT_SECONDS,
    TIME_BETWEEN_CALLS_SECONDS,
    OIDCCallback,
    OIDCCallbackContext,
    OIDCCallbackResult,
    OIDCIdPInfo,
    _OIDCProperties,
)
from pymongo.errors import ConfigurationError, OperationFailure
from pymongo.helpers_shared import _AUTHENTICATION_FAILURE_CODE

if TYPE_CHECKING:
    from pymongo.asynchronous.pool import AsyncConnection
    from pymongo.auth_shared import MongoCredential

_IS_SYNC = False


def _get_authenticator(
    credentials: MongoCredential, address: tuple[str, int]
) -> _OIDCAuthenticator:
    if credentials.cache.data:
        return credentials.cache.data

    # Extract values.
    principal_name = credentials.username
    properties = credentials.mechanism_properties

    # Validate that the address is allowed.
    if properties.human_callback is not None:
        found = False
        allowed_hosts = properties.allowed_hosts
        for patt in allowed_hosts:
            if patt == address[0]:
                found = True
            elif patt.startswith("*.") and address[0].endswith(patt[1:]):
                found = True
        if not found:
            raise ConfigurationError(
                f"Refusing to connect to {address[0]}, which is not in authOIDCAllowedHosts: {allowed_hosts}"
            )

    # Get or create the cache data.
    credentials.cache.data = _OIDCAuthenticator(username=principal_name, properties=properties)
    return credentials.cache.data


@dataclass
class _OIDCAuthenticator:
    username: str
    properties: _OIDCProperties
    refresh_token: Optional[str] = field(default=None)
    access_token: Optional[str] = field(default=None)
    idp_info: Optional[OIDCIdPInfo] = field(default=None)
    token_gen_id: int = field(default=0)
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_call_time: float = field(default=0)

    async def reauthenticate(self, conn: AsyncConnection) -> Optional[Mapping[str, Any]]:
        """Handle a reauthenticate from the server."""
        # Invalidate the token for the connection.
        self._invalidate(conn)
        # Call the appropriate auth logic for the callback type.
        if self.properties.callback:
            return await self._authenticate_machine(conn)
        return await self._authenticate_human(conn)

    async def authenticate(self, conn: AsyncConnection) -> Optional[Mapping[str, Any]]:
        """Handle an initial authenticate request."""
        # First handle speculative auth.
        # If it succeeded, we are done.
        ctx = conn.auth_ctx
        if ctx and ctx.speculate_succeeded():
            resp = ctx.speculative_authenticate
            if resp and resp["done"]:
                conn.oidc_token_gen_id = self.token_gen_id
                return resp

        # If spec auth failed, call the appropriate auth logic for the callback type.
        # We cannot assume that the token is invalid, because a proxy may have been
        # involved that stripped the speculative auth information.
        if self.properties.callback:
            return await self._authenticate_machine(conn)
        return await self._authenticate_human(conn)

    def get_spec_auth_cmd(self) -> Optional[MutableMapping[str, Any]]:
        """Get the appropriate speculative auth command."""
        if not self.access_token:
            return None
        return self._get_start_command({"jwt": self.access_token})

    async def _authenticate_machine(self, conn: AsyncConnection) -> Mapping[str, Any]:
        # If there is a cached access token, try to authenticate with it. If
        # authentication fails with error code 18, invalidate the access token,
        # fetch a new access token, and try to authenticate again. If authentication
        # fails for any other reason, raise the error to the user.
        if self.access_token:
            try:
                return await self._sasl_start_jwt(conn)
            except OperationFailure as e:
                if self._is_auth_error(e):
                    return await self._authenticate_machine(conn)
                raise
        return await self._sasl_start_jwt(conn)

    async def _authenticate_human(self, conn: AsyncConnection) -> Optional[Mapping[str, Any]]:
        # If we have a cached access token, try a JwtStepRequest.
        # authentication fails with error code 18, invalidate the access token,
        # and try to authenticate again.  If authentication fails for any other
        # reason, raise the error to the user.
        if self.access_token:
            try:
                return await self._sasl_start_jwt(conn)
            except OperationFailure as e:
                if self._is_auth_error(e):
                    return await self._authenticate_human(conn)
                raise

        # If we have a cached refresh token, try a JwtStepRequest with that.
        # If authentication fails with error code 18, invalidate the access and
        # refresh tokens, and try to authenticate again. If authentication fails for
        # any other reason, raise the error to the user.
        if self.refresh_token:
            try:
                return await self._sasl_start_jwt(conn)
            except OperationFailure as e:
                if self._is_auth_error(e):
                    self.refresh_token = None
                    return await self._authenticate_human(conn)
                raise

        # Start a new Two-Step SASL conversation.
        # Run a PrincipalStepRequest to get the IdpInfo.
        cmd = self._get_start_command(None)
        start_resp = await self._run_command(conn, cmd)
        # Attempt to authenticate with a JwtStepRequest.
        return await self._sasl_continue_jwt(conn, start_resp)

    def _get_access_token(self) -> Optional[str]:
        properties = self.properties
        cb: Union[None, OIDCCallback]
        resp: OIDCCallbackResult

        is_human = properties.human_callback is not None
        if is_human and self.idp_info is None:
            return None

        if properties.callback:
            cb = properties.callback
        if properties.human_callback:
            cb = properties.human_callback

        prev_token = self.access_token
        if prev_token:
            return prev_token

        if cb is None and not prev_token:
            return None

        if not prev_token and cb is not None:
            with self.lock:
                # See if the token was changed while we were waiting for the
                # lock.
                new_token = self.access_token
                if new_token != prev_token:
                    return new_token

                # Ensure that we are waiting a min time between callback invocations.
                delta = time.time() - self.last_call_time
                if delta < TIME_BETWEEN_CALLS_SECONDS:
                    time.sleep(TIME_BETWEEN_CALLS_SECONDS - delta)
                self.last_call_time = time.time()

                if is_human:
                    timeout = HUMAN_CALLBACK_TIMEOUT_SECONDS
                    assert self.idp_info is not None
                else:
                    timeout = int(remaining() or MACHINE_CALLBACK_TIMEOUT_SECONDS)
                context = OIDCCallbackContext(
                    timeout_seconds=timeout,
                    version=CALLBACK_VERSION,
                    refresh_token=self.refresh_token,
                    idp_info=self.idp_info,
                    username=self.properties.username,
                )
                resp = cb.fetch(context)
                if not isinstance(resp, OIDCCallbackResult):
                    raise ValueError(
                        f"Callback result must be of type OIDCCallbackResult, not {type(resp)}"
                    )
                self.refresh_token = resp.refresh_token
                self.access_token = resp.access_token
                self.token_gen_id += 1

        return self.access_token

    async def _run_command(
        self, conn: AsyncConnection, cmd: MutableMapping[str, Any]
    ) -> Mapping[str, Any]:
        try:
            return await conn.command("$external", cmd, no_reauth=True)  # type: ignore[call-arg]
        except OperationFailure as e:
            if self._is_auth_error(e):
                self._invalidate(conn)
            raise

    def _is_auth_error(self, err: Exception) -> bool:
        if not isinstance(err, OperationFailure):
            return False
        return err.code == _AUTHENTICATION_FAILURE_CODE

    def _invalidate(self, conn: AsyncConnection) -> None:
        # Ignore the invalidation if a token gen id is given and is less than our
        # current token gen id.
        token_gen_id = conn.oidc_token_gen_id or 0
        if token_gen_id is not None and token_gen_id < self.token_gen_id:
            return
        self.access_token = None

    async def _sasl_continue_jwt(
        self, conn: AsyncConnection, start_resp: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.access_token = None
        self.refresh_token = None
        start_payload: dict = bson.decode(start_resp["payload"])
        if "issuer" in start_payload:
            self.idp_info = OIDCIdPInfo(**start_payload)
        access_token = self._get_access_token()
        conn.oidc_token_gen_id = self.token_gen_id
        cmd = self._get_continue_command({"jwt": access_token}, start_resp)
        return await self._run_command(conn, cmd)

    async def _sasl_start_jwt(self, conn: AsyncConnection) -> Mapping[str, Any]:
        access_token = self._get_access_token()
        conn.oidc_token_gen_id = self.token_gen_id
        cmd = self._get_start_command({"jwt": access_token})
        return await self._run_command(conn, cmd)

    def _get_start_command(self, payload: Optional[Mapping[str, Any]]) -> MutableMapping[str, Any]:
        if payload is None:
            principal_name = self.username
            if principal_name:
                payload = {"n": principal_name}
            else:
                payload = {}
        bin_payload = Binary(bson.encode(payload))
        return {"saslStart": 1, "mechanism": "MONGODB-OIDC", "payload": bin_payload}

    def _get_continue_command(
        self, payload: Mapping[str, Any], start_resp: Mapping[str, Any]
    ) -> MutableMapping[str, Any]:
        bin_payload = Binary(bson.encode(payload))
        return {
            "saslContinue": 1,
            "payload": bin_payload,
            "conversationId": start_resp["conversationId"],
        }


async def _authenticate_oidc(
    credentials: MongoCredential, conn: AsyncConnection, reauthenticate: bool
) -> Optional[Mapping[str, Any]]:
    """Authenticate using MONGODB-OIDC."""
    authenticator = _get_authenticator(credentials, conn.address)
    if reauthenticate:
        return await authenticator.reauthenticate(conn)
    else:
        return await authenticator.authenticate(conn)
