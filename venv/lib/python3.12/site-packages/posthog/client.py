import atexit
import hashlib
import logging
import numbers
import os
import platform
import sys
import warnings
from datetime import datetime, timedelta
from typing import Any, Optional, Union
from uuid import UUID, uuid4

import distro  # For Linux OS detection
from dateutil.tz import tzutc
from six import string_types

from posthog.consumer import Consumer
from posthog.exception_capture import ExceptionCapture
from posthog.exception_utils import exc_info_from_error, exceptions_from_error_tuple, handle_in_app
from posthog.feature_flags import InconclusiveMatchError, match_feature_flag_properties
from posthog.poller import Poller
from posthog.request import (
    DEFAULT_HOST,
    APIError,
    batch_post,
    decide,
    determine_server_host,
    flags,
    get,
    remote_config,
)
from posthog.types import (
    FeatureFlag,
    FlagMetadata,
    FlagsAndPayloads,
    FlagsResponse,
    FlagValue,
    normalize_flags_response,
    to_flags_and_payloads,
    to_payloads,
    to_values,
)
from posthog.utils import SizeLimitedDict, clean, guess_timezone, remove_trailing_slash
from posthog.version import VERSION

try:
    import queue
except ImportError:
    import Queue as queue


ID_TYPES = (numbers.Number, string_types, UUID)
MAX_DICT_SIZE = 50_000

# TODO: Get rid of these when you're done rolling out `/flags` to all customers
ROLLOUT_PERCENTAGE = 1
INCLUDED_HASHES = set({"bc94e67150c97dbcbf52549d50a7b80814841dbf"})  # this is PostHog's API key
# Explicitly excluding all the API tokens associated with the top 10 customers; we'll get to them soon, but don't want to rollout to them just yet
EXCLUDED_HASHES = set(
    {
        "03005596796f9ee626e9596b8062972cb6a556a0",
        "05620a20b287e0d5cb1d4a0dd492797f36b952c5",
        "0f95b5ca12878693c01c6420e727904f1737caa7",
        "1212b6287a6e7e5ff6be5cb30ec563f35c2139d6",
        "171ec1bb2caf762e06b1fde2e36a38c4638691a8",
        "171faa9fc754b1aa42252a4eedb948b7c805d5cb",
        "178ddde3f628fb0030321387acf939e4e6946d35",
        "1790085d7e9aa136e8b73c180dd6a6060e2ef949",
        "1895a3349c2371559c886f19ef1bf60617a934e0",
        "1f01267d4f0295f88e8943bc963d816ee4abc84b",
        "213df54990a34e62e3570b430f7ee36ec0928743",
        "23d235537d988ab98ad259853eab02b07d828c2b",
        "27135f7ae8f936222a5fcfcdc75c139b27dd3254",
        "2817396d80fafc86c0816af8e73880f8b3e54320",
        "29d3235e63db42056858ef04c6a5488c2a459eaa",
        "2a76d9b5eb9307e540de9d516aa80f6cb5a0292f",
        "2a92965a1344ab8a1f7dac2507e858f579a88ac2",
        "2d5823818261512d616161de2bb8a161d48f1e35",
        "32942f6a879dbfa8011cc68288c098e4a76e6cc0",
        "3db6c17ab65827ceadf77d9a8462fabd94170ca6",
        "4975b24f9ced9b2c06b604ddc9612f663f9452d5",
        "497c7b017b13cd6cdbfe641c71f0dfb660a4c518",
        "49c79e1dbce4a7b9394d6c14bf0421e04cecb445",
        "4d63e1c5cd3a80972eac4e7526f03357ac538043",
        "4da0f42a6f8f116822411152e5cda3c65ed2561f",
        "4e494675ecd2b841784d6f29b658b38a0877a62e",
        "4e852d8422130cec991eca2d6416dbe321d0a689",
        "5120bfd92c9c6731074a89e4a82f49e947d34369",
        "512cd72f9aa7ab11dfd012cc2e19394a020bd9a8",
        "5b175d4064cc62f01118a2c6818c2c02fc8f27e1",
        "5ba4bba3979e97d2c84df2aba394ca29c6c43187",
        "639014946463614353ca640b268dc6592f62b652",
        "643b9be9d50104e2b4ba94bc56688adba69c80fe",
        "658f92992af9fc6a360143d72d93a36f63bbccb0",
        "673a59c99739dfcee35202e428dd020b94866d52",
        "67a9829b4997f5c6f3ab8173ad299f634adcfa53",
        "6d686043e914ae8275df65e1ad890bd32a3b6fdd",
        "6e4b5e1d649ad006d78f1f1617a9a0f35fc73078",
        "6f1fc3a8fa9df54d00cbc1ef9ad5f24640589fd0",
        "764e5fec2c7899cfee620fae8450fcc62cd72bf0",
        "80ea6d6ed9a5895633c7bee7aba4323eeacdc90e",
        "872e420156f583bc97351f3d83c02dae734a85df",
        "8a24844cbeae31e74b4372964cdea74e99d9c0e2",
        "975ae7330506d4583b000f96ad87abb41a0141ce",
        "9e3d71378b340def3080e0a3a785a1b964cf43ef",
        "9ede7b21365661331d024d92915de6e69749892b",
        "a1ed1b4216ef4cec542c6b3b676507770be24ddc",
        "a4f66a70a9647b3b89fc59f7642af8ffab073ba1",
        "a7adb80be9e90948ab6bb726cc6e8e52694aec74",
        "bca4b14ac8de49cccc02306c7bb6e5ae2acc0f72",
        "bde5fe49f61e13629c5498d7428a7f6215e482a6",
        "c54a7074c323aa7c5cb7b24bf826751b2a58f5d8",
        "c552d20da0c87fb4ebe2da97c7f95c05eef2bca1",
        "d7682f2d268f3064d433309af34f2935810989d2",
        "d794ac43d8be26bf99f369ea79501eb774fe1b16",
        "e0963e2552af77d46bb24d5b5806b5b456c64c5f",
        "e6f14b2100cb0598925958b097ace82486037a25",
        "e79ec399ad45f44a4295a5bb1322e2f14600ae39",
        "eecf29f73f9c31009e5737a6c5ec3f87ec5b8ea6",
        "f2c01f3cc770c7788257ee60910e2530f92eefc3",
        "f7bbc58f4122b1e2812c0f1962c584cb404a1ac3",
    }
)


