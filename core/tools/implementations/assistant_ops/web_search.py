"""Web 搜索工具 - 基于 SearXNG 元搜索引擎，支持百度/Bing 爬虫备选。"""

import logging
import os
import random
from typing import Annotated, Optional
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # SearXNG 需要更长时间

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# SearXNG 只使用国内可访问的引擎
SEARXNG_ENGINES = "baidu,360so,sogou,bing"

# 财经网站域名优先级（分数越高越优先）
FINANCE_DOMAINS = {
    # 官方网站（最高优先级）
    "seres.cn": 100,
    "byd.com": 100,
    # 巨潮资讯（官方公告平台）
    "cninfo.com.cn": 95,
    # 主流财经媒体
    "eastmoney.com": 90,
    "finance.sina.com.cn": 85,
    "10jqka.com.cn": 85,
    "stcn.com": 80,
    "cs.com.cn": 80,
    "cnstock.com": 80,
    "money.163.com": 75,
    "163.com": 70,
    "finance.qq.com": 75,
    "finance.ifeng.com": 75,
    "hexun.com": 70,
    "finance.people.com.cn": 70,
    # 乘联会/汽车工业协会（销量数据权威来源）
    "cpcaauto.com": 95,
    "caam.org.cn": 95,
}

# 全局 Session
_baidu_session: Optional[requests.Session] = None


def _get_domain_score(url: str) -> int:
    """根据 URL 域名返回财经优先级分数。"""
    try:
        domain = urlparse(url).netloc.lower()
        for fin_domain, score in FINANCE_DOMAINS.items():
            if fin_domain in domain:
                return score
    except Exception:
        pass
    return 0


def _sort_by_finance_priority(results: list[dict]) -> list[dict]:
    """按财经网站优先级排序搜索结果。"""
    return sorted(results, key=lambda r: _get_domain_score(r.get("url", "")), reverse=True)


def _search_searxng(
    instance_url: str, query: str, language: str, max_results: int
) -> list[dict]:
    """通过 SearXNG 实例搜索（只使用国内引擎）。"""
    params = {
        "q": query,
        "format": "json",
        "language": language,
        "safesearch": 0,
        "categories": "general",
        "engines": SEARXNG_ENGINES,
        "timeout": 5,
    }
    full_url = f"{instance_url.rstrip('/')}/search?{urlencode(params)}"
    resp = requests.get(
        full_url,
        headers={
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in (data.get("results") or [])[:max_results * 2]:  # 多取一些用于排序
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "engine": item.get("engine", "searxng"),
                "published_date": item.get("publishedDate", ""),
            }
        )

    # 按财经网站优先级排序
    results = _sort_by_finance_priority(results)
    return results[:max_results]


def _get_baidu_session() -> requests.Session:
    """获取百度搜索 Session。"""
    global _baidu_session
    if _baidu_session is None or not _baidu_session.cookies:
        _baidu_session = requests.Session()
        _baidu_session.headers.update(
            {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.baidu.com/",
            }
        )
        try:
            _baidu_session.get("https://www.baidu.com/", timeout=DEFAULT_TIMEOUT)
        except Exception:
            pass
    return _baidu_session


def _search_baidu(query: str, max_results: int) -> list[dict]:
    """通过百度搜索爬取结果。"""
    session = _get_baidu_session()
    resp = session.get(
        "https://www.baidu.com/s",
        params={"wd": query, "rn": max_results, "ie": "utf-8"},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "baidu.com/link" not in href and "baidu.php" not in href:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        snippet = ""
        h3 = a.find_parent("h3")
        container = h3.parent.parent if h3 and h3.parent else a.parent
        if container:
            for el in container.find_all(["span", "div", "p"]):
                text = el.get_text(strip=True)
                if len(text) > 30 and text != title and title not in text:
                    snippet = text[:300]
                    break
        results.append({"title": title, "url": href, "content": snippet, "engine": "baidu"})
        if len(results) >= max_results:
            break
    return results


def _format_results(query: str, results: list[dict], engine_used: str) -> str:
    """将搜索结果格式化为 LLM 友好的文本。"""
    if not results:
        return f"未找到与「{query}」相关的搜索结果。"

    lines = [
        f"Web 搜索结果：{query}",
        f"搜索引擎：{engine_used}",
        f"共 {len(results)} 条结果\n",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"--- 结果 {i} ---")
        lines.append(f"标题：{r['title']}")
        if r.get("published_date"):
            lines.append(f"发布日期：{r['published_date']}")
        lines.append(f"链接：{r['url']}")
        if r["content"]:
            lines.append(f"摘要：{r['content'][:300]}")
        lines.append("")
    return "\n".join(lines)


def run_web_search(
    query: str,
    language: str = "zh",
    max_results: int = 10,
) -> str:
    """执行 Web 搜索。"""
    query_clean = (query or "").strip()
    if not query_clean:
        return "请提供搜索关键词。"

    errors = []

    # 1) SearXNG（优先，只使用国内引擎）
    searxng_instances = os.getenv("SEARXNG_INSTANCES", "").strip()
    if searxng_instances:
        for instance_url in searxng_instances.split(","):
            instance_url = instance_url.strip()
            if not instance_url:
                continue
            try:
                logger.info("SearXNG 搜索: %s | query=%s", instance_url, query_clean)
                results = _search_searxng(instance_url, query_clean, language, max_results)
                if results:
                    return _format_results(query_clean, results, f"SearXNG({instance_url})")
            except Exception as exc:
                logger.warning("SearXNG %s 失败: %s", instance_url, exc)
                errors.append(f"searxng: {exc}")

    # 2) 百度搜索（备选）
    try:
        logger.info("百度搜索: query=%s", query_clean)
        results = _search_baidu(query_clean, max_results)
        if results:
            return _format_results(query_clean, results, "百度")
    except Exception as exc:
        logger.warning("百度搜索失败: %s", exc)
        errors.append(f"baidu: {exc}")

    return f"Web 搜索失败，所有搜索引擎均不可用。错误详情：{'; '.join(errors)}"


@tool
@register_tool(
    tool_id="web_search",
    name="Web 搜索",
    description="通过 SearXNG 元搜索引擎搜索互联网信息（百度/360/搜狗/Bing中国版引擎聚合）。自动优先返回财经类网站的结果（东方财富、新浪财经、巨潮资讯等）。适合获取财报中没有的实时数据，如月度销量、最新公告、行业新闻等。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    data_source_handling="local_only",
    capability_tags=[
        "web_search", "internet_search", "online_search", "information_search",
        "real_time_info", "current_events", "news_query", "fact_check",
        "market_information", "search_engine", "finance_data",
    ],
    tool_role_hint="specialized",
    output_shape="report",
    preferred_for=[
        "搜索互联网实时信息",
        "获取财报外的经营数据（如月销量）",
        "查询最新新闻和公告",
        "事实核查和背景调研",
    ],
    when_to_use="当需要搜索互联网获取最新信息时使用，特别是财报中没有覆盖的实时数据（月度销量、行业动态、最新新闻等）。",
    returns="返回结构化搜索结果，包含标题、链接、摘要。自动优先财经类网站，聚合百度/360/搜狗/Bing中国版引擎结果。",
)
def web_search(
    query: Annotated[str, "搜索关键词，例如：赛力斯 2025年7月 销量，或 比亚迪 最新月销量"],
    max_results: Annotated[int, "最大返回结果数量，默认 10"] = 10,
) -> str:
    """搜索互联网信息，聚合多个搜索引擎的结果，优先财经类网站。"""
    return run_web_search(query=query, max_results=max_results)
