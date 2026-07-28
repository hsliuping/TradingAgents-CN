"""Versioned historical CN market breadth for research-only backfill."""

from __future__ import annotations

import asyncio
import math
import socket
import statistics
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Callable, Protocol
from uuid import NAMESPACE_URL, uuid5

from bson import BSON

from app.services.alphaguard.historical_backfill_config import backfill_policy
from app.services.alphaguard.paper_storage import clean_document, model_document
from app.services.alphaguard.quant_config import regime_config
from tradingagents.alphaguard.backfill_schemas import (
    HistoricalMarketContext,
    HistoricalMarketContextSource,
    backfill_hash,
)


class HistoricalMarketContextError(RuntimeError):
    pass


class HistoricalMarketContextConflict(HistoricalMarketContextError):
    pass


def _number(value: Any) -> float | None:
    if value in (None, "", "None", "nan", "--"):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _decimal(value: Any) -> Decimal | None:
    number = _number(value)
    return Decimal(str(number)) if number is not None else None


def _is_a_share(code: str) -> bool:
    return code.startswith(
        (
            "sh.600",
            "sh.601",
            "sh.603",
            "sh.605",
            "sh.688",
            "sh.689",
            "sz.000",
            "sz.001",
            "sz.002",
            "sz.003",
            "sz.300",
            "sz.301",
        )
    )


def _business_close(value: date) -> datetime:
    return datetime.combine(value, time(15, 0))


@dataclass(frozen=True)
class HistoricalMarketFetchResult:
    provider: str
    provider_version: str
    normalization_version: str
    source_payloads: dict[date, dict[str, Any]]
    context_payloads: dict[date, dict[str, Any]]
    failures: tuple[dict[str, str], ...]


