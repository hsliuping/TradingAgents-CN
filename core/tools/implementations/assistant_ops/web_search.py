"""Web 搜索工具 - 基于 SearXNG 元搜索引擎，支持百度/Bing 爬虫备选。"""

import logging
import os
import random
import re
import time
from typing import Annotated, Optional
from urllib.parse import quote, unquote, urlencode, urlparse

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

# SearXNG 引擎轮换顺序（质量优先）。
# 注意：不放 bing——Bing 中国版对长中文查询会降级成单字匹配，
# 返回"赛"字字典页等无关结果，过滤它们反而浪费上下文 token。
SEARXNG_ENGINE_ORDER = ["baidu", "sogou", "360so"]

# 引擎熔断状态：引擎名 -> 冷却截止时间戳。
# 引擎连续被查询会触发反爬 CAPTCHA 被 SearXNG 挂起（实测 LLM 一轮对话
# 搜 8 次即触发），挂起后该引擎返回 0 结果。这里在客户端配合熔断：
# 某引擎无有效结果后 5 分钟内不再首选它，自动轮换到下一引擎。
_engine_cooldown: dict = {}

# 两次 SearXNG 请求的最小间隔（秒），降低触发反爬的概率
_SEARXNG_MIN_INTERVAL = 1.2
_last_searxng_ts = 0.0

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


def _query_key_terms(query: str) -> list:
    """提取查询中的核心词（去掉年份/数字/量词/单字，用于关联性过滤）。

    例："赛力斯 2026年6月 产销快报 销量 辆" -> ["赛力斯", "产销快报", "销量"]
    """
    tokens = re.split(r"[\s,，、/·\"']+", query.strip())
    terms = []
    for tok in tokens:
        # 去掉纯数字、年份月份、百分数、常见量词
        cleaned = re.sub(r"^\d{4}年?\d{0,2}月?\d{0,2}日?$|^\d+%?$|^\d+$", "", tok)
        if len(cleaned) >= 2:
            terms.append(cleaned)
    return terms


def _filter_irrelevant_results(query: str, results: list) -> list:
    """过滤与查询零关联的垃圾结果。

    背景：Bing 中国版对长中文查询会降级成单字匹配，返回"赛"字字典、
    汉典等无关页面，污染 LLM 上下文。过滤规则：结果标题（含解码后 URL）
    至少包含一个核心词，否则丢弃。
    """
    terms = _query_key_terms(query)
    if not terms:
        return results  # 无法提取核心词（如纯代码查询），不过滤

    kept = []
    for r in results:
        text = (r.get("title", "") or "") + " " + unquote(r.get("url", "") or "")
        if any(t in text for t in terms):
            kept.append(r)
    dropped = len(results) - len(kept)
    if dropped:
        logger.info("垃圾结果过滤: 丢弃 %d 条与查询零关联的结果", dropped)
    return kept


def _search_searxng(
    instance_url: str, query: str, language: str, max_results: int
) -> list:
    """通过 SearXNG 实例搜索（引擎轮换 + 熔断 + 关联性过滤）。

    不再一次并发打满所有引擎（会同时触发多个引擎的反爬 CAPTCHA），
    而是按质量顺序逐个尝试：某引擎返回有效结果即停止；
    无有效结果的引擎进入 5 分钟冷却，后续搜索自动轮换。
    """
    global _last_searxng_ts

    # 全局限速：两次 SearXNG 请求至少间隔 _SEARXNG_MIN_INTERVAL 秒
    wait = _SEARXNG_MIN_INTERVAL - (time.time() - _last_searxng_ts)
    if wait > 0:
        time.sleep(wait)
    _last_searxng_ts = time.time()

    now = time.time()
    # 可用引擎在前（冷却中的排后），同优先级保持质量顺序
    engines = sorted(
        SEARXNG_ENGINE_ORDER,
        key=lambda e: (_engine_cooldown.get(e, 0) > now, SEARXNG_ENGINE_ORDER.index(e)),
    )
    logger.info("SearXNG 引擎顺序: %s（冷却: %s）", engines, {
        e: f"{_engine_cooldown[e] - now:.0f}s" for e in _engine_cooldown if _engine_cooldown[e] > now
    } or "无")

    for engine in engines:
        params = {
            "q": query,
            "format": "json",
            "language": language,
            "safesearch": 0,
            "categories": "general",
            "engines": engine,
            "timeout": 6,
        }
        full_url = f"{instance_url.rstrip('/')}/search?{urlencode(params)}"
        try:
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
        except Exception as exc:
            logger.warning("SearXNG 引擎 %s 查询失败: %s", engine, exc)
            _engine_cooldown[engine] = time.time() + 300
            continue

        raw = data.get("results") or []
        unresponsive = [u[0] for u in (data.get("unresponsive_engines") or [])]
        if engine in unresponsive:
            logger.warning("SearXNG 引擎 %s 已被挂起（反爬/超时），冷却 5 分钟", engine)
            _engine_cooldown[engine] = time.time() + 300
            continue

        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "engine": item.get("engine", engine),
                "published_date": item.get("publishedDate", ""),
            }
            for item in raw[: max_results * 2]
        ]
        results = _filter_irrelevant_results(query, results)
        if not results:
            logger.warning(
                "SearXNG 引擎 %s 无有效结果（原始 %d 条），冷却 5 分钟", engine, len(raw)
            )
            _engine_cooldown[engine] = time.time() + 300
            continue

        results = _sort_by_finance_priority(results)
        logger.info("SearXNG 命中引擎 %s：%d 条有效结果", engine, len(results))
        return results[:max_results]

    return []


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
