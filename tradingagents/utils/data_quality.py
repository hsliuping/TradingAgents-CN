"""Data quality checks for analyst reports.

Detects when data tools return error messages instead of real data,
preventing LLMs from fabricating analysis on empty/failed data sources.
"""


# Markers that indicate a tool failure, not real analysis content
ERROR_MARKERS = [
    "获取失败",
    "❌",
    "数据获取失败",
    "工具调用失败",
    "统一工具不可用",
    "工具执行失败",
    "所有数据源均失败",
    "无法获取数据",
]


def check_report_data(data: str, ticker: str, analyst_type: str) -> dict:
    """Check whether data from a tool contains error markers instead of real data.

    Args:
        data: Raw string returned by the data tool.
        ticker: Stock ticker for context.
        analyst_type: Analyst type name (e.g. "基本面分析", "市场分析").

    Returns:
        {"has_failure": bool, "error_message": str}
    """
    if not data or not data.strip():
        return {
            "has_failure": True,
            "error_message": f"{analyst_type} 返回数据为空",
        }

    # Count how many distinct error markers appear in the data
    found_markers = [m for m in ERROR_MARKERS if m in data]

    # 2+ distinct error markers => the data is clearly an error report, not real data
    if len(found_markers) >= 2:
        return {
            "has_failure": True,
            "error_message": (
                f"{analyst_type} 数据获取失败（检测到多个错误标记: "
                f"{', '.join(found_markers[:3])}）"
            ),
        }

    # Single "获取失败" in a section header is OK if the rest is real data;
    # but if the entire string is dominated by error text, flag it.
    if len(found_markers) == 1:
        error_ratio = sum(
            len(line) for line in data.splitlines() if any(m in line for m in ERROR_MARKERS)
        ) / max(len(data), 1)
        if error_ratio > 0.6:
            return {
                "has_failure": True,
                "error_message": f"{analyst_type} 数据大部分为错误信息",
            }

    return {"has_failure": False, "error_message": ""}


def is_data_critical_failure(data_failures: dict, total_analysts: int = 2) -> bool:
    """Check whether enough critical data sources have failed to warrant stopping.

    Args:
        data_failures: Dict of {analyst_type: check_report_data result}.
        total_analysts: Minimum number of distinct analyst types that must fail
                       to consider the overall analysis as a critical failure.

    Returns:
        True if analysis should be terminated.
    """
    return len(data_failures) >= total_analysts
