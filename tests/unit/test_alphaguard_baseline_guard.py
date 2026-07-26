"""Tests for the AlphaGuard PR-001 startup safety envelope."""

import os
from unittest.mock import patch

import pytest

from app.core.alphaguard_config import (
    AlphaGuardSafetyError,
    AlphaGuardSafetySettings,
    SystemMode,
    load_alphaguard_safety_settings,
    validate_alphaguard_startup_safety,
)
from app.core.startup_validator import StartupValidator


REQUIRED_ENV = {
    "MONGODB_HOST": "localhost",
    "MONGODB_PORT": "27017",
    "MONGODB_DATABASE": "alphaguard_test",
    "MONGODB_DATABASE_SCOPE": "major_instance",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "JWT_SECRET": "alphaguard-test-secret",
}


@patch.dict(os.environ, {}, clear=True)
def test_safety_defaults_are_simulation_only():
    config = AlphaGuardSafetySettings(_env_file=None)

    assert config.system_mode is SystemMode.SIM_AUTONOMOUS
    assert config.live_trading_enabled is False


def test_safe_configuration_passes_startup_guard():
    config = AlphaGuardSafetySettings(
        system_mode=SystemMode.SIM_AUTONOMOUS,
        live_trading_enabled=False,
        _env_file=None,
    )

    assert validate_alphaguard_startup_safety(config) is config


@patch.dict(
    os.environ,
    {
        "ALPHAGUARD_SYSTEM_MODE": "LIVE",
        "ALPHAGUARD_LIVE_TRADING_ENABLED": "false",
    },
    clear=True,
)
def test_unknown_system_mode_fails_closed():
    with pytest.raises(AlphaGuardSafetyError) as exc_info:
        load_alphaguard_safety_settings(env_file=None)

    assert exc_info.value.config_key == "ALPHAGUARD_SYSTEM_MODE"


@patch.dict(
    os.environ,
    {
        "ALPHAGUARD_SYSTEM_MODE": "SIM_AUTONOMOUS",
        "ALPHAGUARD_LIVE_TRADING_ENABLED": "true",
    },
    clear=True,
)
def test_live_trading_enabled_fails_closed():
    with pytest.raises(AlphaGuardSafetyError) as exc_info:
        validate_alphaguard_startup_safety(
            load_alphaguard_safety_settings(env_file=None)
        )

    assert exc_info.value.config_key == "ALPHAGUARD_LIVE_TRADING_ENABLED"


@patch.dict(
    os.environ,
    {
        **REQUIRED_ENV,
        "ALPHAGUARD_SYSTEM_MODE": "SIM_AUTONOMOUS",
        "ALPHAGUARD_LIVE_TRADING_ENABLED": "true",
    },
    clear=True,
)
def test_existing_startup_validator_reports_alphaguard_violation():
    result = StartupValidator().validate()

    invalid_keys = [config.key for config, _ in result.invalid_configs]
    assert result.success is False
    assert "ALPHAGUARD_LIVE_TRADING_ENABLED" in invalid_keys
