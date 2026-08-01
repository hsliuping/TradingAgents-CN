"""Normalize real-time quote synchronization statistics for API responses."""

from typing import Any, Dict, List


def normalize_realtime_sync_result(
    symbols: List[str], sync_result: Dict[str, Any] | None
) -> Dict[str, Any]:
    """Ensure every requested symbol is represented by success or failure."""
    result = dict(sync_result or {})
    success_count = min(max(int(result.get("success_count", 0) or 0), 0), len(symbols))
    reported_errors = max(int(result.get("error_count", 0) or 0), 0)
    error_count = max(reported_errors, len(symbols) - success_count)
    error_count = min(error_count, len(symbols) - success_count)

    errors = list(result.get("errors") or [])
    if error_count and not errors:
        errors.append({
            "error": "未获取到实时行情数据",
            "context": "sync_realtime_quotes",
        })

    result.update({
        "total_processed": len(symbols),
        "success_count": success_count,
        "error_count": error_count,
        "errors": errors,
    })
    return result
