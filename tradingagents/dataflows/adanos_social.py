import os
import re
from typing import Any

import requests


ADANOS_DEFAULT_BASE_URL = "https://api.adanos.org"
ADANOS_DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_SOCIAL_LOOK_BACK_DAYS = 7
LETTER_TICKER_REGEX = re.compile(r"^[A-Z]{1,10}$")
REDDIT_NEWS_TICKER_REGEX = re.compile(r"^[A-Z][A-Z0-9]{0,9}(?:\.[A-Z])?$")


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper().lstrip("$")


def is_adanos_social_sentiment_enabled() -> bool:
    return bool(os.getenv("ADANOS_API_KEY"))


def supports_adanos_social_sentiment_ticker(ticker: str) -> bool:
    normalized_ticker = _normalize_ticker(ticker)
    return bool(
        REDDIT_NEWS_TICKER_REGEX.fullmatch(normalized_ticker)
        or LETTER_TICKER_REGEX.fullmatch(normalized_ticker)
    )


def _request_json(
    path: str,
    *,
    api_key: str,
    base_url: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = requests.get(
        f"{base_url.rstrip('/')}{path}",
        headers={"X-API-Key": api_key, "Accept": "application/json"},
        params=params or {},
        timeout=float(os.getenv("ADANOS_TIMEOUT", str(ADANOS_DEFAULT_TIMEOUT_SECONDS))),
    )
    response.raise_for_status()
    return response.json()


def _iter_source_requests(ticker: str) -> list[tuple[str, str]]:
    requests_to_make: list[tuple[str, str]] = []

    if REDDIT_NEWS_TICKER_REGEX.fullmatch(ticker):
        requests_to_make.extend(
            [
                ("Reddit", f"/reddit/stocks/v1/stock/{ticker}"),
                ("News", f"/news/stocks/v1/stock/{ticker}"),
            ]
        )

    if LETTER_TICKER_REGEX.fullmatch(ticker):
        requests_to_make.extend(
            [
                ("X/Twitter", f"/x/stocks/v1/stock/{ticker}"),
                ("Polymarket", f"/polymarket/stocks/v1/stock/{ticker}"),
            ]
        )

    return requests_to_make


def _format_source_section(source_name: str, payload: dict[str, Any]) -> str:
    lines = [f"## {source_name}"]

    company_name = payload.get("company_name")
    if company_name:
        lines.append(f"- 公司: {company_name}")

    if payload.get("buzz_score") is not None:
        lines.append(f"- 热度分数: {payload['buzz_score']}")
    if payload.get("sentiment_score") is not None:
        lines.append(f"- 情绪分数: {payload['sentiment_score']}")
    if payload.get("bullish_pct") is not None or payload.get("bearish_pct") is not None:
        lines.append(
            f"- 看多/看空: {payload.get('bullish_pct', 'n/a')}% / {payload.get('bearish_pct', 'n/a')}%"
        )
    if payload.get("trend"):
        lines.append(f"- 趋势: {payload['trend']}")

    for key, label in (
        ("total_mentions", "提及数"),
        ("unique_posts", "独立帖子数"),
        ("subreddit_count", "论坛数"),
        ("source_count", "新闻源数"),
        ("unique_tweets", "独立推文数"),
        ("market_count", "活跃市场数"),
        ("trade_count", "交易笔数"),
        ("total_liquidity", "总流动性"),
    ):
        value = payload.get(key)
        if value is not None:
            lines.append(f"- {label}: {value}")

    explanation = payload.get("explanation")
    if explanation:
        lines.append(f"- 说明: {explanation}")

    return "\n".join(lines)


def get_adanos_social_sentiment(
    ticker: str,
    curr_date: str,
    look_back_days: int = DEFAULT_SOCIAL_LOOK_BACK_DAYS,
) -> str:
    """从 Adanos 获取多源社交情绪补充报告。"""
    api_key = os.getenv("ADANOS_API_KEY")
    if not api_key:
        return (
            "Adanos 全球社交情绪未启用：缺少 ADANOS_API_KEY。"
            " 配置后可补充 Reddit、News、X/Twitter 和 Polymarket 舆情。"
        )

    normalized_ticker = _normalize_ticker(ticker)
    source_requests = _iter_source_requests(normalized_ticker)
    if not source_requests:
        return (
            f"Adanos 当前不支持 `{ticker}` 这一精确代码格式的逐股舆情查询。"
            " 对于数字代码或特定交易所后缀，请继续依赖现有中文市场情绪和新闻工具。"
        )

    base_url = os.getenv("ADANOS_BASE_URL", ADANOS_DEFAULT_BASE_URL)
    days = max(1, int(look_back_days or DEFAULT_SOCIAL_LOOK_BACK_DAYS))

    sections: list[str] = []
    notes: list[str] = []

    for source_name, path in source_requests:
        try:
            payload = _request_json(path, api_key=api_key, base_url=base_url, params={"days": days})
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 404:
                notes.append(f"- {source_name}: {normalized_ticker} 暂无覆盖")
                continue
            if status_code in {401, 403}:
                return "Adanos 请求失败：API 凭据无效。"
            notes.append(f"- {source_name}: 请求失败（HTTP {status_code}）")
            continue
        except requests.RequestException as exc:
            notes.append(f"- {source_name}: 请求失败（{exc.__class__.__name__}）")
            continue

        sections.append(_format_source_section(source_name, payload))

    if not sections:
        note_block = "\n".join(notes) if notes else "- 没有可用的 Adanos 舆情数据。"
        return (
            f"# {normalized_ticker} 全球社交情绪补充（Adanos）\n\n"
            f"分析日期: {curr_date}\n"
            f"回看周期: {days} 天\n\n"
            "未获取到可用的 Adanos 舆情数据。\n"
            f"{note_block}"
        )

    output = [
        f"# {normalized_ticker} 全球社交情绪补充（Adanos）",
        "",
        f"分析日期: {curr_date}",
        f"回看周期: {days} 天",
        "",
        *sections,
    ]
    if notes:
        output.extend(["", "## 覆盖说明", *notes])

    return "\n".join(output)
