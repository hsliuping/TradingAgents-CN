"""Candidate-scoped, versioned real-data ingestion for AlphaGuard activation.

The service writes only the repositories already consumed by AlphaGuard.  It
never creates a second price/financial/news store and never substitutes test
fixtures or a live response for a persisted evidence reference.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

from tradingagents.alphaguard.instruments import normalize_instrument

from .real_data_ingestion_service import (
    RealDataIntegrityConflict,
    RealDataProviderError,
    real_data_hash,
)
from .data_quality_gate import DataQualityGate
from .production_data_config import production_market_context_policy


PRICE_FIELDS = (
    "date,code,open,high,low,close,preclose,volume,amount,adjustflag,"
    "turn,tradestatus,pctChg,isST,peTTM,pbMRQ,psTTM,pcfNcfTTM"
)
NORMALIZATION_VERSION = "alphaguard-candidate-real-data-v1"


def _number(value: Any) -> float | None:
    if value in (None, "", "None", "nan", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _business_timestamp(value: date, *, hour: int = 0) -> datetime:
    return datetime.combine(value, time(hour=hour))


def _baostock_code(symbol: str) -> str:
    return f"{'sh' if symbol.startswith('6') else 'sz'}.{symbol}"


def _frame_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    return [
        {str(key): value for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


@dataclass(frozen=True)
class CandidateDataFetchResult:
    provider_versions: dict[str, str]
    raw_prices: tuple[dict[str, Any], ...]
    qfq_prices: tuple[dict[str, Any], ...]
    benchmark_prices: tuple[dict[str, Any], ...]
    financials: tuple[dict[str, Any], ...]
    news: tuple[dict[str, Any], ...]
    announcements: tuple[dict[str, Any], ...]
    industry: tuple[dict[str, Any], ...]
    response_hashes: dict[str, str]


class CandidateDataProvider(Protocol):
    name: str

    def capability_check(self) -> dict[str, Any]: ...

    def fetch(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> CandidateDataFetchResult: ...


class BaoStockAKShareCandidateProvider:
    """BaoStock fundamentals/prices plus AKShare public news/disclosures."""

    name = "baostock+akshare"

    @staticmethod
    def capability_check() -> dict[str, Any]:
        try:
            import akshare as ak
            import baostock as bs

            return {
                "provider": BaoStockAKShareCandidateProvider.name,
                "available": True,
                "provider_versions": {
                    "akshare": getattr(ak, "__version__", "unknown"),
                    "baostock": getattr(bs, "__version__", "unknown"),
                },
                "capabilities": [
                    "RAW_DAILY_PRICE",
                    "QFQ_DAILY_PRICE",
                    "BENCHMARK_PRICE",
                    "FINANCIAL_DATA",
                    "NEWS",
                    "ANNOUNCEMENTS",
                    "INDUSTRY_CURRENT",
                ],
            }
        except Exception as exc:
            return {
                "provider": BaoStockAKShareCandidateProvider.name,
                "available": False,
                "error_type": type(exc).__name__,
            }

    @staticmethod
    def _query_rows(result: Any, *, label: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        while result.error_code == "0" and result.next():
            rows.append(dict(zip(result.fields, result.get_row_data())))
        if result.error_code != "0":
            raise RealDataProviderError(f"BaoStock {label} query failed")
        return rows

    @classmethod
    def fetch(
        cls,
        symbol: str,
        start: date,
        end: date,
    ) -> CandidateDataFetchResult:
        import akshare as ak
        import baostock as bs

        market, symbol = normalize_instrument(symbol, "CN")
        if market != "CN":
            raise RealDataProviderError("automatic real-data activation supports CN only")
        capability = cls.capability_check()
        versions = capability.get("provider_versions") or {}
        login = bs.login()
        if login.error_code != "0":
            raise RealDataProviderError("BaoStock login failed")
        try:
            bs_code = _baostock_code(symbol)
            raw_prices = cls._query_rows(
                bs.query_history_k_data_plus(
                    bs_code,
                    PRICE_FIELDS,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    frequency="d",
                    adjustflag="3",
                ),
                label="raw daily price",
            )
            qfq_prices = cls._query_rows(
                bs.query_history_k_data_plus(
                    bs_code,
                    PRICE_FIELDS,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    frequency="d",
                    adjustflag="2",
                ),
                label="QFQ daily price",
            )
            benchmark_prices = cls._query_rows(
                bs.query_history_k_data_plus(
                    "sh.000300",
                    PRICE_FIELDS,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    frequency="d",
                    adjustflag="3",
                ),
                label="CSI300 daily price",
            )

            financials: list[dict[str, str]] = []
            for year in range(start.year, end.year + 1):
                for quarter in range(1, 5):
                    financials.extend(
                        cls._query_rows(
                            bs.query_profit_data(
                                code=bs_code,
                                year=year,
                                quarter=quarter,
                            ),
                            label=f"profit {year}Q{quarter}",
                        )
                    )
            industry = cls._query_rows(
                bs.query_stock_industry(code=bs_code),
                label="industry",
            )
        finally:
            bs.logout()

        news = _frame_records(ak.stock_news_em(symbol=symbol))
        announcements = _frame_records(
            ak.stock_zh_a_disclosure_report_cninfo(
                symbol=symbol,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
        )
        payloads = {
            "raw_prices": raw_prices,
            "qfq_prices": qfq_prices,
            "benchmark_prices": benchmark_prices,
            "financials": financials,
            "news": news,
            "announcements": announcements,
            "industry": industry,
        }
        return CandidateDataFetchResult(
            provider_versions={
                "baostock": str(versions.get("baostock") or "unknown"),
                "akshare": str(versions.get("akshare") or "unknown"),
            },
            raw_prices=tuple(raw_prices),
            qfq_prices=tuple(qfq_prices),
            benchmark_prices=tuple(benchmark_prices),
            financials=tuple(financials),
            news=tuple(news),
            announcements=tuple(announcements),
            industry=tuple(industry),
            response_hashes={
                key: real_data_hash(value) for key, value in payloads.items()
            },
        )


class CandidateRealDataService:
    """Normalize candidate data and create immutable, traceable source rows."""

    COLLECTIONS = {
        "prices": "stock_daily_quotes",
        "financials": "stock_financial_data",
        "news": "stock_news",
        "announcements": "stock_announcements",
        "industry": "stock_industry_history",
    }

    def __init__(self, db):
        self.db = db

    async def _fetch(
        self,
        provider: CandidateDataProvider,
        *,
        symbol: str,
        start: date,
        end: date,
        timeout_seconds: float,
        max_attempts: int,
    ) -> tuple[CandidateDataFetchResult, list[dict[str, str]]]:
        capability = provider.capability_check()
        if capability.get("available") is not True:
            raise RealDataProviderError(
                f"{provider.name} capability check failed: "
                f"{capability.get('error_type', 'UNAVAILABLE')}"
            )
        failures: list[dict[str, str]] = []
        for attempt in range(1, max_attempts + 1):
            try:
                return (
                    await asyncio.wait_for(
                        asyncio.to_thread(provider.fetch, symbol, start, end),
                        timeout=timeout_seconds,
                    ),
                    failures,
                )
            except Exception as exc:
                failures.append(
                    {
                        "provider": provider.name,
                        "attempt": str(attempt),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:300],
                    }
                )
                if attempt < max_attempts:
                    await asyncio.sleep(min(attempt, 2))
        raise RealDataProviderError(
            f"{provider.name} failed after {max_attempts} attempts: "
            f"{failures[-1]['error_type']}"
        )

    @staticmethod
    def _price_documents(
        *,
        symbol: str,
        result: CandidateDataFetchResult,
        collected_at: datetime,
    ) -> list[dict[str, Any]]:
        raw_by_date = {
            str(item.get("date")): item
            for item in result.raw_prices
            if item.get("date")
        }
        qfq_by_date = {
            str(item.get("date")): item
            for item in result.qfq_prices
            if item.get("date")
        }
        baostock_version = result.provider_versions["baostock"]
        price_version = (
            f"baostock:{baostock_version}:QFQ:{NORMALIZATION_VERSION}"
        )
        raw_version = f"baostock:{baostock_version}:RAW:{NORMALIZATION_VERSION}"
        documents: list[dict[str, Any]] = []
        for value in sorted(set(raw_by_date) & set(qfq_by_date)):
            raw = raw_by_date[value]
            qfq = qfq_by_date[value]
            trade_date = date.fromisoformat(value)
            source_record_id = f"{_baostock_code(symbol)}:{value}:daily"
            business = {
                "ref_id": f"price-{symbol}-{value}",
                "source_record_id": source_record_id,
                "symbol": symbol,
                "code": symbol,
                "market": "CN",
                "business_date": _business_timestamp(trade_date),
                "trade_date": _business_timestamp(trade_date),
                "timestamp": _business_timestamp(trade_date, hour=15),
                "period": "daily",
                "open": _number(raw.get("open")),
                "high": _number(raw.get("high")),
                "low": _number(raw.get("low")),
                "close": _number(raw.get("close")),
                "adjusted_open": _number(qfq.get("open")),
                "adjusted_high": _number(qfq.get("high")),
                "adjusted_low": _number(qfq.get("low")),
                "adjusted_close": _number(qfq.get("close")),
                "prev_close": _number(raw.get("preclose")),
                "volume": _integer(raw.get("volume")),
                "amount": _number(raw.get("amount")),
                "turnover_rate": _number(raw.get("turn")),
                "pct_change": _number(raw.get("pctChg")),
                "pe_ttm": _number(raw.get("peTTM")),
                "pb": _number(raw.get("pbMRQ")),
                "ps_ttm": _number(raw.get("psTTM")),
                "pcf_ttm": _number(raw.get("pcfNcfTTM")),
                "suspended": (
                    str(raw.get("tradestatus", "")).strip() != "1"
                    if raw.get("tradestatus") not in (None, "")
                    else None
                ),
                "st_status": (
                    str(raw.get("isST", "")).strip() == "1"
                    if raw.get("isST") not in (None, "")
                    else None
                ),
                "adjustment_mode": "QFQ",
                "price_adjustment_mode": "QFQ",
                "price_data_version": price_version,
                "adjusted_data_version": price_version,
                "raw_data_version": raw_version,
                "data_version": price_version,
                "data_ref": f"stock_daily_quotes:price-{symbol}-{value}",
                "provider": "baostock",
                "provider_version": baostock_version,
                "normalization_version": NORMALIZATION_VERSION,
            }
            documents.append(
                {
                    **business,
                    "available_at": _business_timestamp(trade_date, hour=15),
                    "collected_at": collected_at,
                    "created_at": collected_at,
                    "content_hash": real_data_hash(business),
                    "source_response_hash": real_data_hash({"raw": raw, "qfq": qfq}),
                    "schema_version": "alphaguard-real-price-v1",
                }
            )
        return documents

    @staticmethod
    def _benchmark_documents(
        result: CandidateDataFetchResult,
        collected_at: datetime,
    ) -> list[dict[str, Any]]:
        baostock_version = result.provider_versions["baostock"]
        version = (
            f"baostock:{baostock_version}:INDEX_RAW:"
            f"{NORMALIZATION_VERSION}"
        )
        documents = []
        for row in sorted(result.benchmark_prices, key=lambda item: str(item["date"])):
            trade_date = date.fromisoformat(str(row["date"]))
            business = {
                "ref_id": f"index-000300-{trade_date.isoformat()}",
                "source_record_id": f"sh.000300:{trade_date.isoformat()}:daily",
                "symbol": "000300",
                "code": "000300",
                "market": "CN",
                "business_date": _business_timestamp(trade_date),
                "trade_date": _business_timestamp(trade_date),
                "timestamp": _business_timestamp(trade_date, hour=15),
                "period": "daily",
                "open": _number(row.get("open")),
                "high": _number(row.get("high")),
                "low": _number(row.get("low")),
                "close": _number(row.get("close")),
                "adjusted_open": _number(row.get("open")),
                "adjusted_high": _number(row.get("high")),
                "adjusted_low": _number(row.get("low")),
                "adjusted_close": _number(row.get("close")),
                "prev_close": _number(row.get("preclose")),
                "volume": _integer(row.get("volume")),
                "amount": _number(row.get("amount")),
                "suspended": (
                    str(row.get("tradestatus", "")).strip() != "1"
                    if row.get("tradestatus") not in (None, "")
                    else None
                ),
                "adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
                "price_adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
                "price_data_version": version,
                "adjusted_data_version": version,
                "raw_data_version": version,
                "data_version": version,
                "data_ref": (
                    f"index_daily:index-000300-{trade_date.isoformat()}"
                ),
                "provider": "baostock",
                "provider_version": baostock_version,
                "normalization_version": NORMALIZATION_VERSION,
            }
            documents.append(
                {
                    **business,
                    "available_at": _business_timestamp(trade_date, hour=15),
                    "collected_at": collected_at,
                    "created_at": collected_at,
                    "content_hash": real_data_hash(business),
                    "source_response_hash": real_data_hash(row),
                    "schema_version": "alphaguard-real-index-price-v1",
                }
            )
        return documents

    @staticmethod
    def _financial_documents(
        *,
        symbol: str,
        result: CandidateDataFetchResult,
        collected_at: datetime,
    ) -> list[dict[str, Any]]:
        provider_version = result.provider_versions["baostock"]
        version = f"baostock:{provider_version}:PROFIT:{NORMALIZATION_VERSION}"
        documents: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in result.financials:
            report_text = str(row.get("statDate") or "")
            publish_text = str(row.get("pubDate") or "")
            if not report_text or not publish_text:
                continue
            identity = (report_text, publish_text)
            if identity in seen:
                continue
            seen.add(identity)
            report_date = date.fromisoformat(report_text)
            published_date = date.fromisoformat(publish_text)
            business = {
                "ref_id": f"financial-{symbol}-{report_text}-{publish_text}",
                "source_record_id": (
                    f"{_baostock_code(symbol)}:profit:{report_text}:{publish_text}"
                ),
                "symbol": symbol,
                "code": symbol,
                "market": "CN",
                "business_date": _business_timestamp(report_date),
                "report_period": _business_timestamp(report_date),
                "end_date": _business_timestamp(report_date),
                "published_at": _business_timestamp(published_date),
                "f_ann_date": _business_timestamp(published_date),
                "ann_date": _business_timestamp(published_date),
                "revenue": _number(row.get("MBRevenue")),
                "net_income": _number(row.get("netProfit")),
                "net_profit": _number(row.get("netProfit")),
                "roe": _number(row.get("roeAvg")),
                "net_margin": _number(row.get("npMargin")),
                "gross_margin": _number(row.get("gpMargin")),
                "eps_ttm": _number(row.get("epsTTM")),
                "total_share": _number(row.get("totalShare")),
                "liquid_share": _number(row.get("liqaShare")),
                "provider": "baostock",
                "provider_version": provider_version,
                "normalization_version": NORMALIZATION_VERSION,
                "data_version": version,
            }
            documents.append(
                {
                    **business,
                    "available_at": _business_timestamp(published_date),
                    "collected_at": collected_at,
                    "created_at": collected_at,
                    "content_hash": real_data_hash(business),
                    "source_response_hash": real_data_hash(row),
                    "schema_version": "alphaguard-real-financial-v1",
                }
            )
        documents.sort(key=lambda item: (item["report_period"], item["published_at"]))
        return documents

    @staticmethod
    def _news_documents(
        *,
        symbol: str,
        result: CandidateDataFetchResult,
        collected_at: datetime,
    ) -> list[dict[str, Any]]:
        provider_version = result.provider_versions["akshare"]
        documents = []
        for row in result.news:
            title = str(row.get("新闻标题") or row.get("标题") or "").strip()
            published = str(row.get("发布时间") or row.get("时间") or "").strip()
            url = str(row.get("新闻链接") or row.get("链接") or "").strip()
            if not title or not published:
                continue
            try:
                published_at = datetime.fromisoformat(published.replace("/", "-"))
            except ValueError:
                continue
            source_record_id = real_data_hash(
                {"symbol": symbol, "title": title, "published": published, "url": url}
            )
            business = {
                "ref_id": f"news-{source_record_id}",
                "news_id": source_record_id,
                "source_record_id": source_record_id,
                "symbol": symbol,
                "symbols": [symbol],
                "market": "CN",
                "business_date": published_at,
                "publish_time": published_at,
                "published_at": published_at,
                "title": title,
                "summary": str(row.get("新闻内容") or row.get("内容") or "").strip(),
                "source": str(row.get("文章来源") or row.get("来源") or "akshare"),
                "url": url,
                "provider": "akshare",
                "provider_version": provider_version,
                "normalization_version": NORMALIZATION_VERSION,
                "data_version": (
                    f"akshare:{provider_version}:STOCK_NEWS:{NORMALIZATION_VERSION}"
                ),
            }
            documents.append(
                {
                    **business,
                    "available_at": published_at,
                    "collected_at": collected_at,
                    "created_at": collected_at,
                    "content_hash": real_data_hash(business),
                    "source_response_hash": real_data_hash(row),
                    "schema_version": "alphaguard-real-news-v1",
                }
            )
        return sorted(documents, key=lambda item: (item["published_at"], item["ref_id"]))

    @staticmethod
    def _announcement_documents(
        *,
        symbol: str,
        result: CandidateDataFetchResult,
        collected_at: datetime,
    ) -> list[dict[str, Any]]:
        provider_version = result.provider_versions["akshare"]
        documents = []
        for row in result.announcements:
            title = str(row.get("公告标题") or row.get("标题") or "").strip()
            published = str(row.get("公告时间") or row.get("公告日期") or "").strip()
            url = str(row.get("公告链接") or row.get("网址") or "").strip()
            if not title or not published:
                continue
            try:
                published_at = datetime.fromisoformat(published[:10])
            except ValueError:
                continue
            query = parse_qs(urlparse(url).query)
            upstream_id = (
                (query.get("announcementId") or query.get("id") or [None])[0]
            )
            source_record_id = str(
                upstream_id
                or real_data_hash(
                    {
                        "symbol": symbol,
                        "title": title,
                        "published": published,
                        "url": url,
                    }
                )
            )
            business = {
                "ref_id": f"announcement-{source_record_id}",
                "announcement_id": source_record_id,
                "source_record_id": source_record_id,
                "symbol": symbol,
                "code": symbol,
                "market": "CN",
                "business_date": published_at,
                "announcement_time": published_at,
                "published_at": published_at,
                "title": title,
                "url": url,
                "provider": "akshare-cninfo",
                "provider_version": provider_version,
                "normalization_version": NORMALIZATION_VERSION,
                "data_version": (
                    f"akshare:{provider_version}:CNINFO:{NORMALIZATION_VERSION}"
                ),
            }
            documents.append(
                {
                    **business,
                    "available_at": published_at,
                    "collected_at": collected_at,
                    "created_at": collected_at,
                    "content_hash": real_data_hash(business),
                    "source_response_hash": real_data_hash(row),
                    "schema_version": "alphaguard-real-announcement-v1",
                }
            )
        return sorted(documents, key=lambda item: (item["published_at"], item["ref_id"]))

    @staticmethod
    def _industry_documents(
        *,
        symbol: str,
        result: CandidateDataFetchResult,
        collected_at: datetime,
    ) -> list[dict[str, Any]]:
        provider_version = result.provider_versions["baostock"]
        documents = []
        for row in result.industry:
            effective_text = str(row.get("updateDate") or "").strip()
            if not effective_text:
                continue
            effective_from = date.fromisoformat(effective_text)
            industry_value = str(row.get("industry") or "").strip()
            industry_code = (
                industry_value[:3]
                if len(industry_value) >= 3
                and industry_value[0].isalpha()
                and industry_value[1:3].isdigit()
                else None
            )
            industry_name = (
                industry_value[3:].strip() if industry_code else industry_value
            )
            business = {
                "ref_id": f"industry-{symbol}-{effective_text}",
                "source_record_id": f"{_baostock_code(symbol)}:industry:{effective_text}",
                "symbol": symbol,
                "code": symbol,
                "market": "CN",
                "business_date": _business_timestamp(effective_from),
                "effective_from": _business_timestamp(effective_from),
                "effective_to": None,
                "industry_code": industry_code,
                "industry_name": industry_name or None,
                "classification": str(
                    row.get("industryClassification") or "CSRC"
                ),
                "history_coverage_status": "CURRENT_ONLY",
                "provider": "baostock",
                "provider_version": provider_version,
                "normalization_version": NORMALIZATION_VERSION,
                "data_version": (
                    f"baostock:{provider_version}:INDUSTRY:{NORMALIZATION_VERSION}"
                ),
            }
            documents.append(
                {
                    **business,
                    "available_at": _business_timestamp(effective_from),
                    "collected_at": collected_at,
                    "created_at": collected_at,
                    "content_hash": real_data_hash(business),
                    "source_response_hash": real_data_hash(row),
                    "schema_version": "alphaguard-real-industry-v1",
                }
            )
        return sorted(documents, key=lambda item: item["effective_from"])

    async def _persist(
        self,
        *,
        collection_name: str,
        documents: list[dict[str, Any]],
        execute: bool,
    ) -> dict[str, int]:
        summary = {"record_count": len(documents), "created": 0, "reused": 0, "conflicts": 0}
        if not documents:
            return summary
        identities = [document["ref_id"] for document in documents]
        existing = await self.db[collection_name].find(
            {"ref_id": {"$in": identities}}
        ).to_list(length=None)
        existing_by_id = {str(item["ref_id"]): item for item in existing}
        for document in documents:
            previous = existing_by_id.get(document["ref_id"])
            if previous is None:
                continue
            if str(previous.get("content_hash")) != document["content_hash"]:
                summary["conflicts"] += 1
            else:
                summary["reused"] += 1
        if summary["conflicts"]:
            raise RealDataIntegrityConflict(
                f"{collection_name} has {summary['conflicts']} immutable conflicts"
            )
        if not execute:
            return summary
        await self.db[collection_name].create_index(
            [("ref_id", 1)],
            name=f"uniq_{collection_name}_real_ref",
            unique=True,
            sparse=True,
        )
        for document in documents:
            if document["ref_id"] in existing_by_id:
                continue
            await self.db[collection_name].insert_one(document)
            summary["created"] += 1
        return summary

    async def sync_candidate(
        self,
        *,
        symbol: str,
        start: date,
        end: date,
        execute: bool,
        provider: CandidateDataProvider | None = None,
        timeout_seconds: float = 90,
        max_attempts: int = 3,
        collected_at: datetime | None = None,
    ) -> dict[str, Any]:
        if end < start:
            raise ValueError("candidate data end date precedes start date")
        market, symbol = normalize_instrument(symbol, "CN")
        if market != "CN":
            raise ValueError("real-data activation candidate must be CN")
        instrument = await self.db["stock_basic_info"].find_one(
            {"$or": [{"symbol": symbol}, {"code": symbol}]}
        )
        if instrument is None:
            raise LookupError(f"stock_basic_info lacks user-selected symbol {symbol}")
        provider = provider or BaoStockAKShareCandidateProvider()
        started_at = datetime.utcnow()
        result, failures = await self._fetch(
            provider,
            symbol=symbol,
            start=start,
            end=end,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        )
        collected_at = collected_at or datetime.utcnow()
        price_documents = self._price_documents(
            symbol=symbol,
            result=result,
            collected_at=collected_at,
        )
        benchmark_documents = self._benchmark_documents(result, collected_at)
        financial_documents = self._financial_documents(
            symbol=symbol,
            result=result,
            collected_at=collected_at,
        )
        news_documents = self._news_documents(
            symbol=symbol,
            result=result,
            collected_at=collected_at,
        )
        announcement_documents = self._announcement_documents(
            symbol=symbol,
            result=result,
            collected_at=collected_at,
        )
        industry_documents = self._industry_documents(
            symbol=symbol,
            result=result,
            collected_at=collected_at,
        )

        categories = {
            "RAW_QFQ_DAILY_PRICE": await self._persist(
                collection_name=self.COLLECTIONS["prices"],
                documents=price_documents,
                execute=execute,
            ),
            "BENCHMARK_PRICE": await self._persist(
                collection_name=self.COLLECTIONS["prices"],
                documents=benchmark_documents,
                execute=execute,
            ),
            "FINANCIAL_DATA": await self._persist(
                collection_name=self.COLLECTIONS["financials"],
                documents=financial_documents,
                execute=execute,
            ),
            "NEWS": await self._persist(
                collection_name=self.COLLECTIONS["news"],
                documents=news_documents,
                execute=execute,
            ),
            "ANNOUNCEMENTS": await self._persist(
                collection_name=self.COLLECTIONS["announcements"],
                documents=announcement_documents,
                execute=execute,
            ),
            "INDUSTRY_HISTORY": await self._persist(
                collection_name=self.COLLECTIONS["industry"],
                documents=industry_documents,
                execute=execute,
            ),
        }
        if not price_documents:
            raise RealDataProviderError(f"{symbol} returned no usable RAW/QFQ overlap")
        data_versions = {
            "price": price_documents[-1]["price_data_version"],
            "benchmark": (
                benchmark_documents[-1]["price_data_version"]
                if benchmark_documents
                else None
            ),
            "financial": (
                financial_documents[-1]["data_version"]
                if financial_documents
                else None
            ),
            "news": (
                news_documents[-1]["data_version"] if news_documents else None
            ),
            "announcements": (
                announcement_documents[-1]["data_version"]
                if announcement_documents
                else None
            ),
            "industry": (
                industry_documents[-1]["data_version"]
                if industry_documents
                else None
            ),
        }
        summary = {
            "domain": "CANDIDATE_REAL_DATA",
            "symbol": symbol,
            "market": "CN",
            "instrument_name": str(
                instrument.get("name") or instrument.get("stock_name") or ""
            ),
            "start_date": price_documents[0]["trade_date"].date(),
            "end_date": price_documents[-1]["trade_date"].date(),
            "provider_versions": result.provider_versions,
            "data_versions": data_versions,
            "categories": categories,
            "provider_failures": failures,
            "response_hashes": result.response_hashes,
            "write": execute,
        }
        if execute:
            await self.db["sync_status"].update_one(
                {
                    "job": f"alphaguard_real_data:CANDIDATE:{symbol}",
                    "data_type": "CANDIDATE_REAL_DATA",
                },
                {
                    "$set": {
                        "job": f"alphaguard_real_data:CANDIDATE:{symbol}",
                        "data_type": "CANDIDATE_REAL_DATA",
                        "symbol": symbol,
                        "market": "CN",
                        "status": "completed",
                        "provider": provider.name,
                        "provider_versions": result.provider_versions,
                        "data_versions": data_versions,
                        "start_date": _business_timestamp(summary["start_date"]),
                        "end_date": _business_timestamp(summary["end_date"]),
                        "record_count": sum(
                            item["record_count"] for item in categories.values()
                        ),
                        "started_at": started_at,
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "schema_version": "alphaguard-real-data-sync-v1",
                    }
                },
                upsert=True,
            )
        return summary

    async def precheck_candidate(
        self,
        *,
        symbol: str,
        trade_date: date,
        cutoff_at: datetime,
    ) -> dict[str, Any]:
        """Build deterministic persisted references without creating a snapshot."""

        market, symbol = normalize_instrument(symbol, "CN")
        if market != "CN":
            raise ValueError("real-data activation candidate must be CN")
        instrument = await self.db["stock_basic_info"].find_one(
            {"$or": [{"symbol": symbol}, {"code": symbol}]}
        )
        if instrument is None:
            raise LookupError(f"stock_basic_info lacks user-selected symbol {symbol}")

        target = await self.db["stock_daily_quotes"].find_one(
            {
                "symbol": symbol,
                "market": "CN",
                "trade_date": _business_timestamp(trade_date),
                "price_adjustment_mode": "QFQ",
            }
        )
        price_version = str((target or {}).get("price_data_version") or "")
        prices = (
            await self.db["stock_daily_quotes"]
            .find(
                {
                    "symbol": symbol,
                    "market": "CN",
                    "period": "daily",
                    "price_data_version": price_version,
                    "trade_date": {"$lte": _business_timestamp(trade_date)},
                }
            )
            .sort("trade_date", -1)
            .limit(800)
            .to_list(length=800)
            if price_version
            else []
        )
        prices.reverse()

        benchmark_target = await self.db["stock_daily_quotes"].find_one(
            {
                "symbol": "000300",
                "market": "CN",
                "trade_date": _business_timestamp(trade_date),
                "period": "daily",
            }
        )
        benchmark_version = str(
            (benchmark_target or {}).get("price_data_version") or ""
        )
        benchmark = (
            await self.db["stock_daily_quotes"]
            .find(
                {
                    "symbol": "000300",
                    "market": "CN",
                    "period": "daily",
                    "price_data_version": benchmark_version,
                    "trade_date": {"$lte": _business_timestamp(trade_date)},
                }
            )
            .sort("trade_date", -1)
            .limit(800)
            .to_list(length=800)
            if benchmark_version
            else []
        )
        benchmark.reverse()

        financials = (
            await self.db["stock_financial_data"]
            .find(
                {
                    "symbol": symbol,
                    "market": "CN",
                    "report_period": {"$lte": _business_timestamp(trade_date)},
                    "published_at": {"$lte": cutoff_at},
                }
            )
            .sort([("report_period", 1), ("published_at", 1)])
            .to_list(length=None)
        )
        news = (
            await self.db["stock_news"]
            .find(
                {
                    "symbol": symbol,
                    "market": "CN",
                    "published_at": {"$lte": cutoff_at},
                }
            )
            .sort("published_at", -1)
            .limit(100)
            .to_list(length=100)
        )
        news.reverse()
        announcements = (
            await self.db["stock_announcements"]
            .find(
                {
                    "symbol": symbol,
                    "market": "CN",
                    "published_at": {"$lte": cutoff_at},
                }
            )
            .sort("published_at", -1)
            .limit(200)
            .to_list(length=200)
        )
        announcements.reverse()
        calendar = (
            await self.db["trading_calendar"]
            .find(
                {
                    "market": "CN",
                    "session_date": {
                        "$gte": _business_timestamp(trade_date - timedelta(days=120)),
                        "$lte": _business_timestamp(trade_date + timedelta(days=60)),
                    },
                    "as_of": {"$lte": cutoff_at},
                }
            )
            .sort("session_date", 1)
            .to_list(length=None)
        )
        market_context_policy = production_market_context_policy()
        market_context = (
            await self.db["ag_market_contexts"]
            .find(
                {
                    "market": "CN",
                    "trade_date": _business_timestamp(trade_date),
                    "calculation_status": "READY",
                    "calculation_version": market_context_policy[
                        "calculation_version"
                    ],
                    "available_at": {"$lte": cutoff_at},
                    "collected_at": {"$lte": cutoff_at},
                }
            )
            .limit(2)
            .to_list(length=2)
        )
        if len(market_context) > 1:
            raise RealDataIntegrityConflict(
                "production MarketContext identity is ambiguous"
            )

        def refs(prefix: str, documents: list[dict[str, Any]]) -> list[str]:
            return [
                f"{prefix}:{document['ref_id']}"
                for document in documents
                if document.get("ref_id")
            ]

        raw_refs = {
            "prices": refs("stock_daily_quotes", prices),
            "benchmark_prices": refs("index_daily", benchmark),
            "financials": refs("stock_financial_data", financials),
            "news": refs("stock_news", news),
            "announcements": refs("stock_announcements", announcements),
            "market_context": refs("market_context", market_context),
            "trading_calendar": refs("trading_calendar", calendar),
        }
        report = await DataQualityGate().evaluate(
            db=self.db,
            symbol=symbol,
            market="CN",
            trade_date=trade_date,
            price_cutoff_at=cutoff_at,
            news_cutoff_at=cutoff_at,
            announcement_cutoff_at=cutoff_at,
            raw_refs=raw_refs,
        )
        versions = {
            "price_data_version": price_version or None,
            "benchmark_data_version": benchmark_version or None,
            "financial_data_version": (
                str(financials[-1].get("data_version")) if financials else None
            ),
            "news_data_version": (
                str(news[-1].get("data_version")) if news else None
            ),
            "announcement_data_version": (
                str(announcements[-1].get("data_version"))
                if announcements
                else None
            ),
            "market_context_data_version": (
                str(market_context[-1].get("data_version"))
                if market_context
                else None
            ),
        }
        return {
            "symbol": symbol,
            "market": "CN",
            "name": str(
                instrument.get("name") or instrument.get("stock_name") or ""
            ),
            "trade_date": trade_date,
            "cutoff_at": cutoff_at,
            "data_quality": report.model_dump(mode="python"),
            "raw_refs": raw_refs,
            "reference_counts": {
                key: len(value) for key, value in raw_refs.items()
            },
            "versions": versions,
            "snapshot_preconditions": {
                "price_target_exists": target is not None,
                "benchmark_target_exists": benchmark_target is not None,
                "market_context_exists": bool(market_context),
                "calendar_visible_at_cutoff": bool(calendar),
            },
        }