class HistoricalMarketProvider(Protocol):
    name: str

    def capability_check(self) -> dict[str, Any]: ...

    def fetch(
        self,
        *,
        selected_dates: list[date],
        policy: dict[str, Any],
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> HistoricalMarketFetchResult: ...


class BaoStockHistoricalMarketProvider:
    """Fetch breadth from each date's actual A-share universe.

    Industry diffusion uses ten historical exchange sector indices.  It does
    not backfill current constituent mappings into the past.
    """

    name = "baostock"

    @staticmethod
    def capability_check() -> dict[str, Any]:
        try:
            import baostock as bs

            return {
                "provider": "baostock",
                "available": True,
                "provider_version": getattr(bs, "__version__", "unknown"),
                "capabilities": [
                    "HISTORICAL_A_SHARE_UNIVERSE",
                    "HISTORICAL_DAILY_BREADTH",
                    "HISTORICAL_SECTOR_INDEXES",
                ],
            }
        except Exception as exc:
            return {
                "provider": "baostock",
                "available": False,
                "error_type": type(exc).__name__,
            }

    @staticmethod
    def _query_rows(result: Any, *, label: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        while result.error_code == "0" and result.next():
            rows.append(dict(zip(result.fields, result.get_row_data())))
        if result.error_code != "0":
            raise HistoricalMarketContextError(
                f"BaoStock {label} failed with provider error"
            )
        return rows

    @classmethod
    def _retry(cls, callback, *, label: str, attempts: int):
        error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return callback()
            except Exception as exc:
                error = exc
                if attempt < attempts:
                    time_module.sleep(min(attempt, 2))
        raise HistoricalMarketContextError(
            f"BaoStock {label} failed after {attempts} attempts: "
            f"{type(error).__name__ if error else 'UNKNOWN'}"
        ) from error

    @classmethod
    def fetch(
        cls,
        *,
        selected_dates: list[date],
        policy: dict[str, Any],
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> HistoricalMarketFetchResult:
        import baostock as bs

        if not selected_dates:
            raise ValueError("selected_dates cannot be empty")
        capability = cls.capability_check()
        if capability.get("available") is not True:
            raise HistoricalMarketContextError("BaoStock is unavailable")
        provider_version = str(capability["provider_version"])
        context_policy = policy["market_context"]
        normalization = str(context_policy["normalization_version"])
        attempts = int(context_policy["query_retry_attempts"])
        socket_timeout = float(context_policy["socket_timeout_seconds"])
        delay = float(context_policy["query_delay_seconds"])
        rolling = int(context_policy["rolling_high_low_sessions"])
        amount_sessions = int(context_policy["amount_ratio_sessions"])
        history_start = min(selected_dates) - timedelta(
            days=int(context_policy["history_buffer_calendar_days"])
        )
        history_end = max(selected_dates)
        selected = set(selected_dates)
        failures: list[dict[str, str]] = []

        previous_socket_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(socket_timeout)
        try:
            login = bs.login()
            if login.error_code != "0":
                raise HistoricalMarketContextError("BaoStock login failed")
        except Exception:
            socket.setdefaulttimeout(previous_socket_timeout)
            raise
        try:
            universe_by_date: dict[date, dict[str, str]] = {}
            for date_index, trade_date in enumerate(selected_dates, start=1):
                try:
                    rows = cls._retry(
                        lambda d=trade_date: cls._query_rows(
                            bs.query_all_stock(day=d.isoformat()),
                            label=f"all-stock {d.isoformat()}",
                        ),
                        label=f"all-stock {trade_date.isoformat()}",
                        attempts=attempts,
                    )
                    universe_by_date[trade_date] = {
                        str(item["code"]): str(item.get("tradeStatus") or "")
                        for item in rows
                        if _is_a_share(str(item.get("code") or ""))
                    }
                except Exception as exc:
                    universe_by_date[trade_date] = {}
                    failures.append(
                        {
                            "scope": trade_date.isoformat(),
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)[:300],
                        }
                    )
                if progress is not None:
                    progress(
                        {
                            "stage": "HISTORICAL_UNIVERSE",
                            "completed": date_index,
                            "total": len(selected_dates),
                            "trade_date": trade_date.isoformat(),
                        }
                    )
            union_codes = sorted(
                {code for values in universe_by_date.values() for code in values}
            )
            records_by_date: dict[date, list[dict[str, Any]]] = {
                item: [] for item in selected_dates
            }
            response_hashes_by_date: dict[date, dict[str, str]] = {
                item: {} for item in selected_dates
            }
            amount_by_date: dict[date, Decimal] = {}
            fields = (
                "date,code,close,preclose,volume,amount,pctChg,"
                "tradestatus,isST"
            )
            last_progress_at = time_module.monotonic()
            for index, code in enumerate(union_codes, start=1):
                try:
                    rows = cls._retry(
                        lambda c=code: cls._query_rows(
                            bs.query_history_k_data_plus(
                                c,
                                fields,
                                start_date=history_start.isoformat(),
                                end_date=history_end.isoformat(),
                                frequency="d",
                                adjustflag="3",
                            ),
                            label=f"history {c}",
                        ),
                        label=f"history {code}",
                        attempts=attempts,
                    )
                except Exception as exc:
                    failures.append(
                        {
                            "scope": code,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)[:300],
                        }
                    )
                    continue
                response_hash = backfill_hash(rows)
                dated_rows: list[tuple[date, dict[str, str]]] = []
                for row in rows:
                    try:
                        row_date = date.fromisoformat(str(row.get("date")))
                    except ValueError:
                        continue
                    dated_rows.append((row_date, row))
                    amount = _decimal(row.get("amount"))
                    if amount is not None and str(row.get("tradestatus")) == "1":
                        amount_by_date[row_date] = (
                            amount_by_date.get(row_date, Decimal("0")) + amount
                        )
                dated_rows.sort(key=lambda item: item[0])
                closes: list[float] = []
                for row_date, row in dated_rows:
                    close = _number(row.get("close"))
                    prior = closes[-rolling:]
                    if row_date in selected and code in universe_by_date[row_date]:
                        pct = _number(row.get("pctChg"))
                        previous = _number(row.get("preclose"))
                        if pct is None and close is not None and previous:
                            pct = (close / previous - 1) * 100
                        records_by_date[row_date].append(
                            {
                                "source_record_id": (
                                    f"{code}:{row_date.isoformat()}:daily"
                                ),
                                "code": code,
                                "trade_status": str(row.get("tradestatus") or ""),
                                "pct_change": pct,
                                "amount": _decimal(row.get("amount")),
                                "close": close,
                                "new_high_20": (
                                    close >= max(prior)
                                    if close is not None and len(prior) == rolling
                                    else None
                                ),
                                "new_low_20": (
                                    close <= min(prior)
                                    if close is not None and len(prior) == rolling
                                    else None
                                ),
                            }
                        )
                        response_hashes_by_date[row_date][code] = response_hash
                    if close is not None and close > 0:
                        closes.append(close)
                if delay > 0 and index < len(union_codes):
                    time_module.sleep(delay)
                progress_due = (
                    index == len(union_codes)
                    or index % 250 == 0
                    or time_module.monotonic() - last_progress_at >= 60
                )
                if progress is not None and progress_due:
                    progress(
                        {
                            "stage": "HISTORICAL_DAILY_BREADTH",
                            "completed": index,
                            "total": len(union_codes),
                            "code": code,
                            "failure_count": len(failures),
                        }
                    )
                    last_progress_at = time_module.monotonic()

            sector_codes = [str(item) for item in context_policy["sector_index_codes"]]
            sector_by_date: dict[date, list[dict[str, Any]]] = {
                item: [] for item in selected_dates
            }
            for code in sector_codes:
                try:
                    rows = cls._retry(
                        lambda c=code: cls._query_rows(
                            bs.query_history_k_data_plus(
                                c,
                                "date,code,close,preclose,pctChg,tradestatus",
                                start_date=history_start.isoformat(),
                                end_date=history_end.isoformat(),
                                frequency="d",
                                adjustflag="3",
                            ),
                            label=f"sector {c}",
                        ),
                        label=f"sector {code}",
                        attempts=attempts,
                    )
                    response_hash = backfill_hash(rows)
                    for row in rows:
                        try:
                            row_date = date.fromisoformat(str(row.get("date")))
                        except ValueError:
                            continue
                        if row_date not in selected:
                            continue
                        pct = _number(row.get("pctChg"))
                        close = _number(row.get("close"))
                        previous = _number(row.get("preclose"))
                        if pct is None and close is not None and previous:
                            pct = (close / previous - 1) * 100
                        sector_by_date[row_date].append(
                            {
                                "source_record_id": (
                                    f"{code}:{row_date.isoformat()}:sector-index"
                                ),
                                "code": code,
                                "pct_change": pct,
                                "response_hash": response_hash,
                            }
                        )
                except Exception as exc:
                    failures.append(
                        {
                            "scope": code,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)[:300],
                        }
                    )
            if progress is not None:
                progress(
                    {
                        "stage": "HISTORICAL_SECTOR_INDEXES",
                        "completed": len(sector_codes),
                        "total": len(sector_codes),
                        "failure_count": len(failures),
                    }
                )

            benchmark_rows = cls._retry(
                lambda: cls._query_rows(
                    bs.query_history_k_data_plus(
                        "sh.000300",
                        "date,code,close,preclose,pctChg,tradestatus",
                        start_date=history_start.isoformat(),
                        end_date=history_end.isoformat(),
                        frequency="d",
                        adjustflag="3",
                    ),
                    label="CSI300 history",
                ),
                label="CSI300 history",
                attempts=attempts,
            )
        finally:
            bs.logout()
            socket.setdefaulttimeout(previous_socket_timeout)

        benchmark_closes: dict[date, float] = {}
        for row in benchmark_rows:
            try:
                row_date = date.fromisoformat(str(row.get("date")))
            except ValueError:
                continue
            value = _number(row.get("close"))
            if value is not None and value > 0:
                benchmark_closes[row_date] = value

        amount_dates = sorted(amount_by_date)
        source_payloads: dict[date, dict[str, Any]] = {}
        context_payloads: dict[date, dict[str, Any]] = {}
        thresholds = regime_config()["thresholds"]
        min_universe = Decimal(str(context_policy["minimum_universe_coverage"]))
        min_high_low = Decimal(str(context_policy["minimum_high_low_coverage"]))
        min_sector = Decimal(str(context_policy["minimum_sector_coverage"]))
        for trade_date in selected_dates:
            rows = sorted(records_by_date[trade_date], key=lambda item: item["code"])
            expected = len(universe_by_date.get(trade_date, {}))
            coverage = (
                Decimal(len(rows)) / Decimal(expected)
                if expected
                else Decimal("0")
            )
            valid_high_low = sum(
                item["new_high_20"] is not None and item["new_low_20"] is not None
                for item in rows
            )
            high_low_coverage = (
                Decimal(valid_high_low) / Decimal(len(rows))
                if rows
                else Decimal("0")
            )
            sectors = sorted(
                sector_by_date[trade_date], key=lambda item: item["code"]
            )
            valid_sectors = [
                item for item in sectors if item.get("pct_change") is not None
            ]
            sector_coverage = Decimal(len(valid_sectors)) / Decimal(len(sector_codes))
            advances = sum(
                item["pct_change"] is not None and item["pct_change"] > 0
                for item in rows
            )
            declines = sum(
                item["pct_change"] is not None and item["pct_change"] < 0
                for item in rows
            )
            unchanged = sum(
                item["pct_change"] is not None and item["pct_change"] == 0
                for item in rows
            )
            current_amount = amount_by_date.get(trade_date)
            prior_amount_dates = [item for item in amount_dates if item < trade_date][
                -amount_sessions:
            ]
            amount_window = [
                {"trade_date": item, "total_amount": amount_by_date[item]}
                for item in prior_amount_dates
            ]
            amount_ratio = None
            if current_amount is not None and len(amount_window) == amount_sessions:
                average = sum(
                    (item["total_amount"] for item in amount_window), Decimal("0")
                ) / Decimal(amount_sessions)
                if average > 0:
                    amount_ratio = current_amount / average
            new_highs = sum(item["new_high_20"] is True for item in rows)
            new_lows = sum(item["new_low_20"] is True for item in rows)
            industry_diffusion = (
                Decimal(
                    sum(float(item["pct_change"]) > 0 for item in valid_sectors)
                )
                / Decimal(len(valid_sectors))
                if valid_sectors
                else None
            )
            breadth = (
                (advances - declines) / (advances + declines)
                if advances + declines
                else None
            )
            benchmark_dates = sorted(
                item for item in benchmark_closes if item <= trade_date
            )[-21:]
            volatility = None
            if len(benchmark_dates) == 21:
                values = [benchmark_closes[item] for item in benchmark_dates]
                returns = [
                    values[index] / values[index - 1] - 1
                    for index in range(1, len(values))
                ]
                volatility = statistics.stdev(returns) * math.sqrt(250)
            extreme = (
                volatility is not None
                and breadth is not None
                and volatility >= float(thresholds["extreme_volatility"])
                and breadth <= float(thresholds["breadth_collapse"])
            )
            source_response_hashes = {
                **response_hashes_by_date[trade_date],
                **{
                    item["code"]: item["response_hash"]
                    for item in sectors
                    if item.get("response_hash")
                },
                "sh.000300": backfill_hash(benchmark_rows),
            }
            source_content = {
                "market": "CN",
                "trade_date": trade_date,
                "provider": "baostock",
                "provider_version": provider_version,
                "normalization_version": normalization,
                "source_record_count": len(rows),
                "expected_universe_count": expected,
                "normalized_records": rows,
                "market_amount_window": amount_window,
                "sector_records": sectors,
                "source_response_hashes": source_response_hashes,
            }
            source_content["content_hash"] = backfill_hash(source_content)
            source_payloads[trade_date] = source_content
            missing: list[str] = []
            if not expected:
                missing.append("historical_universe")
            if coverage < min_universe:
                missing.append("universe_coverage")
            if advances + declines == 0:
                missing.append("advance_count/decline_count")
            if high_low_coverage < min_high_low:
                missing.append("new_high_low_coverage")
            if sector_coverage < min_sector or industry_diffusion is None:
                missing.append("industry_diffusion")
            context_payloads[trade_date] = {
                "market": "CN",
                "trade_date": trade_date,
                "available_at": _business_close(trade_date),
                "provider": "baostock",
                "provider_version": provider_version,
                "data_version": (
                    f"baostock:{provider_version}:MARKET_CONTEXT:{normalization}"
                ),
                "advance_count": advances,
                "decline_count": declines,
                "unchanged_count": unchanged,
                "total_amount": current_amount,
                "amount_ratio20": amount_ratio,
                "new_high_count": new_highs if valid_high_low else None,
                "new_low_count": new_lows if valid_high_low else None,
                "industry_diffusion": industry_diffusion,
                "extreme_risk_flag": bool(extreme),
                "universe_coverage": coverage,
                "high_low_coverage": high_low_coverage,
                "sector_coverage": sector_coverage,
                "calculation_status": (
                    "READY" if not missing else "INSUFFICIENT_DATA"
                ),
                "missing_fields": sorted(set(missing)),
                "methodology": {
                    "breadth": "actual-date A-share universe; unchanged excluded from engine denominator",
                    "amount_ratio20": "current total amount / previous 20 open-session mean",
                    "new_high_low": "close versus previous 20 observed closes",
                    "industry_diffusion": "positive share of ten historical exchange sector indices",
                    "extreme_risk": "existing market-regime-v1 volatility and breadth-collapse thresholds",
                },
            }
        return HistoricalMarketFetchResult(
            provider="baostock",
            provider_version=provider_version,
            normalization_version=normalization,
            source_payloads=source_payloads,
            context_payloads=context_payloads,
            failures=tuple(failures),
        )


