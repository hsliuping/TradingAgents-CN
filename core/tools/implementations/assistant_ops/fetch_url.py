"""网页内容抓取工具 - 获取网页的完整正文内容。"""

import logging
import random
from typing import Annotated
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20
MAX_CONTENT_LENGTH = 8000

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# 需要移除的标签（导航、广告等噪音）
REMOVE_TAGS = [
    "script", "style", "nav", "footer", "header", "aside",
    "iframe", "noscript", "form", "button", "input", "select",
    "svg", "img", "video", "audio",
]

# 噪音文本特征（导航菜单、版权声明等）
NOISE_PATTERNS = [
    "首页", "登录", "注册", "VIP邮箱", "免费下载", "客户端下载",
    "快速导航", "网易首页", "应用", "安全退出", "移动端",
    " COPYRIGHT ", "@版权", "举报", "分享至", "微信扫码",
    "申请入驻", "客户端", "关注我们", "返回首页", "网站地图",
]


def _resolve_baidu_link(url: str) -> str:
    """如果是百度跳转链接，解析出真实 URL。"""
    if "baidu.com/link" not in url and "baidu.php" not in url:
        return url
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
        )
        if resp.url and resp.url != url:
            return resp.url
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta:
            content = meta.get("content", "")
            if "url=" in content.lower():
                real_url = content.split("url=", 1)[-1].strip()
                if real_url.startswith("http"):
                    return real_url
    except Exception as exc:
        logger.warning("解析百度跳转链接失败: %s", exc)
    return url


def _is_noise(text: str) -> bool:
    """判断文本是否是导航菜单等噪音。"""
    if not text or len(text) < 10:
        return True
    # 如果文本太短，很可能是导航链接
    if len(text) < 15 and any(kw in text for kw in ["登录", "注册", "首页", "退出", "关注", "分享"]):
        return True
    # 如果包含太多噪音关键词
    noise_count = sum(1 for pattern in NOISE_PATTERNS if pattern in text)
    if noise_count >= 3:
        return True
    return False


def _extract_main_content(soup: BeautifulSoup) -> str:
    """从 BeautifulSoup 中提取正文内容，优先正文容器。"""
    # 优先级1: 明确的正文容器
    for selector in [
        ("article", None),
        ("div", "post_body"),  # 百度百家号
        ("div", "article-content"),  # 通用文章
        ("div", "post_content"),  # 博客类
        ("div", "main-content"),  # 通用
        ("div", "content"),  # 通用
        ("div", "article_content"),  # 网易
        ("div", "text"),  # 通用
        ("div", "detail"),  # 详情页
        ("div", "post_body"),
        ("div", "art_content"),
        ("div", "article-body"),
        ("div", "news_content"),
        ("div", "TRS_Editor"),
        ("main", None),
    ]:
        tag, cls = selector
        if cls:
            el = soup.find(tag, class_=cls)
        else:
            el = soup.find(tag)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 100:
                return text

    # 优先级2: body 内最长的 div
    body = soup.find("body")
    if not body:
        return ""

    best_text = ""
    best_len = 0
    for div in body.find_all("div"):
        text = div.get_text(separator="\n", strip=True)
        # 过滤噪音
        if _is_noise(text):
            continue
        if len(text) > best_len:
            best_text = text
            best_len = len(text)

    return best_text


def _clean_content(text: str) -> str:
    """清理正文文本，移除多余空行和噪音。"""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if _is_noise(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _fetch_page(url: str) -> str:
    """抓取网页内容并提取正文文本。"""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")

    # 移除不需要的标签
    for tag in soup(REMOVE_TAGS):
        tag.decompose()

    # 提取标题
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)

    # 提取正文
    content = _extract_main_content(soup)
    content = _clean_content(content)

    if not content or len(content) < 50:
        return f"标题：{title}\n链接：{url}\n\n无法提取正文内容（页面可能需要 JavaScript 渲染）。"

    # 限制返回长度
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH] + "\n\n[内容被截断，完整内容请访问原网页]"

    return f"标题：{title}\n链接：{url}\n\n{content}"


def run_fetch_url(url: str) -> str:
    """抓取网页内容。"""
    if not url or not url.strip():
        return "请提供要抓取的网页链接。"

    url = url.strip()

    # 如果是百度跳转链接，先解析真实 URL
    if "baidu.com/link" in url or "baidu.php" in url:
        logger.info("解析百度跳转链接: %s", url[:80])
        real_url = _resolve_baidu_link(url)
        if real_url != url:
            logger.info("真实URL: %s", real_url[:80])
            url = real_url

    # 检查是否是百度验证页面
    if "wappass.baidu.com" in url or "captcha" in url:
        return f"该链接跳转到了百度安全验证页面，无法抓取内容。请尝试其他搜索结果。"

    try:
        logger.info("抓取网页: %s", url[:80])
        return _fetch_page(url)
    except requests.exceptions.Timeout:
        return f"抓取超时：{url}"
    except requests.exceptions.ConnectionError as exc:
        return f"连接失败：{url}\n错误：{exc}"
    except Exception as exc:
        return f"抓取失败：{url}\n错误：{exc}"


@tool
@register_tool(
    tool_id="fetch_url",
    name="网页内容抓取",
    description="抓取指定网页的完整正文内容。当 web_search 返回的摘要信息不够详细时，用此工具抓取搜索结果链接的完整页面。支持解析百度跳转链接获取真实URL。自动提取正文内容，过滤导航菜单、广告等噪音。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    data_source_handling="local_only",
    capability_tags=[
        "web_fetch", "content_extraction", "url_read",
        "page_scrape", "information_retrieval", "real_time_info",
    ],
    tool_role_hint="specialized",
    output_shape="report",
    preferred_for=[
        "获取搜索结果的完整网页内容",
        "读取新闻文章原文",
        "查看公告或报告的详细内容",
        "补充搜索摘要中缺失的细节",
    ],
    when_to_use="当 web_search 搜索结果的摘要信息不够，需要获取完整网页内容时使用。",
    returns="返回网页标题和正文文本（最多8000字符），自动去除导航、广告等无关内容。",
)
def fetch_url(
    url: Annotated[str, "要抓取的网页链接，可以是直接URL或百度搜索结果的跳转链接"],
) -> str:
    """抓取网页的完整正文内容。"""
    return run_fetch_url(url)
