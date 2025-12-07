"""
硬编码代理测试：使用指定代理访问 Yahoo Finance 并获取港股新闻。

运行：
  python scripts/test/yf_hk_news_hardcoded.py [--symbol 0700] [--days 2] [--limit 50]

说明：
- 代理固定为 http://127.0.0.1:10809（同时用于 http/https）。
- 不读取环境变量，也不接收代理参数，完全写死。
"""

import argparse
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yfinance as yf
import os
import requests


# 固定代理与UA
HTTP_PROXY = "http://127.0.0.1:10809"
HTTPS_PROXY = "http://127.0.0.1:10809"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36 TradingAgentsCN/1.0"
)

# 固定 trace id（与示例日志保持一致风格）
TRACE_ID = "c73376da-e015-4527-a387-7439d12c3fd8"


def normalize_hk_symbol(code: str) -> str:
    """标准化港股代码为 Yahoo 期望格式：4位数字 + .HK"""
    if not code:
        return code
    s = str(code).strip().upper()
    if s.endswith(".HK"):
        s = s[:-3]
    if s.isdigit():
        s = s.lstrip("0") or "0"
        s = s.zfill(4)
        return f"{s}.HK"
    return s


def apply_env_proxies():
    os.environ["HTTP_PROXY"] = HTTP_PROXY
    os.environ["HTTPS_PROXY"] = HTTPS_PROXY
    # 有些环境同时读取大写/小写；为稳妥也设定小写形式
    os.environ["http_proxy"] = HTTP_PROXY
    os.environ["https_proxy"] = HTTPS_PROXY


def probe_yahoo_connectivity(logger: logging.Logger) -> None:
    url = "https://query1.finance.yahoo.com/v1/finance/search?q=tencent&lang=zh-Hans-HK"
    headers = {"User-Agent": USER_AGENT}
    proxies = {"http": HTTP_PROXY, "https": HTTPS_PROXY}
    try:
        r = requests.get(url, headers=headers, proxies=proxies, timeout=10)
        if r.status_code == 200:
            data = r.json()
            keys = list(data.keys())
            logger.info(
                f"🔎 Yahoo 接入探测成功: status=200 keys={keys[:5]} trace={TRACE_ID}"
            )
        else:
            logger.warning(
                f"🔎 Yahoo 接入探测返回非200: status={r.status_code} trace={TRACE_ID}"
            )
    except Exception as e:
        logger.error(f"🔎 Yahoo 接入探测失败: {e} trace={TRACE_ID}")


def parse_article_datetime(article: Dict) -> Optional[datetime]:
    ts = article.get("providerPublishTime")
    if isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(ts)
        except Exception:
            pass
    for key in ("pubDate", "published"):
        val = article.get(key)
        if isinstance(val, str) and val:
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(val, fmt)
                except Exception:
                    continue
    return None


def fetch_hk_news(symbol: str, days: int, limit: int) -> List[Dict]:
    yf_symbol = normalize_hk_symbol(symbol)
    # 让 yfinance 自行构建其内部 curl_cffi 会话，代理由环境变量控制
    ticker = yf.Ticker(yf_symbol)
    articles = getattr(ticker, "news", [])
    if not articles:
        return []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    filtered: List[Dict] = []
    for a in articles:
        content = a.get("content") or {}
        dt = parse_article_datetime({**a, **content})
        if dt and start_date <= dt <= end_date:
            title = a.get("title") or content.get("title", "")
            url = (
                a.get("link")
                or content.get("url")
                or content.get("clickThroughUrl")
                or ""
            )
            provider = a.get("publisher")
            if not provider:
                prov = content.get("provider") or {}
                provider = prov.get("displayName") or prov.get("name") or ""
            summary = (
                a.get("summary")
                or content.get("summary")
                or content.get("description")
                or ""
            )
            filtered.append({
                "title": title,
                "summary": summary,
                "url": url,
                "source": provider,
                "publish_time": dt.strftime("%Y-%m-%d %H:%M:%S"),
            })
    return filtered[:limit]


def main():
    parser = argparse.ArgumentParser(description="硬编码代理测试：Yahoo Finance 港股新闻")
    parser.add_argument("--symbol", type=str, default="0700", help="港股代码，如 0700/00700/0700.HK")
    parser.add_argument("--days", type=int, default=2, help="时间范围（天）")
    parser.add_argument("--limit", type=int, default=50, help="最大返回条数")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s"
    )
    logger = logging.getLogger("agents")

    # 打印代理信息（与项目日志格式一致）
    logger.info(
        f"🌐 使用代理访问 Yahoo Finance: {{'http': '{HTTP_PROXY}', 'https': '{HTTPS_PROXY}'}} trace={TRACE_ID}"
    )

    # 将代理写入环境变量，供 yfinance/curl_cffi 使用
    apply_env_proxies()
    # yfinance 不直接读取 UA 环境变量；此处主要用于我们自己的日志一致性

    try:
        # 先做连接探测
        probe_yahoo_connectivity(logger)

        items = fetch_hk_news(args.symbol, args.days, args.limit)
        if not items:
            logger.warning(f"⚠️ 未获取到新闻数据（可能需要代理或被限频）  trace={TRACE_ID}")
            # 同时输出原始 news 条数，便于排查
            yf_symbol = normalize_hk_symbol(args.symbol)
            raw_news = getattr(yf.Ticker(yf_symbol), "news", [])
            logger.info(f"📦 原始 news 数量: {len(raw_news)} trace={TRACE_ID}")
            if raw_news:
                for i, a in enumerate(raw_news[:3], 1):
                    content = a.get("content") or {}
                    title = a.get("title") or content.get("title", "")
                    source = a.get("publisher") or content.get("provider", "")
                    ts = a.get("providerPublishTime") or a.get("pubDate") or content.get("pubDate")
                    logger.info(
                        f"示例[{i}] title={title} source={source} ts={ts} keys={list(a.keys())}"
                    )
        else:
            logger.info(f"✅ 成功获取到 {len(items)} 条新闻 trace={TRACE_ID}")
            for i, it in enumerate(items, 1):
                print(f"[{i}] {it['publish_time']} | {it['source']} | {it['title']}")
                print(f"    {it['url']}")
    except Exception as e:
        logger.error(f"❌ 获取港股新闻失败: {e} trace={TRACE_ID}")


if __name__ == "__main__":
    main()