class HistoricalMarketContextService:
    def __init__(self, db):
        self.db = db
        self.policy = backfill_policy()

    async def sync(
        self,
        *,
        selected_dates: list[date],
        provider: HistoricalMarketProvider | None = None,
        timeout_seconds: float = 3600,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        dates = sorted(set(selected_dates))
        if not dates:
            raise ValueError("historical MarketContext requires selected dates")
        provider = provider or BaoStockHistoricalMarketProvider()
        capability = provider.capability_check()
        if capability.get("available") is not True:
            raise HistoricalMarketContextError(
                f"provider unavailable: {capability.get('error_type', 'UNKNOWN')}"
            )
        fetched = await asyncio.wait_for(
            asyncio.to_thread(
                provider.fetch,
                selected_dates=dates,
                policy=self.policy,
                progress=progress,
            ),
            timeout=timeout_seconds,
        )
        created = reused = ready = insufficient = 0
        contexts: list[HistoricalMarketContext] = []
        collected_at = datetime.utcnow()
        for trade_date in dates:
            source_payload = dict(fetched.source_payloads[trade_date])
            source_identity = (
                f"CN:{trade_date}:{fetched.provider}:"
                f"{fetched.provider_version}:{fetched.normalization_version}"
            )
            source = HistoricalMarketContextSource(
                source_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"alphaguard:research-market-source:{source_identity}",
                    )
                ),
                collected_at=collected_at,
                **source_payload,
            )
            source_document = model_document(source)
            source_size = len(BSON.encode(source_document))
            if source_size >= 15_000_000:
                raise HistoricalMarketContextError(
                    "historical MarketContext source document approaches the "
                    f"MongoDB 16MB limit: {trade_date} bytes={source_size}"
                )
            stored_source = clean_document(
                await self.db["ag_research_market_context_sources"].find_one(
                    {
                        "market": "CN",
                        "trade_date": datetime.combine(trade_date, time()),
                        "provider": fetched.provider,
                        "provider_version": fetched.provider_version,
                        "normalization_version": fetched.normalization_version,
                    }
                )
            )
            if stored_source:
                existing_source = HistoricalMarketContextSource.model_validate(
                    stored_source
                )
                if existing_source.content_hash != source.content_hash:
                    raise HistoricalMarketContextConflict(
                        "same MarketContext source identity has different content"
                    )
                source = existing_source
                reused += 1
            else:
                await self.db["ag_research_market_context_sources"].insert_one(
                    source_document
                )
                created += 1

            context_payload = dict(fetched.context_payloads[trade_date])
            context_payload.update(
                source_record_id=source.source_id,
                source_refs=[f"research_market_context_source:{source.source_id}"],
            )
            context_payload["content_hash"] = backfill_hash(context_payload)
            context = HistoricalMarketContext(
                context_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        "alphaguard:research-market-context:"
                        f"CN:{trade_date}:{context_payload['data_version']}",
                    )
                ),
                created_at=collected_at,
                **context_payload,
            )
            stored_context = clean_document(
                await self.db["ag_research_market_contexts"].find_one(
                    {
                        "market": "CN",
                        "trade_date": datetime.combine(trade_date, time()),
                        "data_version": context.data_version,
                    }
                )
            )
            if stored_context:
                existing_context = HistoricalMarketContext.model_validate(
                    stored_context
                )
                if existing_context.content_hash != context.content_hash:
                    raise HistoricalMarketContextConflict(
                        "same MarketContext identity has different content"
                    )
                context = existing_context
            else:
                await self.db["ag_research_market_contexts"].insert_one(
                    model_document(context)
                )
            contexts.append(context)
            if context.calculation_status == "READY":
                ready += 1
            else:
                insufficient += 1
        event_payload = {
                "event_id": str(
                    uuid5(
                        NAMESPACE_URL,
                        "market-context-sync:"
                        f"{fetched.provider}:{fetched.provider_version}:"
                        f"{fetched.normalization_version}:{backfill_hash(dates)}",
                    )
                ),
                "event_type": "HISTORICAL_MARKET_CONTEXT_SYNCED",
                "selected_trade_dates": [datetime.combine(item, time()) for item in dates],
                "provider": fetched.provider,
                "provider_version": fetched.provider_version,
                "created": created,
                "reused": reused,
                "ready": ready,
                "insufficient": insufficient,
                "failure_count": len(fetched.failures),
                "failures": list(fetched.failures)[:100],
                "created_at": collected_at,
                "schema_version": "alphaguard-historical-backfill-v1",
            }
        await self.db["ag_research_backfill_events"].update_one(
            {"event_id": event_payload["event_id"]},
            {"$setOnInsert": event_payload},
            upsert=True,
        )
        return {
            "provider": fetched.provider,
            "provider_version": fetched.provider_version,
            "selected_date_count": len(dates),
            "created": created,
            "reused": reused,
            "ready": ready,
            "insufficient": insufficient,
            "failure_count": len(fetched.failures),
            "contexts": contexts,
        }
