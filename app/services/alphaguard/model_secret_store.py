"""Secret-store boundary for AlphaGuard model credentials.

The production macOS implementation calls Security.framework directly.
Secrets remain process-local byte buffers and never appear in argv, MongoDB,
logs, exceptions, or API responses.
"""

from __future__ import annotations

import ctypes
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
import json
import os
import platform
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

from .credential_host_runtime import CREDENTIAL_HOST_TOKEN_HEADER


KEYCHAIN_ALIAS_SERVICE = "AlphaGuard Credential Alias"
COMPATIBLE_KEYCHAIN_SERVICE = "AlphaGuard Compatible Model API"
PROVIDER_KEYCHAIN_SERVICES = {
    "openai": "AlphaGuard OpenAI API",
    "openai_compatible": COMPATIBLE_KEYCHAIN_SERVICE,
}
_ERR_SEC_ITEM_NOT_FOUND = -25300


class SecretStoreError(RuntimeError):
    """A deliberately non-sensitive Secret Store error."""


class SecretStoreUnavailable(SecretStoreError):
    pass


class SecretNotFound(SecretStoreError):
    pass


class SecretStore(Protocol):
    @property
    def available(self) -> bool: ...

    def read(self, *, service: str, account: str) -> str: ...

    def write(self, *, service: str, account: str, secret: str) -> None: ...

    def delete(
        self, *, service: str, account: str, missing_ok: bool = False
    ) -> None: ...


def keychain_ref(*, service: str, account: str) -> str:
    return (
        f"keychain:{quote(service, safe='')}/{quote(account, safe='')}"
    )


def parse_keychain_ref(reference: str) -> tuple[str | None, str]:
    raw = reference.removeprefix("keychain:")
    if not raw:
        raise SecretStoreError("invalid keychain credential reference")
    if "/" not in raw:
        # Backward compatibility for the PR-010 Level A account-only format.
        return None, unquote(raw)
    service, account = raw.split("/", 1)
    if not service or not account:
        raise SecretStoreError("invalid keychain credential reference")
    return unquote(service), unquote(account)


@dataclass(frozen=True)
class _KeychainBindings:
    security: ctypes.CDLL
    core_foundation: ctypes.CDLL


@lru_cache(maxsize=1)
def _load_keychain_bindings() -> _KeychainBindings:
    security = ctypes.CDLL(
        "/System/Library/Frameworks/Security.framework/Security"
    )
    core_foundation = ctypes.CDLL(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
    )
    security.SecKeychainAddGenericPassword.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    security.SecKeychainFindGenericPassword.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    security.SecKeychainItemModifyAttributesAndData.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
    security.SecKeychainItemFreeContent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    security.SecKeychainItemFreeContent.restype = ctypes.c_int32
    security.SecKeychainItemDelete.argtypes = [ctypes.c_void_p]
    security.SecKeychainItemDelete.restype = ctypes.c_int32
    core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
    core_foundation.CFRelease.restype = None
    return _KeychainBindings(
        security=security,
        core_foundation=core_foundation,
    )