def get_os_info():
    """
    Returns standardized OS name and version information.
    Similar to how user agent parsing works in JS.
    """
    os_name = ""
    os_version = ""

    platform_name = sys.platform

    if platform_name.startswith("win"):
        os_name = "Windows"
        if hasattr(platform, "win32_ver"):
            win_version = platform.win32_ver()[0]
            if win_version:
                os_version = win_version

    elif platform_name == "darwin":
        os_name = "Mac OS X"
        if hasattr(platform, "mac_ver"):
            mac_version = platform.mac_ver()[0]
            if mac_version:
                os_version = mac_version

    elif platform_name.startswith("linux"):
        os_name = "Linux"
        linux_info = distro.info()
        if linux_info["version"]:
            os_version = linux_info["version"]

    elif platform_name.startswith("freebsd"):
        os_name = "FreeBSD"
        if hasattr(platform, "release"):
            os_version = platform.release()

    else:
        os_name = platform_name
        if hasattr(platform, "release"):
            os_version = platform.release()

    return os_name, os_version


def system_context() -> dict[str, Any]:
    os_name, os_version = get_os_info()

    return {
        "$python_runtime": platform.python_implementation(),
        "$python_version": "%s.%s.%s" % (sys.version_info[:3]),
        "$os": os_name,
        "$os_version": os_version,
    }


def is_token_in_rollout(
    token: str,
    percentage: float = 0,
    included_hashes: Optional[set[str]] = None,
    excluded_hashes: Optional[set[str]] = None,
) -> bool:
    """
    Determines if a token should be included in a rollout based on:
    1. If its hash matches any included_hashes provided
    2. If its hash falls within the percentage rollout

    Args:
        token: String to hash (usually API key)
        percentage: Float between 0 and 1 representing rollout percentage
        included_hashes: Optional set of specific SHA1 hashes to match against
        excluded_hashes: Optional set of specific SHA1 hashes to exclude from rollout
    Returns:
        bool: True if token should be included in rollout
    """
    # First generate SHA1 hash of token
    token_hash = hashlib.sha1(token.encode("utf-8")).hexdigest()

    # Check if hash matches any included hashes
    if included_hashes and token_hash in included_hashes:
        return True

    # Check if hash matches any excluded hashes
    if excluded_hashes and token_hash in excluded_hashes:
        return False

    # Convert first 8 chars of hash to int and divide by max value to get number between 0-1
    hash_int = int(token_hash[:8], 16)
    hash_float = hash_int / 0xFFFFFFFF

    return hash_float < percentage


