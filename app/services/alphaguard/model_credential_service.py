"""Resolve credential references without persisting, logging, or exposing values."""

from __future__ import annotations

import os
from pathlib import Path

from .model_secret_store import (
    KEYCHAIN_ALIAS_SERVICE,
    SecretNotFound,
    SecretStore,
    SecretStoreError,
    default_secret_store,
    parse_keychain_ref,
)


_PLACEHOLDERS = (
    "your-api-key",
    "your_api_key",
    "placeholder",
    "replace-me",
    "replace_me",
    "changeme",
)


class CredentialNotConfigured(RuntimeError):
    pass


class ModelCredentialService:
    def __init__(self, secret_store: SecretStore | None = None):
        self.secret_store = secret_store or default_secret_store()

    @staticmethod
    def _valid(value: str | None) -> bool:
        normalized = (value or "").strip()
        return bool(normalized) and not any(
            marker in normalized.lower() for marker in _PLACEHOLDERS
        )

    def configured(self, credential_ref: str) -> bool:
        try:
            value = self.resolve(credential_ref)
        except CredentialNotConfigured:
            return False
        return self._valid(value)

    def resolve(self, credential_ref: str) -> str:
        if credential_ref.startswith("env:"):
            name = credential_ref.removeprefix("env:")
            value = os.getenv(name)
        elif credential_ref.startswith("docker-secret:"):
            name = credential_ref.removeprefix("docker-secret:")
            path = Path("/run/secrets") / name
            value = path.read_text(encoding="utf-8").strip() if path.is_file() else None
        elif credential_ref.startswith("keychain:"):
            try:
                service, account = parse_keychain_ref(credential_ref)
                if service is None:
                    # The old account-only reference remains readable without
                    # changing persisted Level A profile history.
                    from subprocess import run, SubprocessError

                    try:
                        value = run(
                            [
                                "/usr/bin/security",
                                "find-generic-password",
                                "-a",
                                account,
                                "-w",
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=5,
                        ).stdout.strip()
                    except (FileNotFoundError, SubprocessError):
                        value = None
                else:
                    value = self.secret_store.read(
                        service=service, account=account
                    )
            except (SecretNotFound, SecretStoreError):
                value = None
        elif credential_ref.startswith("keychain-alias:"):
            alias = credential_ref.removeprefix("keychain-alias:")
            try:
                target_ref = self.secret_store.read(
                    service=KEYCHAIN_ALIAS_SERVICE,
                    account=alias,
                )
                if not target_ref.startswith("keychain:"):
                    raise CredentialNotConfigured(
                        "invalid Keychain alias target"
                    )
                value = self.resolve(target_ref)
            except (SecretNotFound, SecretStoreError):
                value = None
        else:
            raise CredentialNotConfigured(
                "unsupported credential reference type"
            )
        if not self._valid(value):
            raise CredentialNotConfigured("model credential is not configured")
        return str(value)