@dataclass(frozen=True)
class MacOSKeychainSecretStore:
    security_framework: Path = Path(
        "/System/Library/Frameworks/Security.framework/Security"
    )
    core_foundation_framework: Path = Path(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
    )

    @property
    def available(self) -> bool:
        if platform.system() != "Darwin":
            return False
        try:
            _load_keychain_bindings()
        except OSError:
            return False
        return True

    def _ensure_available(self) -> None:
        if not self.available:
            raise SecretStoreUnavailable(
                "macOS Keychain Secret Store is unavailable"
            )

    @staticmethod
    def _encoded_identity(
        *,
        service: str,
        account: str,
    ) -> tuple[bytes, bytes]:
        if not service or not account:
            raise SecretStoreError("invalid Keychain identity")
        return service.encode("utf-8"), account.encode("utf-8")

    def _find_item(
        self,
        *,
        service: str,
        account: str,
    ) -> tuple[int, ctypes.c_void_p]:
        self._ensure_available()
        service_bytes, account_bytes = self._encoded_identity(
            service=service,
            account=account,
        )
        item_ref = ctypes.c_void_p()
        try:
            status = _load_keychain_bindings().security[
                "SecKeychainFindGenericPassword"
            ](
                None,
                len(service_bytes),
                service_bytes,
                len(account_bytes),
                account_bytes,
                None,
                None,
                ctypes.byref(item_ref),
            )
        except (OSError, ValueError, ctypes.ArgumentError) as exc:
            raise SecretStoreError(
                "macOS Keychain operation failed"
            ) from exc
        return int(status), item_ref

    @staticmethod
    def _release_item(item_ref: ctypes.c_void_p) -> None:
        if item_ref.value:
            _load_keychain_bindings().core_foundation.CFRelease(item_ref)

    def read(self, *, service: str, account: str) -> str:
        self._ensure_available()
        service_bytes, account_bytes = self._encoded_identity(
            service=service,
            account=account,
        )
        password_length = ctypes.c_uint32()
        password_data = ctypes.c_void_p()
        try:
            status = _load_keychain_bindings().security[
                "SecKeychainFindGenericPassword"
            ](
                None,
                len(service_bytes),
                service_bytes,
                len(account_bytes),
                account_bytes,
                ctypes.byref(password_length),
                ctypes.byref(password_data),
                None,
            )
        except (OSError, ValueError, ctypes.ArgumentError) as exc:
            raise SecretStoreError(
                "macOS Keychain operation failed"
            ) from exc
        if status == _ERR_SEC_ITEM_NOT_FOUND:
            raise SecretNotFound("credential is not configured")
        if status != 0 or not password_data.value:
            raise SecretStoreError("macOS Keychain operation failed")
        try:
            value = ctypes.string_at(
                password_data.value,
                password_length.value,
            ).decode("utf-8")
        except UnicodeError as exc:
            raise SecretStoreError(
                "macOS Keychain credential encoding is invalid"
            ) from exc
        finally:
            _load_keychain_bindings().security.SecKeychainItemFreeContent(
                None,
                password_data,
            )
        if not value:
            raise SecretNotFound("credential is not configured")
        return value

    def write(self, *, service: str, account: str, secret: str) -> None:
        if not secret:
            raise SecretStoreError("empty credentials are not accepted")
        self._ensure_available()
        service_bytes, account_bytes = self._encoded_identity(
            service=service,
            account=account,
        )
        secret_bytes = secret.encode("utf-8")
        secret_buffer = ctypes.create_string_buffer(secret_bytes)
        status, item_ref = self._find_item(
            service=service,
            account=account,
        )
        try:
            if status == 0:
                status = _load_keychain_bindings().security[
                    "SecKeychainItemModifyAttributesAndData"
                ](
                    item_ref,
                    None,
                    len(secret_bytes),
                    ctypes.cast(secret_buffer, ctypes.c_void_p),
                )
            elif status == _ERR_SEC_ITEM_NOT_FOUND:
                status = _load_keychain_bindings().security[
                    "SecKeychainAddGenericPassword"
                ](
                    None,
                    len(service_bytes),
                    service_bytes,
                    len(account_bytes),
                    account_bytes,
                    len(secret_bytes),
                    ctypes.cast(secret_buffer, ctypes.c_void_p),
                    None,
                )
            if status != 0:
                raise SecretStoreError("macOS Keychain operation failed")
        finally:
            self._release_item(item_ref)
            ctypes.memset(secret_buffer, 0, len(secret_buffer))

    def delete(
        self,
        *,
        service: str,
        account: str,
        missing_ok: bool = False,
    ) -> None:
        status, item_ref = self._find_item(
            service=service,
            account=account,
        )
        if status == _ERR_SEC_ITEM_NOT_FOUND:
            if missing_ok:
                return
            raise SecretNotFound("credential is not configured")
        if status != 0 or not item_ref.value:
            raise SecretStoreError("macOS Keychain operation failed")
        try:
            delete_status = (
                _load_keychain_bindings().security.SecKeychainItemDelete(
                    item_ref
                )
            )
            if delete_status != 0:
                raise SecretStoreError("macOS Keychain operation failed")
        finally:
            self._release_item(item_ref)


