"""Resolve credential references without persisting, logging, or exposing values."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


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
            account = credential_ref.removeprefix("keychain:")
            try:
                value = subprocess.run(
                    [
                        "security",
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
            except (FileNotFoundError, subprocess.SubprocessError):
                value = None
        else:
            raise CredentialNotConfigured(
                "unsupported credential reference type"
            )
        if not self._valid(value):
            raise CredentialNotConfigured("model credential is not configured")
        return str(value)
