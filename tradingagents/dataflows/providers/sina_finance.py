"""
新浪财经实时行情抓取封装。

说明：
- 当前仅提供独立可调用能力，不接入主数据源调度链路。
- 主要依赖 hq.sinajs.cn 的行情接口，适合作为后续集成前的封闭验证模块。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import re
import requests


SINA_QUOTE_URL = "https://hq.sinajs.cn/list="
SINA_A_SHARE_PAGE_URL = "https://finance.sina.com.cn/realstock/company/{symbol}/nc.shtml"
SINA_HK_PAGE_URL = "https://stock.finance.sina.com.cn/hkstock/quotes/{code}.html"


@dataclass
class SinaQuote:
    symbol: str
    market: str
    source_symbol: str
    name: str
    current_price: Optional[float]
    pre_close: Optional[float]
    open_price: Optional[float]
    high_price: Optional[float]
    low_price: Optional[float]
    change_amount: Optional[float]
    change_percent: Optional[float]
    volume: Optional[float]
    amount: Optional[float]
    trade_date: Optional[str]
    trade_time: Optional[str]
    updated_at: Optional[str]
    source: str = "sina_finance"


@dataclass
class SinaFinancePageSnapshot:
    symbol: str
    market: str
    page_url: str
    title: str
    keywords: Optional[str]
    page_type: str
    html_length: int
    has_quote_api_reference: bool
    source: str = "sina_finance_page"


def _safe_float(value: object) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def normalize_sina_symbol(symbol: str, market_hint: Optional[str] = None) -> str:
    raw = str(symbol or "").strip().lower()
    if not raw:
        raise ValueError("symbol 不能为空")

    if raw.startswith(("sh", "sz", "hk")):
        return raw

    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError(f"无法识别的 symbol: {symbol}")

    market = (market_hint or "").upper().strip()
    if market in {"HK", "港股"}:
        return f"hk{digits.zfill(5)}"

    if market in {"CN", "A股"}:
        prefix = "sh" if digits.startswith(("5", "6", "9")) else "sz"
        return f"{prefix}{digits.zfill(6)}"

    if len(digits) <= 5:
        return f"hk{digits.zfill(5)}"

    prefix = "sh" if digits.startswith(("5", "6", "9")) else "sz"
    return f"{prefix}{digits.zfill(6)}"


def infer_sina_page_url(symbol: str, market_hint: Optional[str] = None) -> str:
    normalized = normalize_sina_symbol(symbol, market_hint)
    if normalized.startswith("hk"):
        return SINA_HK_PAGE_URL.format(code=normalized[2:].zfill(5))
    return SINA_A_SHARE_PAGE_URL.format(symbol=normalized)


def _parse_cn_quote(source_symbol: str, payload: List[str]) -> SinaQuote:
    name = payload[0] if len(payload) > 0 else source_symbol
    pre_close = _safe_float(payload[2] if len(payload) > 2 else None)
    current_price = _safe_float(payload[3] if len(payload) > 3 else None)

    trade_date = None
    trade_time = None
    for index, value in enumerate(payload):
        text = str(value or "").strip()
        if not trade_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            trade_date = text
            if index + 1 < len(payload):
                next_text = str(payload[index + 1] or "").strip()
                if re.fullmatch(r"\d{2}:\d{2}:\d{2}", next_text):
                    trade_time = next_text
            continue

        if not trade_time and re.fullmatch(r"\d{2}:\d{2}:\d{2}", text):
            trade_time = text

    updated_at = None
    if trade_date and trade_time:
        updated_at = f"{trade_date}T{trade_time}"

    change_amount = None
    change_percent = None
    if current_price is not None and pre_close not in (None, 0, 0.0):
        change_amount = round(current_price - pre_close, 4)
        change_percent = round((current_price / pre_close - 1.0) * 100.0, 4)

    return SinaQuote(
        symbol=source_symbol[2:],
        market="CN",
        source_symbol=source_symbol,
        name=name,
        current_price=current_price,
        pre_close=pre_close,
        open_price=_safe_float(payload[1] if len(payload) > 1 else None),
        high_price=_safe_float(payload[4] if len(payload) > 4 else None),
        low_price=_safe_float(payload[5] if len(payload) > 5 else None),
        change_amount=change_amount,
        change_percent=change_percent,
        volume=_safe_float(payload[8] if len(payload) > 8 else None),
        amount=_safe_float(payload[9] if len(payload) > 9 else None),
        trade_date=trade_date,
        trade_time=trade_time,
        updated_at=updated_at,
    )


def _parse_hk_quote(source_symbol: str, payload: List[str]) -> SinaQuote:
    name = payload[1] if len(payload) > 1 and payload[1] else (payload[0] if payload else source_symbol)
    trade_date = payload[17].replace("/", "-") if len(payload) > 17 and payload[17] else None
    trade_time = payload[18] if len(payload) > 18 and payload[18] else None
    updated_at = None
    if trade_date and trade_time:
        updated_at = f"{trade_date}T{trade_time}"

    return SinaQuote(
        symbol=source_symbol[2:],
        market="HK",
        source_symbol=source_symbol,
        name=name,
        current_price=_safe_float(payload[6] if len(payload) > 6 else None),
        pre_close=_safe_float(payload[3] if len(payload) > 3 else None),
        open_price=_safe_float(payload[2] if len(payload) > 2 else None),
        high_price=_safe_float(payload[4] if len(payload) > 4 else None),
        low_price=_safe_float(payload[5] if len(payload) > 5 else None),
        change_amount=_safe_float(payload[7] if len(payload) > 7 else None),
        change_percent=(
            round(_safe_float(payload[8] if len(payload) > 8 else None) * 100.0, 4)
            if _safe_float(payload[8] if len(payload) > 8 else None) is not None
            else None
        ),
        volume=_safe_float(payload[12] if len(payload) > 12 else None),
        amount=_safe_float(payload[11] if len(payload) > 11 else None),
        trade_date=trade_date,
        trade_time=trade_time,
        updated_at=updated_at,
    )


def parse_sina_quote_line(line: str) -> Optional[SinaQuote]:
    text = str(line or "").strip()
    if not text or not text.startswith("var hq_str_") or '="' not in text:
        return None

    prefix, raw_payload = text.split('="', 1)
    source_symbol = prefix.replace("var hq_str_", "").strip()
    payload_text = raw_payload.rsplit('";', 1)[0]
    payload = payload_text.split(",")

    if source_symbol.startswith(("sh", "sz")):
        return _parse_cn_quote(source_symbol, payload)
    if source_symbol.startswith("hk"):
        return _parse_hk_quote(source_symbol, payload)
    return None


class SinaFinanceQuoteClient:
    """独立的新浪财经行情抓取客户端。"""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def fetch_quotes(self, symbols: Iterable[str], market_hint: Optional[str] = None) -> Dict[str, SinaQuote]:
        normalized_symbols = [normalize_sina_symbol(symbol, market_hint) for symbol in symbols]
        if not normalized_symbols:
            return {}

        request = Request(
            f"{SINA_QUOTE_URL}{','.join(normalized_symbols)}?{urlencode({'_t': datetime.now().timestamp()})}",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.sina.com.cn",
            },
        )

        with urlopen(request, timeout=self.timeout) as response:
            body = response.read().decode("gbk", errors="ignore")

        result: Dict[str, SinaQuote] = {}
        for line in body.splitlines():
            parsed = parse_sina_quote_line(line)
            if not parsed:
                continue
            result[parsed.symbol] = parsed

        return result


class SinaFinancePageClient:
    """独立的新浪财经页面抓取客户端。"""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def fetch_page_snapshot(
        self, symbol: str, market_hint: Optional[str] = None
    ) -> SinaFinancePageSnapshot:
        normalized = normalize_sina_symbol(symbol, market_hint)
        page_url = infer_sina_page_url(symbol, market_hint)

        response = requests.get(
            page_url,
            timeout=self.timeout,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.sina.com.cn",
            },
        )
        response.raise_for_status()

        html = response.text
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        keywords_match = re.search(
            r'<meta\s+name="Keywords"\s+content="(.*?)"',
            html,
            re.IGNORECASE | re.DOTALL,
        )

        return SinaFinancePageSnapshot(
            symbol=normalized[2:] if normalized.startswith(("sh", "sz", "hk")) else normalized,
            market="HK" if normalized.startswith("hk") else "CN",
            page_url=page_url,
            title=title_match.group(1).strip() if title_match else "",
            keywords=keywords_match.group(1).strip() if keywords_match else None,
            page_type="hk_quote_page" if normalized.startswith("hk") else "cn_realstock_page",
            html_length=len(html),
            has_quote_api_reference=("hq.sinajs.cn" in html),
        )