class Client(object):
    """Create a new PostHog client."""

    log = logging.getLogger("posthog")

    def __init__(
        self,
        api_key=None,
        host=None,
        debug=False,
        max_queue_size=10000,
        send=True,
        on_error=None,
        flush_at=100,
        flush_interval=0.5,
        gzip=False,
        max_retries=3,
        sync_mode=False,
        timeout=15,
        thread=1,
        poll_interval=30,
        personal_api_key=None,
        project_api_key=None,
        disabled=False,
        disable_geoip=True,
        historical_migration=False,
        feature_flags_request_timeout_seconds=3,
        super_properties=None,
        enable_exception_autocapture=False,
        log_captured_exceptions=False,
        exception_autocapture_integrations=None,
        project_root=None,
        privacy_mode=False,
    ):
        self.queue = queue.Queue(max_queue_size)

        # api_key: This should be the Team API Key (token), public
        self.api_key = project_api_key or api_key

        require("api_key", self.api_key, string_types)

        self.on_error = on_error
        self.debug = debug
        self.send = send
        self.sync_mode = sync_mode
        # Used for session replay URL generation - we don't want the server host here.
        self.raw_host = host or DEFAULT_HOST
        self.host = determine_server_host(host)
        self.gzip = gzip
        self.timeout = timeout
        self._feature_flags = None  # private variable to store flags
        self.feature_flags_by_key = None
        self.group_type_mapping = None
        self.cohorts = None
        self.poll_interval = poll_interval
        self.feature_flags_request_timeout_seconds = feature_flags_request_timeout_seconds
        self.poller = None
        self.distinct_ids_feature_flags_reported = SizeLimitedDict(MAX_DICT_SIZE, set)
        self.disabled = disabled
        self.disable_geoip = disable_geoip
        self.historical_migration = historical_migration
        self.super_properties = super_properties
        self.enable_exception_autocapture = enable_exception_autocapture
        self.log_captured_exceptions = log_captured_exceptions
        self.exception_autocapture_integrations = exception_autocapture_integrations
        self.exception_capture = None
        self.privacy_mode = privacy_mode

        if project_root is None:
            try:
                project_root = os.getcwd()
            except Exception:
                project_root = None

        self.project_root = project_root

        # personal_api_key: This should be a generated Personal API Key, private
        self.personal_api_key = personal_api_key
        if debug:
            # Ensures that debug level messages are logged when debug mode is on.
            # Otherwise, defaults to WARNING level. See https://docs.python.org/3/howto/logging.html#what-happens-if-no-configuration-is-provided
            logging.basicConfig()
            self.log.setLevel(logging.DEBUG)
        else:
            self.log.setLevel(logging.WARNING)

        if self.enable_exception_autocapture:
            self.exception_capture = ExceptionCapture(self, integrations=self.exception_autocapture_integrations)

        if sync_mode:
            self.consumers = None
        else:
            # On program exit, allow the consumer thread to exit cleanly.
            # This prevents exceptions and a messy shutdown when the
            # interpreter is destroyed before the daemon thread finishes
            # execution. However, it is *not* the same as flushing the queue!
            # To guarantee all messages have been delivered, you'll still need
            # to call flush().
            if send:
                atexit.register(self.join)
            for n in range(thread):
                self.consumers = []
                consumer = Consumer(
                    self.queue,
                    self.api_key,
                    host=self.host,
                    on_error=on_error,
                    flush_at=flush_at,
                    flush_interval=flush_interval,
                    gzip=gzip,
                    retries=max_retries,
                    timeout=timeout,
                    historical_migration=historical_migration,
                )
                self.consumers.append(consumer)

                # if we've disabled sending, just don't start the consumer
                if send:
                    consumer.start()

    @property
    def feature_flags(self):
        """
        Get the local evaluation feature flags.
        """
        return self._feature_flags

    @feature_flags.setter
    def feature_flags(self, flags):
        """
        Set the local evaluation feature flags.
        """
        self._feature_flags = flags or []
        self.feature_flags_by_key = {flag["key"]: flag for flag in self._feature_flags if flag.get("key") is not None}
        assert (
            self.feature_flags_by_key is not None
        ), "feature_flags_by_key should be initialized when feature_flags is set"

    def identify(self, distinct_id=None, properties=None, context=None, timestamp=None, uuid=None, disable_geoip=None):
        if context is not None:
            warnings.warn(
                "The 'context' parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )

        properties = properties or {}
        require("distinct_id", distinct_id, ID_TYPES)
        require("properties", properties, dict)

        msg = {
            "timestamp": timestamp,
            "distinct_id": distinct_id,
            "$set": properties,
            "event": "$identify",
            "uuid": uuid,
        }

        return self._enqueue(msg, disable_geoip)

    def get_feature_variants(
        self, distinct_id, groups=None, person_properties=None, group_properties=None, disable_geoip=None
    ) -> dict[str, Union[bool, str]]:
        """
        Get feature flag variants for a distinct_id by calling decide.
        """
        resp_data = self.get_flags_decision(distinct_id, groups, person_properties, group_properties, disable_geoip)
        return to_values(resp_data) or {}

    def get_feature_payloads(
        self, distinct_id, groups=None, person_properties=None, group_properties=None, disable_geoip=None
    ) -> dict[str, str]:
        """
        Get feature flag payloads for a distinct_id by calling decide.
        """
        resp_data = self.get_flags_decision(distinct_id, groups, person_properties, group_properties, disable_geoip)
        return to_payloads(resp_data) or {}

    def get_feature_flags_and_payloads(
        self, distinct_id, groups=None, person_properties=None, group_properties=None, disable_geoip=None
    ) -> FlagsAndPayloads:
        """
        Get feature flags and payloads for a distinct_id by calling decide.
        """
        resp = self.get_flags_decision(distinct_id, groups, person_properties, group_properties, disable_geoip)
        return to_flags_and_payloads(resp)

    def get_flags_decision(
        self, distinct_id, groups=None, person_properties=None, group_properties=None, disable_geoip=None
    ) -> FlagsResponse:
        """
        Get feature flags decision, using either flags() or decide() API based on rollout.
        """
        require("distinct_id", distinct_id, ID_TYPES)

        if disable_geoip is None:
            disable_geoip = self.disable_geoip

        if groups:
            require("groups", groups, dict)
        else:
            groups = {}

        request_data = {
            "distinct_id": distinct_id,
            "groups": groups,
            "person_properties": person_properties,
            "group_properties": group_properties,
            "disable_geoip": disable_geoip,
        }

        use_flags = is_token_in_rollout(
            self.api_key, ROLLOUT_PERCENTAGE, included_hashes=INCLUDED_HASHES, excluded_hashes=EXCLUDED_HASHES
        )

        if use_flags:
            resp_data = flags(
                self.api_key, self.host, timeout=self.feature_flags_request_timeout_seconds, **request_data
            )
        else:
            resp_data = decide(
                self.api_key, self.host, timeout=self.feature_flags_request_timeout_seconds, **request_data
            )

        return normalize_flags_response(resp_data)

    def capture(
        self,
        distinct_id=None,
        event=None,
        properties=None,
        context=None,
        timestamp=None,
        uuid=None,
        groups=None,
        send_feature_flags=False,
        disable_geoip=None,
    ):
        if context is not None:
            warnings.warn(
                "The 'context' parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )

        properties = {**(properties or {}), **system_context()}

        require("distinct_id", distinct_id, ID_TYPES)
        require("properties", properties, dict)
        require("event", event, string_types)

        msg = {
            "properties": properties,
            "timestamp": timestamp,
            "distinct_id": distinct_id,
            "event": event,
            "uuid": uuid,
        }

        if groups:
            require("groups", groups, dict)
            msg["properties"]["$groups"] = groups

        extra_properties: dict[str, Any] = {}
        feature_variants: Optional[dict[str, Union[bool, str]]] = {}
        if send_feature_flags:
            try:
                feature_variants = self.get_feature_variants(distinct_id, groups, disable_geoip=disable_geoip)
            except Exception as e:
                self.log.exception(f"[FEATURE FLAGS] Unable to get feature variants: {e}")

        elif self.feature_flags and event != "$feature_flag_called":
            # Local evaluation is enabled, flags are loaded, so try and get all flags we can without going to the server
            feature_variants = self.get_all_flags(
                distinct_id, groups=(groups or {}), disable_geoip=disable_geoip, only_evaluate_locally=True
            )

        for feature, variant in (feature_variants or {}).items():
            extra_properties[f"$feature/{feature}"] = variant

        active_feature_flags = [key for (key, value) in (feature_variants or {}).items() if value is not False]
        if active_feature_flags:
            extra_properties["$active_feature_flags"] = active_feature_flags

        if extra_properties:
            msg["properties"] = {**extra_properties, **msg["properties"]}

        return self._enqueue(msg, disable_geoip)

    def set(self, distinct_id=None, properties=None, context=None, timestamp=None, uuid=None, disable_geoip=None):
        if context is not None:
            warnings.warn(
                "The 'context' parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )

        properties = properties or {}
        require("distinct_id", distinct_id, ID_TYPES)
        require("properties", properties, dict)

        msg = {
            "timestamp": timestamp,
            "distinct_id": distinct_id,
            "$set": properties,
            "event": "$set",
            "uuid": uuid,
        }

        return self._enqueue(msg, disable_geoip)

    def set_once(self, distinct_id=None, properties=None, context=None, timestamp=None, uuid=None, disable_geoip=None):
        if context is not None:
            warnings.warn(
                "The 'context' parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )

        properties = properties or {}
        require("distinct_id", distinct_id, ID_TYPES)
        require("properties", properties, dict)

        msg = {
            "timestamp": timestamp,
            "distinct_id": distinct_id,
            "$set_once": properties,
            "event": "$set_once",
            "uuid": uuid,
        }

        return self._enqueue(msg, disable_geoip)

    def group_identify(
        self,
        group_type=None,
        group_key=None,
        properties=None,
        context=None,
        timestamp=None,
        uuid=None,
        disable_geoip=None,
        distinct_id=None,
    ):
        if context is not None:
            warnings.warn(
                "The 'context' parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )
        properties = properties or {}
        require("group_type", group_type, ID_TYPES)
        require("group_key", group_key, ID_TYPES)
        require("properties", properties, dict)

        if distinct_id:
            require("distinct_id", distinct_id, ID_TYPES)
        else:
            distinct_id = "${}_{}".format(group_type, group_key)

        msg = {
            "event": "$groupidentify",
            "properties": {
                "$group_type": group_type,
                "$group_key": group_key,
                "$group_set": properties,
            },
            "distinct_id": distinct_id,
            "timestamp": timestamp,
            "uuid": uuid,
        }

        return self._enqueue(msg, disable_geoip)

    def alias(self, previous_id=None, distinct_id=None, context=None, timestamp=None, uuid=None, disable_geoip=None):
        if context is not None:
            warnings.warn(
                "The 'context' parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )

        require("previous_id", previous_id, ID_TYPES)
        require("distinct_id", distinct_id, ID_TYPES)

        msg = {
            "properties": {
                "distinct_id": previous_id,
                "alias": distinct_id,
            },
            "timestamp": timestamp,
            "event": "$create_alias",
            "distinct_id": previous_id,
        }

        return self._enqueue(msg, disable_geoip)

    def page(
        self, distinct_id=None, url=None, properties=None, context=None, timestamp=None, uuid=None, disable_geoip=None
    ):
        if context is not None:
            warnings.warn(
                "The 'context' parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )

        properties = properties or {}
        require("distinct_id", distinct_id, ID_TYPES)
        require("properties", properties, dict)

        require("url", url, string_types)
        properties["$current_url"] = url

        msg = {
            "event": "$pageview",
            "properties": properties,
            "timestamp": timestamp,
            "distinct_id": distinct_id,
            "uuid": uuid,
        }

        return self._enqueue(msg, disable_geoip)

    def capture_exception(
        self,
        exception=None,
        distinct_id=None,
        properties=None,
        context=None,
        timestamp=None,
        uuid=None,
        groups=None,
        **kwargs,
    ):
        if context is not None:
            warnings.warn(
                "The 'context' parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )

        # this function shouldn't ever throw an error, so it logs exceptions instead of raising them.
        # this is important to ensure we don't unexpectedly re-raise exceptions in the user's code.
        try:
            properties = properties or {}

            # if there's no distinct_id, we'll generate one and set personless mode
            # via $process_person_profile = false
            if distinct_id is None:
                properties["$process_person_profile"] = False
                distinct_id = uuid4()

            require("distinct_id", distinct_id, ID_TYPES)
            require("properties", properties, dict)

            if exception is not None:
                exc_info = exc_info_from_error(exception)
            else:
                exc_info = sys.exc_info()

            if exc_info is None or exc_info == (None, None, None):
                self.log.warning("No exception information available")
                return

            # Format stack trace for cymbal
            all_exceptions_with_trace = exceptions_from_error_tuple(exc_info)

            # Add in-app property to frames in the exceptions
            event = handle_in_app(
                {
                    "exception": {
                        "values": all_exceptions_with_trace,
                    },
                },
                project_root=self.project_root,
            )
            all_exceptions_with_trace_and_in_app = event["exception"]["values"]

            properties = {
                "$exception_type": all_exceptions_with_trace_and_in_app[0].get("type"),
                "$exception_message": all_exceptions_with_trace_and_in_app[0].get("value"),
                "$exception_list": all_exceptions_with_trace_and_in_app,
                "$exception_personURL": f"{remove_trailing_slash(self.raw_host)}/project/{self.api_key}/person/{distinct_id}",
                **properties,
            }

            if self.log_captured_exceptions:
                self.log.exception(exception, extra=kwargs)

            return self.capture(distinct_id, "$exception", properties, context, timestamp, uuid, groups)
        except Exception as e:
            self.log.exception(f"Failed to capture exception: {e}")

    def _enqueue(self, msg, disable_geoip):
        """Push a new `msg` onto the queue, return `(success, msg)`"""

        if self.disabled:
            return False, "disabled"

        timestamp = msg["timestamp"]
        if timestamp is None:
            timestamp = datetime.now(tz=tzutc())

        require("timestamp", timestamp, datetime)

        # add common
        timestamp = guess_timezone(timestamp)
        msg["timestamp"] = timestamp.isoformat()

        # only send if "uuid" is truthy
        if "uuid" in msg:
            uuid = msg.pop("uuid")
            if uuid:
                msg["uuid"] = stringify_id(uuid)

        if not msg.get("properties"):
            msg["properties"] = {}
        msg["properties"]["$lib"] = "posthog-python"
        msg["properties"]["$lib_version"] = VERSION

        if disable_geoip is None:
            disable_geoip = self.disable_geoip

        if disable_geoip:
            msg["properties"]["$geoip_disable"] = True

        if self.super_properties:
            msg["properties"] = {**msg["properties"], **self.super_properties}

        msg["distinct_id"] = stringify_id(msg.get("distinct_id", None))

        msg = clean(msg)
        self.log.debug("queueing: %s", msg)

        # if send is False, return msg as if it was successfully queued
        if not self.send:
            return True, msg

        if self.sync_mode:
            self.log.debug("enqueued with blocking %s.", msg["event"])
            batch_post(
                self.api_key,
                self.host,
                gzip=self.gzip,
                timeout=self.timeout,
                batch=[msg],
                historical_migration=self.historical_migration,
            )

            return True, msg

        try:
            self.queue.put(msg, block=False)
            self.log.debug("enqueued %s.", msg["event"])
            return True, msg
        except queue.Full:
            self.log.warning("analytics-python queue is full")
            return False, msg

    def flush(self):
        """Forces a flush from the internal queue to the server"""
        queue = self.queue
        size = queue.qsize()
        queue.join()
        # Note that this message may not be precise, because of threading.
        self.log.debug("successfully flushed about %s items.", size)

    def join(self):
        """Ends the consumer thread once the queue is empty.
        Blocks execution until finished
        """
        for consumer in self.consumers:
            consumer.pause()
            try:
                consumer.join()
            except RuntimeError:
                # consumer thread has not started
                pass

        if self.poller:
            self.poller.stop()

    def shutdown(self):
        """Flush all messages and cleanly shutdown the client"""
        self.flush()
        self.join()

        if self.exception_capture:
            self.exception_capture.close()

    def _load_feature_flags(self):
        try:
            response = get(
                self.personal_api_key,
                f"/api/feature_flag/local_evaluation/?token={self.api_key}&send_cohorts",
                self.host,
                timeout=10,
            )

            self.feature_flags = response["flags"] or []
            self.group_type_mapping = response["group_type_mapping"] or {}
            self.cohorts = response["cohorts"] or {}

        except APIError as e:
            if e.status == 401:
                self.log.error(
                    "[FEATURE FLAGS] Error loading feature flags: To use feature flags, please set a valid personal_api_key. More information: https://posthog.com/docs/api/overview"
                )
                if self.debug:
                    raise APIError(
                        status=401,
                        message="You are using a write-only key with feature flags. "
                        "To use feature flags, please set a personal_api_key "
                        "More information: https://posthog.com/docs/api/overview",
                    )
            elif e.status == 402:
                self.log.warning(
                    "[FEATURE FLAGS] PostHog feature flags quota limited, resetting feature flag data.  Learn more about billing limits at https://posthog.com/docs/billing/limits-alerts"
                )
                # Reset all feature flag data when quota limited
                self.feature_flags = []
                self.group_type_mapping = {}
                self.cohorts = {}

                if self.debug:
                    raise APIError(
                        status=402,
                        message="PostHog feature flags quota limited",
                    )
            else:
                self.log.error(f"[FEATURE FLAGS] Error loading feature flags: {e}")
        except Exception as e:
            self.log.warning(
                "[FEATURE FLAGS] Fetching feature flags failed with following error. We will retry in %s seconds."
                % self.poll_interval
            )
            self.log.warning(e)

        self._last_feature_flag_poll = datetime.now(tz=tzutc())

    def load_feature_flags(self):
        if not self.personal_api_key:
            self.log.warning("[FEATURE FLAGS] You have to specify a personal_api_key to use feature flags.")
            self.feature_flags = []
            return

        self._load_feature_flags()
        if not (self.poller and self.poller.is_alive()):
            self.poller = Poller(interval=timedelta(seconds=self.poll_interval), execute=self._load_feature_flags)
            self.poller.start()

    def _compute_flag_locally(
        self,
        feature_flag,
        distinct_id,
        *,
        groups={},
        person_properties={},
        group_properties={},
        warn_on_unknown_groups=True,
    ) -> FlagValue:
        if feature_flag.get("ensure_experience_continuity", False):
            raise InconclusiveMatchError("Flag has experience continuity enabled")

        if not feature_flag.get("active"):
            return False

        flag_filters = feature_flag.get("filters") or {}
        aggregation_group_type_index = flag_filters.get("aggregation_group_type_index")
        if aggregation_group_type_index is not None:
            group_name = self.group_type_mapping.get(str(aggregation_group_type_index))

            if not group_name:
                self.log.warning(
                    f"[FEATURE FLAGS] Unknown group type index {aggregation_group_type_index} for feature flag {feature_flag['key']}"
                )
                # failover to `/decide/`
                raise InconclusiveMatchError("Flag has unknown group type index")

            if group_name not in groups:
                # Group flags are never enabled in `groups` aren't passed in
                # don't failover to `/decide/`, since response will be the same
                if warn_on_unknown_groups:
                    self.log.warning(
                        f"[FEATURE FLAGS] Can't compute group feature flag: {feature_flag['key']} without group names passed in"
                    )
                else:
                    self.log.debug(
                        f"[FEATURE FLAGS] Can't compute group feature flag: {feature_flag['key']} without group names passed in"
                    )
                return False

            focused_group_properties = group_properties[group_name]
            return match_feature_flag_properties(feature_flag, groups[group_name], focused_group_properties)
        else:
            return match_feature_flag_properties(feature_flag, distinct_id, person_properties, self.cohorts)

    def feature_enabled(
        self,
        key,
        distinct_id,
        *,
        groups={},
        person_properties={},
        group_properties={},
        only_evaluate_locally=False,
        send_feature_flag_events=True,
        disable_geoip=None,
    ):
        response = self.get_feature_flag(
            key,
            distinct_id,
            groups=groups,
            person_properties=person_properties,
            group_properties=group_properties,
            only_evaluate_locally=only_evaluate_locally,
            send_feature_flag_events=send_feature_flag_events,
            disable_geoip=disable_geoip,
        )

        if response is None:
            return None
        return bool(response)

    def get_feature_flag(
        self,
        key,
        distinct_id,
        *,
        groups={},
        person_properties={},
        group_properties={},
        only_evaluate_locally=False,
        send_feature_flag_events=True,
        disable_geoip=None,
    ) -> Optional[FlagValue]:
        """
        Get a feature flag value for a key by evaluating locally or remotely
        depending on whether local evaluation is enabled and the flag can be
        locally evaluated.

        This also captures the $feature_flag_called event unless send_feature_flag_events is False.
        """
        require("key", key, string_types)
        require("distinct_id", distinct_id, ID_TYPES)
        require("groups", groups, dict)

        if self.disabled:
            return None

        person_properties, group_properties = self._add_local_person_and_group_properties(
            distinct_id, groups, person_properties, group_properties
        )

        response = self._locally_evaluate_flag(key, distinct_id, groups, person_properties, group_properties)

        flag_details = None
        request_id = None

        flag_was_locally_evaluated = response is not None
        if not flag_was_locally_evaluated and not only_evaluate_locally:
            try:
                flag_details, request_id = self._get_feature_flag_details_from_decide(
                    key, distinct_id, groups, person_properties, group_properties, disable_geoip
                )
                response = flag_details.get_value() if flag_details else False
                self.log.debug(f"Successfully computed flag remotely: #{key} -> #{response}")
            except Exception as e:
                self.log.exception(f"[FEATURE FLAGS] Unable to get flag remotely: {e}")

        if send_feature_flag_events:
            self._capture_feature_flag_called(
                distinct_id,
                key,
                response or False,
                None,
                flag_was_locally_evaluated,
                groups,
                disable_geoip,
                request_id,
                flag_details,
            )

        return response

    def _locally_evaluate_flag(
        self,
        key: str,
        distinct_id: str,
        groups: dict[str, str],
        person_properties: dict[str, str],
        group_properties: dict[str, str],
    ) -> Optional[FlagValue]:
        if self.feature_flags is None and self.personal_api_key:
            self.load_feature_flags()
        response = None

        if self.feature_flags:
            assert (
                self.feature_flags_by_key is not None
            ), "feature_flags_by_key should be initialized when feature_flags is set"
            # Local evaluation
            flag = self.feature_flags_by_key.get(key)
            if flag:
                try:
                    response = self._compute_flag_locally(
                        flag,
                        distinct_id,
                        groups=groups,
                        person_properties=person_properties,
                        group_properties=group_properties,
                    )
                    self.log.debug(f"Successfully computed flag locally: {key} -> {response}")
                except InconclusiveMatchError as e:
                    self.log.debug(f"Failed to compute flag {key} locally: {e}")
                except Exception as e:
                    self.log.exception(f"[FEATURE FLAGS] Error while computing variant locally: {e}")
        return response

    def get_feature_flag_payload(
        self,
        key,
        distinct_id,
        *,
        match_value=None,
        groups={},
        person_properties={},
        group_properties={},
        only_evaluate_locally=False,
        send_feature_flag_events=True,
        disable_geoip=None,
    ):
        if self.disabled:
            return None

        if match_value is None:
            person_properties, group_properties = self._add_local_person_and_group_properties(
                distinct_id, groups, person_properties, group_properties
            )
            match_value = self._locally_evaluate_flag(key, distinct_id, groups, person_properties, group_properties)

        response = None
        payload = None
        flag_details = None
        request_id = None

        if match_value is not None:
            payload = self._compute_payload_locally(key, match_value)

        flag_was_locally_evaluated = payload is not None
        if not flag_was_locally_evaluated and not only_evaluate_locally:
            try:
                flag_details, request_id = self._get_feature_flag_details_from_decide(
                    key, distinct_id, groups, person_properties, group_properties, disable_geoip
                )
                payload = flag_details.metadata.payload if flag_details else None
                response = flag_details.get_value() if flag_details else False
            except Exception as e:
                self.log.exception(f"[FEATURE FLAGS] Unable to get feature flags and payloads: {e}")

        if send_feature_flag_events:
            self._capture_feature_flag_called(
                distinct_id,
                key,
                response or False,
                payload,
                flag_was_locally_evaluated,
                groups,
                disable_geoip,
                request_id,
                flag_details,
            )

        return payload

    def _get_feature_flag_details_from_decide(
        self,
        key: str,
        distinct_id: str,
        groups: dict[str, str],
        person_properties: dict[str, str],
        group_properties: dict[str, str],
        disable_geoip: Optional[bool],
    ) -> tuple[Optional[FeatureFlag], Optional[str]]:
        """
        Calls /decide and returns the flag details and request id
        """
        resp_data = self.get_flags_decision(distinct_id, groups, person_properties, group_properties, disable_geoip)
        request_id = resp_data.get("requestId")
        flags = resp_data.get("flags")
        flag_details = flags.get(key) if flags else None
        return flag_details, request_id

    def _capture_feature_flag_called(
        self,
        distinct_id: str,
        key: str,
        response: FlagValue,
        payload: Optional[str],
        flag_was_locally_evaluated: bool,
        groups: dict[str, str],
        disable_geoip: Optional[bool],
        request_id: Optional[str],
        flag_details: Optional[FeatureFlag],
    ):
        feature_flag_reported_key = f"{key}_{str(response)}"

        if feature_flag_reported_key not in self.distinct_ids_feature_flags_reported[distinct_id]:
            properties: dict[str, Any] = {
                "$feature_flag": key,
                "$feature_flag_response": response,
                "locally_evaluated": flag_was_locally_evaluated,
                f"$feature/{key}": response,
            }

            if payload:
                properties["$feature_flag_payload"] = payload

            if request_id:
                properties["$feature_flag_request_id"] = request_id
            if isinstance(flag_details, FeatureFlag):
                if flag_details.reason and flag_details.reason.description:
                    properties["$feature_flag_reason"] = flag_details.reason.description
                if isinstance(flag_details.metadata, FlagMetadata):
                    if flag_details.metadata.version:
                        properties["$feature_flag_version"] = flag_details.metadata.version
                    if flag_details.metadata.id:
                        properties["$feature_flag_id"] = flag_details.metadata.id

            self.capture(
                distinct_id,
                "$feature_flag_called",
                properties,
                groups=groups,
                disable_geoip=disable_geoip,
            )
            self.distinct_ids_feature_flags_reported[distinct_id].add(feature_flag_reported_key)

    def get_remote_config_payload(self, key: str):
        if self.disabled:
            return None

        if self.personal_api_key is None:
            self.log.warning(
                "[FEATURE FLAGS] You have to specify a personal_api_key to fetch decrypted feature flag payloads."
            )
            return None

        try:
            return remote_config(
                self.personal_api_key,
                self.host,
                key,
                timeout=self.feature_flags_request_timeout_seconds,
            )
        except Exception as e:
            self.log.exception(f"[FEATURE FLAGS] Unable to get decrypted feature flag payload: {e}")

    def _compute_payload_locally(self, key: str, match_value: FlagValue) -> Optional[str]:
        payload = None

        if self.feature_flags_by_key is None:
            return payload

        flag_definition = self.feature_flags_by_key.get(key)
        if flag_definition:
            flag_filters = flag_definition.get("filters") or {}
            flag_payloads = flag_filters.get("payloads") or {}
            # For boolean flags, convert True to "true"
            # For multivariate flags, use the variant string as-is
            lookup_value = "true" if isinstance(match_value, bool) and match_value else str(match_value)
            payload = flag_payloads.get(lookup_value, None)
        return payload

    def get_all_flags(
        self,
        distinct_id,
        *,
        groups={},
        person_properties={},
        group_properties={},
        only_evaluate_locally=False,
        disable_geoip=None,
    ) -> Optional[dict[str, Union[bool, str]]]:
        response = self.get_all_flags_and_payloads(
            distinct_id,
            groups=groups,
            person_properties=person_properties,
            group_properties=group_properties,
            only_evaluate_locally=only_evaluate_locally,
            disable_geoip=disable_geoip,
        )

        return response["featureFlags"]

    def get_all_flags_and_payloads(
        self,
        distinct_id,
        *,
        groups={},
        person_properties={},
        group_properties={},
        only_evaluate_locally=False,
        disable_geoip=None,
    ) -> FlagsAndPayloads:
        if self.disabled:
            return {"featureFlags": None, "featureFlagPayloads": None}

        person_properties, group_properties = self._add_local_person_and_group_properties(
            distinct_id, groups, person_properties, group_properties
        )

        response, fallback_to_decide = self._get_all_flags_and_payloads_locally(
            distinct_id, groups=groups, person_properties=person_properties, group_properties=group_properties
        )

        if fallback_to_decide and not only_evaluate_locally:
            try:
                decide_response = self.get_flags_decision(
                    distinct_id,
                    groups=groups,
                    person_properties=person_properties,
                    group_properties=group_properties,
                    disable_geoip=disable_geoip,
                )
                return to_flags_and_payloads(decide_response)
            except Exception as e:
                self.log.exception(f"[FEATURE FLAGS] Unable to get feature flags and payloads: {e}")

        return response

    def _get_all_flags_and_payloads_locally(
        self, distinct_id, *, groups={}, person_properties={}, group_properties={}, warn_on_unknown_groups=False
    ) -> tuple[FlagsAndPayloads, bool]:
        require("distinct_id", distinct_id, ID_TYPES)
        require("groups", groups, dict)

        if self.feature_flags is None and self.personal_api_key:
            self.load_feature_flags()

        flags: dict[str, FlagValue] = {}
        payloads: dict[str, str] = {}
        fallback_to_decide = False
        # If loading in previous line failed
        if self.feature_flags:
            for flag in self.feature_flags:
                try:
                    flags[flag["key"]] = self._compute_flag_locally(
                        flag,
                        distinct_id,
                        groups=groups,
                        person_properties=person_properties,
                        group_properties=group_properties,
                        warn_on_unknown_groups=warn_on_unknown_groups,
                    )
                    matched_payload = self._compute_payload_locally(flag["key"], flags[flag["key"]])
                    if matched_payload:
                        payloads[flag["key"]] = matched_payload
                except InconclusiveMatchError:
                    # No need to log this, since it's just telling us to fall back to `/decide`
                    fallback_to_decide = True
                except Exception as e:
                    self.log.exception(f"[FEATURE FLAGS] Error while computing variant and payload: {e}")
                    fallback_to_decide = True
        else:
            fallback_to_decide = True

        return {"featureFlags": flags, "featureFlagPayloads": payloads}, fallback_to_decide

    def feature_flag_definitions(self):
        return self.feature_flags

    def _add_local_person_and_group_properties(self, distinct_id, groups, person_properties, group_properties):
        all_person_properties = {"distinct_id": distinct_id, **(person_properties or {})}

        all_group_properties = {}
        if groups:
            for group_name in groups:
                all_group_properties[group_name] = {
                    "$group_key": groups[group_name],
                    **(group_properties.get(group_name) or {}),
                }

        return all_person_properties, all_group_properties


def require(name, field, data_type):
    """Require that the named `field` has the right `data_type`"""
    if not isinstance(field, data_type):
        msg = "{0} must have {1}, got: {2}".format(name, data_type, field)
        raise AssertionError(msg)


def stringify_id(val):
    if val is None:
        return None
    if isinstance(val, string_types):
        return val
    return str(val)
