from datetime import datetime

import requests

from tradingagents.dataflows.news.google_news_rss import get_news_data_via_rss
from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def _normalize_input_date(value: str) -> str:
    if "-" in value:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    return datetime.strptime(value, "%m/%d/%Y").strftime("%Y-%m-%d")


def getNewsData(query, start_date, end_date):
    """
    通过 Google News RSS 搜索获取新闻结果。

    说明：
    - 旧的 DOM 抓取方式对港股等中文财经查询命中率很差，且容易受页面结构影响失效。
    - 当前主链路统一切换到 RSS 搜索结果，以提高稳定性和可维护性。
    """
    normalized_start = _normalize_input_date(start_date)
    normalized_end = _normalize_input_date(end_date)

    try:
        return get_news_data_via_rss(query, normalized_start, normalized_end)
    except requests.exceptions.Timeout as e:
        logger.error(f"[Google新闻RSS] 连接超时: {e}")
        return []
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[Google新闻RSS] 连接错误: {e}")
        return []
    except Exception as e:
        logger.error(f"[Google新闻RSS] 获取Google新闻失败: {e}")
        return []
