"""Test the update check API for stable, test, and legacy client flows."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, Optional


DEFAULT_BASE_URL = "https://www.tradingagentscn.com/api/app/check-update"
DEFAULT_VERSION = "1.0.0"
DEFAULT_PLATFORM = "win"
DEFAULT_TIMEOUT = 15
DEFAULT_USER_AGENT = "TradingAgentsCN/1.0.0"
REQUIRED_DATA_FIELDS = {
    "has_update",
    "version",
    "package_type",
    "download_url",
    "file_size",
    "sha256",
    "release_notes",
    "release_date",
    "is_mandatory",
    "min_version",
}


def build_url(
    base_url: str,
    version: str,
    platform: str,
    channel: Optional[str],
    build_type: Optional[str],
) -> str:
    params: Dict[str, str] = {
        "version": version,
        "platform": platform,
    }
    if build_type:
        params["build_type"] = build_type
    if channel:
        params["channel"] = channel
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def fetch_json(url: str, user_agent: str, timeout: int) -> Dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read().decode("utf-8", errors="replace")
        payload = json.loads(body)
        return {
            "status": response.status,
            "content_type": content_type,
            "body": body,
            "json": payload,
        }


def validate_payload(payload: Dict[str, object]) -> Iterable[str]:
    issues = []

    if payload.get("success") is not True:
        issues.append("success is not true")

    data = payload.get("data")
    if not isinstance(data, dict):
        issues.append("data is missing or not an object")
        return issues

    missing_fields = sorted(REQUIRED_DATA_FIELDS - set(data.keys()))
    if missing_fields:
        issues.append("missing data fields: " + ", ".join(missing_fields))

    has_update = data.get("has_update")
    if not isinstance(has_update, bool):
        issues.append("data.has_update is not a boolean")
        return issues

    if has_update:
        package_type = data.get("package_type")
        if package_type not in {"installer", "update"}:
            issues.append("data.package_type must be installer or update")

        version = data.get("version")
        if not isinstance(version, str) or not version.strip():
            issues.append("data.version is empty while has_update=true")

        download_url = data.get("download_url")
        if not isinstance(download_url, str) or not download_url.strip():
            issues.append("data.download_url is empty while has_update=true")
        else:
            parsed_url = urllib.parse.urlparse(download_url)
            if parsed_url.scheme not in {"http", "https"}:
                issues.append("data.download_url must be an absolute http/https URL")

        file_size = data.get("file_size")
        if not isinstance(file_size, int) or file_size < 0:
            issues.append("data.file_size must be a non-negative integer")

    return issues


def run_case(name: str, url: str, user_agent: str, timeout: int) -> int:
    print(f"\n=== {name} ===")
    print(f"URL: {url}")

    try:
        result = fetch_json(url, user_agent=user_agent, timeout=timeout)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP Error: {exc.code}")
        if error_body:
            print("Response Body:")
            print(error_body)
        return 1
    except urllib.error.URLError as exc:
        print(f"Request failed: {exc}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON response: {exc}")
        return 1

    payload = result["json"]
    assert isinstance(payload, dict)

    print(f"HTTP Status: {result['status']}")
    print(f"Content-Type: {result['content_type']}")

    issues = list(validate_payload(payload))
    if issues:
        print("Validation: FAILED")
        for issue in issues:
            print(f"- {issue}")
        print("Response JSON:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    print("Validation: OK")
    print("Response JSON:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test update check API endpoints.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Update check endpoint URL")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Client version to send")
    parser.add_argument("--platform", default=DEFAULT_PLATFORM, help="Platform query parameter")
    parser.add_argument("--build-type", default="", help="Optional build_type query parameter")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds")
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header to send",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    build_type = args.build_type or None
    cases = [
        (
            "stable channel",
            build_url(args.base_url, args.version, args.platform, "stable", build_type),
        ),
        (
            "test channel",
            build_url(args.base_url, args.version, args.platform, "test", build_type),
        ),
        (
            "legacy client (no channel)",
            build_url(args.base_url, args.version, args.platform, None, build_type),
        ),
    ]

    exit_code = 0
    for name, url in cases:
        case_code = run_case(name, url, user_agent=args.user_agent, timeout=args.timeout)
        exit_code = max(exit_code, case_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())