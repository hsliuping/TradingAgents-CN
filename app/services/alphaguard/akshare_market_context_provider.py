"""AKShare/Tencent fallback for production MarketContext source data.

BaoStock is used once for the actual-date A-share universe.  Daily histories
come from AKShare's Tencent historical-daily interface with bounded
parallelism.  No realtime snapshot or research collection is read.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import math
import socket
import statistics
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable

from app.services.alphaguard.historical_market_context_service import (
    HistoricalMarketContextError,
    HistoricalMarketFetchResult,
    _business_close,
    _decimal,
    _is_a_share,
    _number,
)
from tradingagents.alphaguard.backfill_schemas import backfill_hash


class AKShareTencentMarketContextProvider:
    name = "akshare-tencent"

    @staticmethod
    def capability_check() -> dict[str, Any]:
        try:
            import akshare as ak
            import baostock as bs

            available = callable(getattr(ak, "stock_zh_a_hist_tx", None))
            return {
                "provider": "akshare-tencent",
                "underlying_source": "AKShare/Tencent",
                "universe_source": "BaoStock/query_all_stock",
                "available": available,
                "provider_version": str(
                    getattr(ak, "__version__", "unknown")
                ),
                "universe_provider_version": str(
                    getattr(bs, "__version__", "unknown")
                ),
                "capabilities": [
                    "HISTORICAL_A_SHARE_UNIVERSE",
                    "HISTORICAL_DAILY_BREADTH",
                    "HISTORICAL_SECTOR_INDEXES",
                ],
                "error_type": None if available else "INTERFACE_MISSING",
            }
        except Exception as exc:
            return {
                "provider": "akshare-tencent",
                "underlying_source": "AKShare/Tencent",
                "available": False,
                "error_type": type(exc).__name__,
            }

    @staticmethod
    def _query_baostock_rows(result: Any) -> list[dict[str, str]]:
        rows = []
        while result.error_code == "0" and result.next():
            rows.append(dict(zip(result.fields, result.get_row_data())))
        if result.error_code != "0":
            raise HistoricalMarketContextError(
                "BaoStock universe query failed"
            )
        return rows

    @staticmethod
    def _tx_code(code: str) -> str:
        return code.replace(".", "")

    @classmethod
    def _history(
        cls,
        *,
        code: str,
        start: date,
        end: date,
        timeout_seconds: float,
        attempts: int,
    ) -> list[dict[str, Any]]:
        import akshare as ak

        error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                frame = ak.stock_zh_a_hist_tx(
                    symbol=cls._tx_code(code),
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="",
                    timeout=timeout_seconds,
                )
                if frame is None:
                    return []
                rows = frame.to_dict(orient="records")
                return [
                    {
                        "date": str(item.get("date"))[:10],
                        "code": code,
                        "open": item.get("open"),
                        "high": item.get("high"),
                        "low": item.get("low"),
                        "close": item.get("close"),
                        "volume": item.get("volume"),
                        "amount": item.get("amount"),
                    }
                    for item in rows
                ]
            except Exception as exc:
                error = exc
                if attempt < attempts:
                    time_module.sleep(min(attempt, 2))
        raise HistoricalMarketContextError(
            f"AKShare/Tencent history {code} failed after {attempts}: "
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
            raise HistoricalMarketContextError(
                "AKShare/Tencent market provider unavailable"
            )
        context_policy = policy["market_context"]
        # AKShare's Tencent adapter emits one tqdm bar per symbol.  Disable
        # only that process-local presentation hook; requests and parsed
        # business values are unchanged.
        try:
            tx_module = importlib.import_module(
                "akshare.stock_feature.stock_hist_tx"
            )
            tx_module.get_tqdm = lambda: (
                lambda iterable, **_kwargs: iterable
            )
            # The requested window is already bounded and later validated
            # against the actual-date universe.  AKShare otherwise performs
            # an extra unbounded "first trading day" request per symbol before
            # every daily-history request.  Bypass only that discovery call;
            # stock_zh_a_hist_tx remains the source of every daily bar.
            tx_module.get_tx_start_year = lambda **_kwargs: "19000101"
        except (ImportError, AttributeError):
            pass
        provider_version = str(capability["provider_version"])
        universe_version = str(capability["universe_provider_version"])
        normalization = str(context_policy["normalization_version"])
        attempts = int(context_policy["query_retry_attempts"])
        timeout_seconds = float(context_policy["socket_timeout_seconds"])
        rolling = int(context_policy["rolling_high_low_sessions"])
        amount_sessions = int(context_policy["amount_ratio_sessions"])
        workers = int(context_policy.get("fallback_parallelism", 8))
        history_start = min(selected_dates) - timedelta(
            days=int(context_policy["history_buffer_calendar_days"])
        )
        history_end = max(selected_dates)
        selected = set(selected_dates)
        failures: list[dict[str, str]] = []

        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout_seconds)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                login = bs.login()
            if login.error_code != "0":
                raise HistoricalMarketContextError(
                    "BaoStock universe login failed"
                )
            try:
                universe_by_date: dict[date, dict[str, str]] = {}
                for index, trade_date in enumerate(selected_dates, start=1):
                    rows = cls._query_baostock_rows(
                        bs.query_all_stock(day=trade_date.isoformat())
                    )
                    universe_by_date[trade_date] = {
                        str(item["code"]): str(
                            item.get("tradeStatus") or ""
                        )
                        for item in rows
                        if _is_a_share(str(item.get("code") or ""))
                    }
                    if progress:
                        progress(
                            {
                                "stage": "TENCENT_UNIVERSE",
                                "completed": index,
                                "total": len(selected_dates),
                                "trade_date": trade_date.isoformat(),
                            }
                        )
            finally:
                with contextlib.redirect_stdout(io.StringIO()):
                    bs.logout()
        finally:
            socket.setdefaulttimeout(previous_timeout)

        union_codes = sorted(
            {code for values in universe_by_date.values() for code in values}
        )
        histories: dict[str, list[dict[str, Any]]] = {}
        last_progress = time_module.monotonic()
        with ThreadPoolExecutor(max_workers=max(1, min(workers, 32))) as pool:
            future_by_code = {
                pool.submit(
                    cls._history,
                    code=code,
                    start=history_start,
                    end=history_end,
                    timeout_seconds=timeout_seconds,
                    attempts=attempts,
                ): code
                for code in union_codes
            }
            for completed, future in enumerate(
                as_completed(future_by_code), start=1
            ):
                code = future_by_code[future]
                try:
                    histories[code] = future.result()
                except Exception as exc:
                    failures.append(
                        {
                            "scope": code,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)[:300],
                        }
                    )
                if (
                    completed == len(future_by_code)
                    or completed % 250 == 0
                    or time_module.monotonic() - last_progress >= 60
                ):
                    if progress:
                        progress(
                            {
                                "stage": "TENCENT_DAILY_BREADTH",
                                "completed": completed,
                                "total": len(future_by_code),
                                "code": code,
                                "failure_count": len(failures),
                            }
                        )
                    last_progress = time_module.monotonic()

        records_by_date: dict[date, list[dict[str, Any]]] = {
            item: [] for item in selected_dates
        }
        response_hashes_by_date: dict[date, dict[str, str]] = {
            item: {} for item in selected_dates
        }
        amount_by_date: dict[date, Decimal] = {}
        for code, rows in histories.items():
            response_hash = backfill_hash(rows)
            dated_rows = []
            for row in rows:
                try:
                    row_date = date.fromisoformat(str(row.get("date")))
                except ValueError:
                    continue
                dated_rows.append((row_date, row))
                amount = _decimal(row.get("amount"))
                if amount is not None:
                    amount_by_date[row_date] = (
                        amount_by_date.get(row_date, Decimal("0")) + amount
                    )
            dated_rows.sort(key=lambda item: item[0])
            closes: list[float] = []
            for row_date, row in dated_rows:
                close = _number(row.get("close"))
                prior = closes[-rolling:]
                if row_date in selected and code in universe_by_date[row_date]:
                    previous = closes[-1] if closes else None
                    pct = (
                        (close / previous - 1) * 100
                        if close is not None and previous
                        else None
                    )
                    records_by_date[row_date].append(
                        {
                            "source_record_id": (
                                f"AKShare/Tencent:{cls._tx_code(code)}:"
                                f"{row_date.isoformat()}:daily"
                            ),
                            "code": code,
                            "trade_status": universe_by_date[row_date][code],
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

        sector_codes = [
            str(item) for item in context_policy["sector_index_codes"]
        ]
        sector_by_date: dict[date, list[dict[str, Any]]] = {
            item: [] for item in selected_dates
        }
        for code in sector_codes:
            try:
                rows = cls._history(
                    code=code,
                    start=history_start,
                    end=history_end,
                    timeout_seconds=timeout_seconds,
                    attempts=attempts,
                )
                response_hash = backfill_hash(rows)
                closes = []
                for row in rows:
                    try:
                        row_date = date.fromisoformat(str(row.get("date")))
                    except ValueError:
                        continue
                    close = _number(row.get("close"))
                    previous = closes[-1] if closes else None
                    if row_date in selected:
                        sector_by_date[row_date].append(
                            {
                                "source_record_id": (
                                    f"AKShare/Tencent:{cls._tx_code(code)}:"
                                    f"{row_date.isoformat()}:sector-index"
                                ),
                                "code": code,
                                "pct_change": (
                                    (close / previous - 1) * 100
                                    if close is not None and previous
                                    else None
                                ),
                                "response_hash": response_hash,
                            }
                        )
                    if close is not None and close > 0:
                        closes.append(close)
            except Exception as exc:
                failures.append(
                    {
                        "scope": code,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:300],
                    }
                )
        if progress:
            progress(
                {
                    "stage": "TENCENT_SECTOR_INDEXES",
                    "completed": len(sector_codes),
                    "total": len(sector_codes),
                    "failure_count": len(failures),
                }
            )

        amount_dates = sorted(amount_by_date)
        min_universe = Decimal(
            str(context_policy["minimum_universe_coverage"])
        )
        min_high_low = Decimal(
            str(context_policy["minimum_high_low_coverage"])
        )
        min_sector = Decimal(
            str(context_policy["minimum_sector_coverage"])
        )
        source_payloads: dict[date, dict[str, Any]] = {}
        context_payloads: dict[date, dict[str, Any]] = {}
        for trade_date in selected_dates:
            rows = sorted(
                records_by_date[trade_date], key=lambda item: item["code"]
            )
            expected = len(universe_by_date.get(trade_date, {}))
            coverage = (
                Decimal(len(rows)) / Decimal(expected)
                if expected
                else Decimal("0")
            )
            valid_high_low = sum(
                item["new_high_20"] is not None
                and item["new_low_20"] is not None
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
            sector_coverage = (
                Decimal(len(valid_sectors)) / Decimal(len(sector_codes))
            )
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
            prior_amount_dates = [
                item for item in amount_dates if item < trade_date
            ][-amount_sessions:]
            amount_window = [
                {"trade_date": item, "total_amount": amount_by_date[item]}
                for item in prior_amount_dates
            ]
            amount_ratio = None
            if current_amount is not None and len(amount_window) == amount_sessions:
                average = sum(
                    (
                        item["total_amount"]
                        for item in amount_window
                    ),
                    Decimal("0"),
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
            source_response_hashes = {
                **response_hashes_by_date[trade_date],
                **{
                    item["code"]: item["response_hash"]
                    for item in sectors
                    if item.get("response_hash")
                },
                "universe": backfill_hash(universe_by_date[trade_date]),
            }
            source_content = {
                "market": "CN",
                "trade_date": trade_date,
                "provider": "akshare-tencent",
                "provider_version": provider_version,
                "underlying_source": "AKShare/Tencent",
                "normalization_version": normalization,
                "source_record_count": len(rows),
                "expected_universe_count": expected,
                "normalized_records": rows,
                "market_amount_window": amount_window,
                "sector_records": sectors,
                "source_response_hashes": source_response_hashes,
                "universe_provider": "baostock",
                "universe_provider_version": universe_version,
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
                "provider": "akshare-tencent",
                "provider_version": provider_version,
                "data_version": (
                    f"akshare:{provider_version}:TENCENT:"
                    f"MARKET_CONTEXT:{normalization}"
                ),
                "advance_count": advances,
                "decline_count": declines,
                "unchanged_count": unchanged,
                "total_amount": current_amount,
                "amount_ratio20": amount_ratio,
                "new_high_count": new_highs if valid_high_low else None,
                "new_low_count": new_lows if valid_high_low else None,
                "industry_diffusion": industry_diffusion,
                # ProductionMarketContextService combines these actual-market
                # breadth inputs with version-locked persisted CSI300
                # volatility.  The provider must not assert a safe value when
                # it does not own the benchmark inputs.
                "extreme_risk_flag": None,
                "universe_coverage": coverage,
                "high_low_coverage": high_low_coverage,
                "sector_coverage": sector_coverage,
                "calculation_status": (
                    "READY" if not missing else "INSUFFICIENT_DATA"
                ),
                "missing_fields": sorted(set(missing)),
                "methodology": {
                    "breadth": (
                        "actual-date BaoStock A-share universe plus "
                        "AKShare/Tencent historical daily bars"
                    ),
                    "amount_ratio20": (
                        "current total amount / previous 20 open-session mean"
                    ),
                    "new_high_low": (
                        "close versus previous 20 observed closes"
                    ),
                    "industry_diffusion": (
                        "positive share of ten historical exchange sector indices"
                    ),
                    "extreme_risk": (
                        "calculated by ProductionMarketContextService from "
                        "persisted CSI300 volatility and this full-market breadth"
                    ),
                },
            }
        return HistoricalMarketFetchResult(
            provider="akshare-tencent",
            provider_version=provider_version,
            normalization_version=normalization,
            source_payloads=source_payloads,
            context_payloads=context_payloads,
            failures=tuple(failures),
        )
