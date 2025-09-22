"""Provides the code to load PRAW's configuration file ``praw.ini``."""

from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path
from threading import Lock
from typing import Any

from .exceptions import ClientException


class _NotSet:
    def __bool__(self) -> bool:
        return False

    __nonzero__ = __bool__

    def __str__(self) -> str:
        return "NotSet"


class Config:
    """A class containing the configuration for a Reddit site."""

    CONFIG = None
    CONFIG_NOT_SET = _NotSet()  # Represents a config value that is not set.
    LOCK = Lock()
    INTERPOLATION_LEVEL = {
        "basic": configparser.BasicInterpolation,
        "extended": configparser.ExtendedInterpolation,
    }

    @staticmethod
    def _config_boolean(item: bool | str) -> bool:
        if isinstance(item, bool):
            return item
        return item.lower() in {"1", "yes", "true", "on"}

    @classmethod
    def _load_config(cls, *, config_interpolation: str | None = None):
        """Attempt to load settings from various praw.ini files."""
        if config_interpolation is not None:
            interpolator_class = cls.INTERPOLATION_LEVEL[config_interpolation]()
        else:
            interpolator_class = None

        config = configparser.ConfigParser(interpolation=interpolator_class)
        module_dir = Path(sys.modules[__name__].__file__).parent

        if "APPDATA" in os.environ:  # Windows
            os_config_path = Path(os.environ["APPDATA"])
        elif "XDG_CONFIG_HOME" in os.environ:  # Modern Linux
            os_config_path = Path(os.environ["XDG_CONFIG_HOME"])
        elif "HOME" in os.environ:  # Legacy Linux
            os_config_path = Path(os.environ["HOME"]) / ".config"
        else:
            os_config_path = None

        locations = [str(module_dir / "praw.ini"), "praw.ini"]

        if os_config_path is not None:
            locations.insert(1, str(os_config_path / "praw.ini"))

        config.read(locations)
        cls.CONFIG = config

    @property
    def short_url(self) -> str:
        """Return the short url.

        :raises: :class:`.ClientException` if it is not set.

        """
        if self._short_url is self.CONFIG_NOT_SET:
            msg = "No short domain specified."
            raise ClientException(msg)
        return self._short_url

    def __init__(
        self,
        site_name: str,
        config_interpolation: str | None = None,
        **settings: str,
    ):
        """Initialize a :class:`.Config` instance."""
        with Config.LOCK:
            if Config.CONFIG is None:
                self._load_config(config_interpolation=config_interpolation)

        self._settings = settings
        self.custom = dict(Config.CONFIG.items(site_name), **settings)

        self.client_id = self.client_secret = self.oauth_url = None
        self.reddit_url = self.refresh_token = self.redirect_uri = None
        self.password = self.user_agent = self.username = None

        self._initialize_attributes()

    def _fetch(self, key: str) -> Any:
        value = self.custom[key]
        del self.custom[key]
        return value

    def _fetch_default(
        self, key: str, *, default: bool | float | str | None = None
    ) -> Any:
        if key not in self.custom:
            return default
        return self._fetch(key)

    def _fetch_or_not_set(self, key: str) -> Any | _NotSet:
        if key in self._settings:  # Passed in values have the highest priority
            return self._fetch(key)

        env_value = os.getenv(f"praw_{key}")
        ini_value = self._fetch_default(key)  # Needed to remove from custom

        # Environment variables have higher priority than praw.ini settings
        return env_value or ini_value or self.CONFIG_NOT_SET

    def _initialize_attributes(self):
        self._short_url = self._fetch_default("short_url") or self.CONFIG_NOT_SET
        self.check_for_async = self._config_boolean(
            self._fetch_default("check_for_async", default=True)
        )
        self.check_for_updates = self._config_boolean(
            self._fetch_or_not_set("check_for_updates")
        )
        self.warn_comment_sort = self._config_boolean(
            self._fetch_default("warn_comment_sort", default=True)
        )
        self.warn_additional_fetch_params = self._config_boolean(
            self._fetch_default("warn_additional_fetch_params", default=True)
        )
        self.window_size = self._fetch_default("window_size", default=600)
        self.kinds = {
            x: self._fetch(f"{x}_kind")
            for x in [
                "comment",
                "message",
                "redditor",
                "submission",
                "subreddit",
                "trophy",
            ]
        }

        for attribute in (
            "client_id",
            "client_secret",
            "redirect_uri",
            "refresh_token",
            "password",
            "user_agent",
            "username",
        ):
            setattr(self, attribute, self._fetch_or_not_set(attribute))

        for required_attribute in (
            "oauth_url",
            "ratelimit_seconds",
            "reddit_url",
            "timeout",
        ):
            setattr(self, required_attribute, self._fetch(required_attribute))

        for attribute, conversion in {
            "ratelimit_seconds": int,
            "timeout": int,
        }.items():
            try:
                setattr(self, attribute, conversion(getattr(self, attribute)))
            except ValueError:
                msg = f"An incorrect config type was given for option {attribute}. The expected type is {conversion.__name__}, but the given value is {getattr(self, attribute)}."
                raise ValueError(msg) from None
