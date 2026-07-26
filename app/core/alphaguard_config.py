"""AlphaGuard PR-001 safety configuration and startup guard.

Real trading is intentionally unavailable during the Baseline Guard phase.
The guard is loaded independently by every process entry point so an unsafe
environment fails before database, queue, or analysis work starts.
"""

from enum import Enum
import logging
from pathlib import Path
from typing import Optional, Union

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class SystemMode(str, Enum):
    """System modes permitted during PR-001."""

    SIM_AUTONOMOUS = "SIM_AUTONOMOUS"


class AlphaGuardSafetySettings(BaseSettings):
    """Fail-closed AlphaGuard safety settings."""

    system_mode: SystemMode = SystemMode.SIM_AUTONOMOUS
    live_trading_enabled: bool = False

    model_config = SettingsConfigDict(
        env_prefix="ALPHAGUARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class AlphaGuardSafetyError(RuntimeError):
    """Raised when AlphaGuard is configured outside the PR-001 safety envelope."""

    def __init__(self, config_key: str, message: str):
        self.config_key = config_key
        super().__init__(message)


def load_alphaguard_safety_settings(
    env_file: Optional[Union[str, Path]] = ".env",
) -> AlphaGuardSafetySettings:
    """Load safety settings and convert schema failures into startup errors."""

    try:
        return AlphaGuardSafetySettings(_env_file=env_file)
    except ValidationError as exc:
        first_error = exc.errors()[0] if exc.errors() else {}
        field_name = str((first_error.get("loc") or ("safety",))[0]).upper()
        config_key = f"ALPHAGUARD_{field_name}"
        raise AlphaGuardSafetyError(
            config_key,
            (
                f"{config_key} is invalid. PR-001 only permits "
                "ALPHAGUARD_SYSTEM_MODE=SIM_AUTONOMOUS and "
                "ALPHAGUARD_LIVE_TRADING_ENABLED=false."
            ),
        ) from exc


def validate_alphaguard_startup_safety(
    safety_settings: Optional[AlphaGuardSafetySettings] = None,
) -> AlphaGuardSafetySettings:
    """Reject any startup configuration that could enable real trading."""

    config = safety_settings or load_alphaguard_safety_settings()

    if config.system_mode is not SystemMode.SIM_AUTONOMOUS:
        raise AlphaGuardSafetyError(
            "ALPHAGUARD_SYSTEM_MODE",
            "PR-001 only permits ALPHAGUARD_SYSTEM_MODE=SIM_AUTONOMOUS.",
        )

    if config.live_trading_enabled:
        raise AlphaGuardSafetyError(
            "ALPHAGUARD_LIVE_TRADING_ENABLED",
            (
                "Real trading is disabled during PR-001. Set "
                "ALPHAGUARD_LIVE_TRADING_ENABLED=false."
            ),
        )

    logger.info(
        "AlphaGuard safety guard passed: system_mode=%s, live_trading_enabled=%s",
        config.system_mode.value,
        config.live_trading_enabled,
    )
    return config