class UnavailableSecretStore:
    @property
    def available(self) -> bool:
        return False

    def read(self, *, service: str, account: str) -> str:
        raise SecretStoreUnavailable("Secret Store is unavailable")

    def write(self, *, service: str, account: str, secret: str) -> None:
        raise SecretStoreUnavailable("Secret Store is unavailable")

    def delete(
        self,
        *,
        service: str,
        account: str,
        missing_ok: bool = False,
    ) -> None:
        raise SecretStoreUnavailable("Secret Store is unavailable")


_credential_profile_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "alphaguard_credential_profile_context",
    default=None,
)


@dataclass(frozen=True)
class CredentialHostSecretStore:
    """Read-only Secret Store client used by Docker backend processes."""

    base_url: str
    token_path: Path
    timeout_seconds: float = 5.0

    @property
    def available(self) -> bool:
        return bool(self.base_url) and self.token_path.is_file()

    @contextmanager
    def profile_context(self, profile: Any):
        context = {
            "role": profile.role,
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "config_hash": profile.config_hash,
            "credential_ref": profile.credential_ref,
            "endpoint_profile_id": profile.endpoint_profile_id,
            "endpoint_profile_version": profile.endpoint_profile_version,
            "endpoint_model_id": profile.endpoint_model_id,
            "endpoint_model_version": profile.endpoint_model_version,
        }
        token = _credential_profile_context.set(context)
        try:
            yield
        finally:
            _credential_profile_context.reset(token)

    def _token(self) -> str:
        try:
            value = self.token_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError) as exc:
            raise SecretStoreUnavailable(
                "Credential Host authorization is unavailable"
            ) from exc
        if not value:
            raise SecretStoreUnavailable(
                "Credential Host authorization is unavailable"
            )
        return value

    def read(self, *, service: str, account: str) -> str:
        if not self.available:
            raise SecretStoreUnavailable("Credential Host is unavailable")
        body = json.dumps(
            {
                "service": service,
                "account": account,
                "profile": _credential_profile_context.get(),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/internal/alphaguard/credentials/read",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                CREDENTIAL_HOST_TOKEN_HEADER: self._token(),
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {401, 403, 404}:
                raise SecretNotFound("credential is not configured") from exc
            raise SecretStoreUnavailable("Credential Host is unavailable") from exc
        except (URLError, OSError, UnicodeError, ValueError) as exc:
            raise SecretStoreUnavailable("Credential Host is unavailable") from exc
        value = payload.get("value") if isinstance(payload, dict) else None
        if not isinstance(value, str) or not value:
            raise SecretNotFound("credential is not configured")
        return value

    def write(self, *, service: str, account: str, secret: str) -> None:
        raise SecretStoreUnavailable(
            "Credential Host bridge is read-only from Docker services"
        )

    def delete(
        self,
        *,
        service: str,
        account: str,
        missing_ok: bool = False,
    ) -> None:
        raise SecretStoreUnavailable(
            "Credential Host bridge is read-only from Docker services"
        )


def default_secret_store() -> SecretStore:
    store = MacOSKeychainSecretStore()
    if store.available:
        return store
    host_url = os.getenv("ALPHAGUARD_CREDENTIAL_HOST_URL", "").strip()
    token_path = Path(
        os.getenv(
            "ALPHAGUARD_CREDENTIAL_HOST_TOKEN_FILE",
            "/run/alphaguard-credential-host/access.token",
        )
    )
    remote = CredentialHostSecretStore(host_url, token_path)
    return remote if remote.available else UnavailableSecretStore()
