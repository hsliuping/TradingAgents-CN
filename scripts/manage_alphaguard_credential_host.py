#!/usr/bin/env python3
"""Install and inspect the macOS LaunchAgent for Credential Host."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.alphaguard.credential_host_runtime import (  # noqa: E402
    ensure_credential_host_runtime,
)


LABEL = "com.alphaguard.credential-host"
RUNTIME_DIR = ROOT / "runtime" / "credential-host"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _launch_agent_payload() -> dict:
    managed_python = ROOT / ".venv" / "bin" / "python"
    python = managed_python if managed_python.is_file() else Path(sys.executable)
    entrypoint = ROOT / "scripts" / "run_alphaguard_credential_host.py"
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(python),
            str(entrypoint),
            "--execute",
            "--host",
            "0.0.0.0",
            "--port",
            "8011",
            "--runtime-dir",
            str(RUNTIME_DIR),
        ],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        "ProcessType": "Background",
        "Umask": 0o077,
        "StandardOutPath": str(RUNTIME_DIR / "credential-host.stdout.log"),
        "StandardErrorPath": str(RUNTIME_DIR / "credential-host.stderr.log"),
    }


def _write_plist() -> None:
    ensure_credential_host_runtime(RUNTIME_DIR)
    PLIST_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = PLIST_PATH.with_suffix(".plist.tmp")
    with temporary.open("wb") as output:
        plistlib.dump(_launch_agent_payload(), output, sort_keys=True)
    os.chmod(temporary, 0o600)
    temporary.replace(PLIST_PATH)


def _run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/launchctl", *arguments],
        check=check,
        capture_output=True,
        text=True,
        timeout=15,
    )


def install() -> int:
    _write_plist()
    _run("bootout", _domain(), str(PLIST_PATH), check=False)
    _run("bootstrap", _domain(), str(PLIST_PATH))
    _run("kickstart", "-k", f"{_domain()}/{LABEL}")
    print("credential_host_service=INSTALLED")
    return 0


def status() -> int:
    result = _run("print", f"{_domain()}/{LABEL}", check=False)
    running = result.returncode == 0 and "state = running" in result.stdout
    print(f"credential_host_service={'RUNNING' if running else 'STOPPED'}")
    print(f"launch_agent={'INSTALLED' if PLIST_PATH.is_file() else 'MISSING'}")
    print(
        "authorization_material="
        f"{'READY' if (RUNTIME_DIR / 'access.token').is_file() else 'MISSING'}"
    )
    return 0 if running else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "status"))
    args = parser.parse_args()
    return install() if args.action == "install" else status()


if __name__ == "__main__":
    raise SystemExit(main())
