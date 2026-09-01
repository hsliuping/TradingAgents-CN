"""Focused regression checks for the Windows portable MongoDB startup flow."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SERVICES_SCRIPT = ROOT / "scripts" / "installer" / "start_services_clean.ps1"
SETUP_SCRIPT = ROOT / "scripts" / "installer" / "setup.ps1"
START_ALL_SCRIPT = ROOT / "scripts" / "installer" / "start_all.ps1"
IMPORT_SCRIPT = ROOT / "scripts" / "import_config_and_create_user.py"
HELPER_SCRIPT = ROOT / "scripts" / "init_mongodb_user.py"
SYNC_SCRIPT = ROOT / "scripts" / "deployment" / "sync_to_portable.ps1"
PACKAGE_SCRIPT = ROOT / "scripts" / "deployment" / "build_portable_package.ps1"
NSIS_SCRIPT = ROOT / "scripts" / "windows-installer" / "nsis" / "installer.nsi"
PREPARE_SCRIPT = ROOT / "scripts" / "windows-installer" / "prepare" / "build_portable.ps1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _load_functions(*names: str):
    tree = ast.parse(_read(IMPORT_SCRIPT), filename=str(IMPORT_SCRIPT))
    wanted = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
    ]
    namespace = {"Optional": Optional, "re": re}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), str(IMPORT_SCRIPT), "exec"), namespace)
    return [namespace[name] for name in names]


def test_explicit_mongodb_endpoint_overrides_preserve_full_uri():
    _, apply_cli_overrides = _load_functions(
        "rewrite_mongodb_uri_endpoint", "apply_cli_overrides"
    )
    config = {
        "mongodb_host": "localhost",
        "mongodb_port": 27017,
        "mongodb_username": "component-user",
        "mongodb_password": "component-secret",
        "mongodb_database": "component_db",
        "mongodb_auth_source": "admin",
        "mongodb_connection_string": (
            "mongodb://component-user:component-secret@localhost:27017/"
            "component_db?authSource=custom&retryWrites=true"
        ),
    }

    apply_cli_overrides(config, host="127.0.0.1", port=27027)

    assert config["mongodb_host"] == "127.0.0.1"
    assert config["mongodb_port"] == 27027
    assert config["mongodb_connection_string"] == (
        "mongodb://component-user:component-secret@127.0.0.1:27027/"
        "component_db?authSource=custom&retryWrites=true"
    )


def test_endpoint_rewrite_can_add_a_missing_port_without_losing_suffix():
    rewrite = _load_functions("rewrite_mongodb_uri_endpoint")[0]
    uri = "mongodb://user:secret@localhost/component_db?authSource=custom"
    assert rewrite(uri, port=27027) == (
        "mongodb://user:secret@localhost:27027/"
        "component_db?authSource=custom"
    )


def test_startup_scripts_use_configured_port_and_gate_import():
    services = _read(SERVICES_SCRIPT)
    setup = _read(SETUP_SCRIPT)
    start_all = _read(START_ALL_SCRIPT)

    assert "--port $mongoPort" in services
    assert "${mongoProbeHost}:$mongoPort" in services
    assert "--create-only" in services
    assert "--verify-only" in services
    assert "No initialization marker was created" in services
    assert not re.search(r"initScript.*(?:127\.0\.0\.1\s+)?27017", services)

    assert "Wait-ForTcpPort -HostName $mongoProbeHost -Port $mongoPort" in start_all
    assert "--mongodb-host $mongoHost --mongodb-port $mongoPort" in start_all
    assert "Sync-MongoUriEndpoints" in setup
    assert "MONGODB_CONNECTION_STRING|MONGODB_URL|MONGO_URI|MONGODB_URI" in setup
    assert "-PortNumber $MongoPort" in setup
    assert "Sync-MongoUriEndpoints" in start_all
    assert "MONGODB_CONNECTION_STRING|MONGODB_URL|MONGO_URI|MONGODB_URI" in start_all
    assert "exit 1" in start_all[start_all.index("# Step 2: Import"):]
    assert "Set-Content -LiteralPath $importMarkerFile" in start_all
    assert "$importExitCode -eq 0" in start_all


def test_initialization_helper_is_tracked_and_authenticating():
    helper = _read(HELPER_SCRIPT)

    assert "createUser" in helper
    assert "verify_authenticated_user" in helper
    assert "--verify-only" in helper
    assert "client.admin.command(\"ping\")" in helper


def test_build_flows_stage_the_same_startup_payload():
    sync = _read(SYNC_SCRIPT)
    package = _read(PACKAGE_SCRIPT)
    prepare = _read(PREPARE_SCRIPT)

    for script in (sync, package, prepare):
        assert "scripts\\init_mongodb_user.py" in script
        assert "scripts\\import_config_and_create_user.py" in script
        assert "start_services_clean.ps1" in script

    assert "scripts\\installer\\setup.ps1" in sync
    assert "scripts\\installer\\setup.ps1" in package
    assert "scripts\\installer" in prepare
    assert "Destination = \"start_services_clean.ps1\"" in sync
    assert "Destination = \"start_services_clean.ps1\"" in package
    assert "Destination = \"start_services_clean.ps1\"" in prepare


def test_nsis_rewrites_derived_mongodb_uris():
    nsis = _read(NSIS_SCRIPT)

    assert "MONGODB_PORT=$MongoPort" in nsis
    assert "MONGODB_CONNECTION_STRING|MONGODB_URL|MONGO_URI|MONGODB_URI" in nsis
    assert "`$$1`$$2`$$3:$MongoPort" in nsis
