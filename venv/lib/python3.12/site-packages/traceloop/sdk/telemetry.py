import os
import uuid
from pathlib import Path
import logging
import sys
from posthog import Posthog
from traceloop.sdk.version import __version__

POSTHOG_API_KEY = "phc_6AT2D3sP5u4fkUZtSqgtmoKmcx8rEX8f86lpISOpAhx"


class Telemetry:
    ANON_ID_PATH = str(Path.home() / ".cache" / "traceloop" / "telemetry_anon_id")
    UNKNOWN_ANON_ID = "UNKNOWN"

    _posthog: Posthog = None

    def __new__(cls) -> "Telemetry":
        if not hasattr(cls, "instance"):
            obj = cls.instance = super(Telemetry, cls).__new__(cls)
            obj._telemetry_enabled = (
                os.getenv("TRACELOOP_TELEMETRY") or "true"
            ).lower() == "true" and "pytest" not in sys.modules

            if obj._telemetry_enabled:
                try:
                    obj._posthog = Posthog(
                        project_api_key=POSTHOG_API_KEY,
                        host="https://app.posthog.com",
                    )
                    obj._curr_anon_id = None

                    posthog_logger = logging.getLogger("posthog")
                    posthog_logger.disabled = True
                except Exception:
                    # disable telemetry if it fails
                    obj._telemetry_enabled = False

        return cls.instance

    def _anon_id(self) -> str:
        if self._curr_anon_id:
            return self._curr_anon_id

        try:
            if not os.path.exists(self.ANON_ID_PATH):
                os.makedirs(os.path.dirname(self.ANON_ID_PATH), exist_ok=True)
                with open(self.ANON_ID_PATH, "w") as f:
                    new_anon_id = str(uuid.uuid4())
                    f.write(new_anon_id)
                self._curr_anon_id = new_anon_id
            else:
                with open(self.ANON_ID_PATH, "r") as f:
                    self._curr_anon_id = f.read()
        except Exception:
            self._curr_anon_id = self.UNKNOWN_ANON_ID
        return self._curr_anon_id

    def _context(self) -> dict:
        return {
            "sdk": "python",
            "sdk_version": __version__,
            "$process_person_profile": False,
        }

    def capture(self, event: str, event_properties: dict = {}) -> None:
        try:  # don't fail if telemetry fails
            if self._telemetry_enabled:
                self._posthog.capture(
                    self._anon_id(), event, {**self._context(), **event_properties}
                )
        except Exception:
            pass

    def log_exception(self, exception: Exception):
        try:  # don't fail if telemetry fails
            return self._posthog.capture(
                self._anon_id(),
                "exception",
                {
                    **self._context(),
                    "exception": str(exception),
                },
            )
        except Exception:
            pass

    def feature_enabled(self, key: str):
        try:  # don't fail if telemetry fails
            if self._telemetry_enabled:
                return self._posthog.feature_enabled(key, self._anon_id())
        except Exception:
            pass
        return False
