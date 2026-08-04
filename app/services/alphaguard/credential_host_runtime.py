"""Local authorization material for the macOS Credential Host bridge."""

from __future__ import annotations

import os
from pathlib import Path
import secrets


CREDENTIAL_HOST_TOKEN_NAME = "access.token"
CREDENTIAL_HOST_TOKEN_HEADER = "X-AlphaGuard-Credential-Token"


def ensure_credential_host_runtime(runtime_dir: Path) -> Path:
    """Create a private runtime directory and token without exposing it."""

    runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(runtime_dir, 0o700)
    token_path = runtime_dir / CREDENTIAL_HOST_TOKEN_NAME
    if not token_path.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(token_path, flags, 0o600)
        try:
            token = secrets.token_urlsafe(48).encode("ascii")
            os.write(descriptor, token)
        finally:
            os.close(descriptor)
    os.chmod(token_path, 0o600)
    return token_path


def read_credential_host_token(token_path: Path) -> str:
    try:
        token = token_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(
            "Credential Host authorization material is unavailable"
        ) from exc
    if not token:
        raise RuntimeError(
            "Credential Host authorization material is unavailable"
        )
    return token
