import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def _normalize_date(date_value: str) -> str:
    if not date_value:
        return ""

    raw = date_value.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return raw


def _strip_html(value: str) -> str:
    if not value:
        return ""
    return BeautifulSoup(html.unescape(value), "html.parser").get_text(" ", strip=True)


def build_google_news_rss_url(
    query: str,
    start_date: str,
    end_date: str,
    hl: str = "zh-CN",
    gl: str = "CN",
    ceid: str = "CN:zh-Hans",
) -> str:
    search_query = f"{query} after:{start_date} before:{end_date}"
    encoded_query = urllib.parse.quote(search_query)
    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}&hl={hl}&gl={gl}&ceid={urllib.parse.quote(ceid)}"
    )


def parse_google_news_rss(xml_text: str) -> List[Dict]:
    root = ET.fromstring(xml_text)
    items = []

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = _normalize_date(item.findtext("pubDate") or "")
        source = (item.findtext("source") or "").strip()
        description = _strip_html(item.findtext("description") or "")

        if not source and title:
            parts = re.split(r"\s[-|｜]\s", title)
            if len(parts) >= 2:
                source = parts[-1].strip()

        items.append(
            {
                "link": link,
                "title": title,
                "snippet": description,
                "date": pub_date,
                "source": source,
            }
        )

    return items


def get_news_data_via_rss(
    query: str,
    start_date: str,
    end_date: str,
    max_items: int = 50,
    timeout: int = 20,
) -> List[Dict]:
    url = build_google_news_rss_url(query, start_date, end_date)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
    }

    logger.info(f"[Google新闻RSS] 开始获取新闻，查询: {query}, 时间范围: {start_date} 至 {end_date}")
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    items = parse_google_news_rss(response.text)
    if max_items > 0:
        items = items[:max_items]

    logger.info(f"[Google新闻RSS] 成功获取 {len(items)} 条新闻，查询: {query}")
    return items
