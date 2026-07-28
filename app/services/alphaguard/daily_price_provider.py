"""Auditable daily-price providers and deterministic cross-provider resolution.

Provider responses are never production evidence.  They must first pass this
module's completed-daily-bar gate and then be persisted by
``IncrementalDailyPriceService`` before any AlphaGuard pipeline can read them.
"""

from __future__ import annotations

import contextlib
import io
import socket
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal, Protocol

from tradingagents.alphaguard.instruments import normalize_instrument

from .production_data_config import daily_price_provider_policy
from .real_data_ingestion_service import real_data_hash


PriceMode = Literal["RAW", "QFQ", "INDEX_UNADJUSTED_EQUIVALENT"]
ProbeStatus = Literal["VALID", "INSUFFICIENT_DATA", "INVALID", "ERROR"]


class DailyPriceProviderError(RuntimeError):
    pass


class DailyPriceIntegrityConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderCapability:
    provider_name: str
    provider_version: str
    underlying_source: str
    supports_market: tuple[str, ...]
    supports_equity_daily: bool
    supports_index_daily: bool
    supports_raw: bool
    supports_qfq: bool
    provides_volume: bool
    provides_amount: bool
    provides_provider_update_time: bool
    provides_source_record_id: bool
    network_required: bool
    available: bool
    error_type: str | None = None


@dataclass(frozen=True)
class NormalizedDailyPrice:
    market: Literal["CN"]
    symbol: str
    trade_date: date
    mode: PriceMode
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_shares: int
    amount_cny: Decimal
    provider: str
    provider_version: str
    underlying_source: str
    source_record_identity: str
    provider_update_time: datetime | None
    response_received_at: datetime
    update_time_verified: bool
    source_response_hash: str
    normalization_version: str
    volume_normalization_rule: str
    amount_normalization_rule: str
    content_hash: str


@dataclass(frozen=True)
class ProviderProbe:
    capability: ProviderCapability
    symbol: str
    trade_date: date
    mode: PriceMode
    status: ProbeStatus
    row_count: int
    returned_trade_dates: tuple[str, ...]
    response_received_at: datetime
    provider_update_time: datetime | None
    source_record_identity: str
    record: NormalizedDailyPrice | None
    failure_reason: str | None = None
    error_code: str | None = None
    error_type: str | None = None

    def report(self) -> dict[str, Any]:
        value = asdict(self)
        value["capability"] = asdict(self.capability)
        if self.record is not None:
            value["record"] = asdict(self.record)
        return value


@dataclass(frozen=True)
class ProviderResolution:
    symbol: str
    trade_date: date
    status: Literal["READY", "INSUFFICIENT_DATA", "INTEGRITY_CONFLICT"]
    primary_provider_key: str | None
    fallback_reason: str | None
    raw: NormalizedDailyPrice | None
    adjusted: NormalizedDailyPrice | None
    probes: tuple[ProviderProbe, ...]
    comparisons: tuple[dict[str, Any], ...]
    failure_reasons: tuple[str, ...]

    def report(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "status": self.status,
            "primary_provider_key": self.primary_provider_key,
            "fallback_reason": self.fallback_reason,
            "raw": asdict(self.raw) if self.raw else None,
            "adjusted": asdict(self.adjusted) if self.adjusted else None,
            "probes": [probe.report() for probe in self.probes],
            "comparisons": list(self.comparisons),
            "failure_reasons": list(self.failure_reasons),
        }


class DailyPriceProvider(Protocol):
    provider_key: str

    def capability_check(self) -> ProviderCapability: ...

    def probe(
        self,
        *,
        symbol: str,
        trade_date: date,
        mode: PriceMode,
    ) -> ProviderProbe: ...


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "None", "nan", "--"):
        return None
    try:
        result = Decimal(str(value))
    except Exception:
        return None
    return result if result.is_finite() else None


def _quantize(value: Decimal, quantum: str) -> Decimal:
    return value.quantize(Decimal(quantum), rounding=ROUND_HALF_UP)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _after_close(trade_date: date, at: datetime) -> bool:
    policy = daily_price_provider_policy()
    close_at = time.fromisoformat(str(policy["market_close_time"]))
    return at.date() > trade_date or (
        at.date() == trade_date and at.time() >= close_at
    )


def _normalize_record(
    *,
    capability: ProviderCapability,
    symbol: str,
    trade_date: date,
    mode: PriceMode,
    row: dict[str, Any],
    date_field: str,
    open_field: str,
    high_field: str,
    low_field: str,
    close_field: str,
    volume_field: str,
    amount_field: str,
    volume_multiplier: int,
    volume_rule: str,
    amount_multiplier: Decimal,
    amount_rule: str,
    response_received_at: datetime,
    source_record_identity: str,
    provider_update_time: datetime | None = None,
) -> tuple[NormalizedDailyPrice | None, str | None]:
    policy = daily_price_provider_policy()
    observed_date = _parse_date(row.get(date_field))
    if observed_date != trade_date:
        return None, "OLD_OR_WRONG_TRADE_DATE"
    values = {
        "open": _decimal(row.get(open_field)),
        "high": _decimal(row.get(high_field)),
        "low": _decimal(row.get(low_field)),
        "close": _decimal(row.get(close_field)),
        "volume": _decimal(row.get(volume_field)),
        "amount": _decimal(row.get(amount_field)),
    }
    if any(value is None for value in values.values()):
        missing = sorted(key for key, value in values.items() if value is None)
        return None, f"MISSING_FIELDS:{','.join(missing)}"
    open_price = _quantize(values["open"], str(policy["price_quantum"]))
    high_price = _quantize(values["high"], str(policy["price_quantum"]))
    low_price = _quantize(values["low"], str(policy["price_quantum"]))
    close_price = _quantize(values["close"], str(policy["price_quantum"]))
    volume = values["volume"] * volume_multiplier
    amount = values["amount"] * amount_multiplier
    if any(value <= 0 for value in (open_price, high_price, low_price, close_price)):
        return None, "NON_POSITIVE_OHLC"
    if not (low_price <= open_price <= high_price):
        return None, "OPEN_OUTSIDE_DAILY_RANGE"
    if not (low_price <= close_price <= high_price):
        return None, "CLOSE_OUTSIDE_DAILY_RANGE"
    if volume < 0 or amount < 0:
        return None, "NEGATIVE_VOLUME_OR_AMOUNT"
    if volume != volume.to_integral_value():
        return None, "NON_INTEGRAL_VOLUME_SHARES"
    if not _after_close(trade_date, response_received_at):
        return None, "RESPONSE_RECEIVED_BEFORE_MARKET_CLOSE"
    canonical = {
        "market": "CN",
        "symbol": symbol,
        "trade_date": trade_date,
        "mode": mode,
        "open": format(open_price, "f"),
        "high": format(high_price, "f"),
        "low": format(low_price, "f"),
        "close": format(close_price, "f"),
        "volume_shares": int(volume),
        "amount_cny": format(
            _quantize(amount, str(policy["amount_quantum_cny"])), "f"
        ),
        "provider": capability.provider_name,
        "provider_version": capability.provider_version,
        "underlying_source": capability.underlying_source,
        "source_record_identity": source_record_identity,
        "provider_update_time": provider_update_time,
        "update_time_verified": provider_update_time is not None,
        "normalization_version": policy["normalization_version"],
        "volume_normalization_rule": volume_rule,
        "amount_normalization_rule": amount_rule,
    }
    source_response_hash = real_data_hash(row)
    content_hash = real_data_hash(canonical)
    return (
        NormalizedDailyPrice(
            market="CN",
            symbol=symbol,
            trade_date=trade_date,
            mode=mode,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume_shares=int(volume),
            amount_cny=_quantize(
                amount, str(policy["amount_quantum_cny"])
            ),
            provider=capability.provider_name,
            provider_version=capability.provider_version,
            underlying_source=capability.underlying_source,
            source_record_identity=source_record_identity,
            provider_update_time=provider_update_time,
            response_received_at=response_received_at,
            update_time_verified=provider_update_time is not None,
            source_response_hash=source_response_hash,
            normalization_version=str(policy["normalization_version"]),
            volume_normalization_rule=volume_rule,
            amount_normalization_rule=amount_rule,
            content_hash=content_hash,
        ),
        None,
    )


def _empty_or_error_probe(
    *,
    capability: ProviderCapability,
    symbol: str,
    trade_date: date,
    mode: PriceMode,
    response_received_at: datetime,
    source_record_identity: str,
    status: ProbeStatus,
    row_count: int = 0,
    returned_trade_dates: tuple[str, ...] = (),
    failure_reason: str,
    error_code: str | None = None,
    error_type: str | None = None,
) -> ProviderProbe:
    return ProviderProbe(
        capability=capability,
        symbol=symbol,
        trade_date=trade_date,
        mode=mode,
        status=status,
        row_count=row_count,
        returned_trade_dates=returned_trade_dates,
        response_received_at=response_received_at,
        provider_update_time=None,
        source_record_identity=source_record_identity,
        record=None,
        failure_reason=failure_reason,
        error_code=error_code,
        error_type=error_type,
    )


class BaoStockDailyPriceProvider:
    provider_key = "BAOSTOCK"

    def __init__(self, *, timeout_seconds: float = 20):
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def capability_check() -> ProviderCapability:
        try:
            import baostock as bs

            return ProviderCapability(
                provider_name="baostock",
                provider_version=str(getattr(bs, "__version__", "unknown")),
                underlying_source="BaoStock",
                supports_market=("CN",),
                supports_equity_daily=True,
                supports_index_daily=True,
                supports_raw=True,
                supports_qfq=True,
                provides_volume=True,
                provides_amount=True,
                provides_provider_update_time=False,
                provides_source_record_id=False,
                network_required=True,
                available=True,
            )
        except Exception as exc:
            return ProviderCapability(
                provider_name="baostock",
                provider_version="unavailable",
                underlying_source="BaoStock",
                supports_market=("CN",),
                supports_equity_daily=True,
                supports_index_daily=True,
                supports_raw=True,
                supports_qfq=True,
                provides_volume=True,
                provides_amount=True,
                provides_provider_update_time=False,
                provides_source_record_id=False,
                network_required=True,
                available=False,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _code(symbol: str) -> str:
        return f"{'sh' if symbol.startswith('6') or symbol == '000300' else 'sz'}.{symbol}"

    def probe(
        self,
        *,
        symbol: str,
        trade_date: date,
        mode: PriceMode,
    ) -> ProviderProbe:
        capability = self.capability_check()
        source_identity = (
            f"BaoStock/query_history_k_data_plus/{self._code(symbol)}/"
            f"{trade_date.isoformat()}/daily/{mode}"
        )
        received = datetime.now()
        if not capability.available:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=received,
                source_record_identity=source_identity,
                status="ERROR",
                failure_reason="CAPABILITY_UNAVAILABLE",
                error_type=capability.error_type,
            )
        import baostock as bs

        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.timeout_seconds)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                login = bs.login()
            if login.error_code != "0":
                return _empty_or_error_probe(
                    capability=capability,
                    symbol=symbol,
                    trade_date=trade_date,
                    mode=mode,
                    response_received_at=datetime.now(),
                    source_record_identity=source_identity,
                    status="ERROR",
                    failure_reason="LOGIN_FAILED",
                    error_code=str(login.error_code),
                )
            try:
                adjustflag = "2" if mode == "QFQ" else "3"
                result = bs.query_history_k_data_plus(
                    self._code(symbol),
                    (
                        "date,code,open,high,low,close,preclose,volume,amount,"
                        "adjustflag,turn,tradestatus,pctChg,isST"
                    ),
                    start_date=trade_date.isoformat(),
                    end_date=trade_date.isoformat(),
                    frequency="d",
                    adjustflag=adjustflag,
                )
                rows: list[dict[str, Any]] = []
                while result.error_code == "0" and result.next():
                    rows.append(dict(zip(result.fields, result.get_row_data())))
                received = datetime.now()
                if result.error_code != "0":
                    return _empty_or_error_probe(
                        capability=capability,
                        symbol=symbol,
                        trade_date=trade_date,
                        mode=mode,
                        response_received_at=received,
                        source_record_identity=source_identity,
                        status="ERROR",
                        failure_reason=str(result.error_msg or "QUERY_FAILED"),
                        error_code=str(result.error_code),
                    )
            finally:
                with contextlib.redirect_stdout(io.StringIO()):
                    bs.logout()
        except Exception as exc:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=datetime.now(),
                source_record_identity=source_identity,
                status="ERROR",
                failure_reason=str(exc)[:300],
                error_type=type(exc).__name__,
            )
        finally:
            socket.setdefaulttimeout(previous_timeout)
        dates = tuple(
            sorted(
                {
                    str(item.get("date"))
                    for item in rows
                    if item.get("date") not in (None, "")
                }
            )
        )
        if len(rows) != 1:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=received,
                source_record_identity=source_identity,
                status="INSUFFICIENT_DATA",
                row_count=len(rows),
                returned_trade_dates=dates,
                failure_reason="EXACT_DAILY_ROW_NOT_RETURNED",
                error_code="0",
            )
        record, failure = _normalize_record(
            capability=capability,
            symbol=symbol,
            trade_date=trade_date,
            mode=mode,
            row=rows[0],
            date_field="date",
            open_field="open",
            high_field="high",
            low_field="low",
            close_field="close",
            volume_field="volume",
            amount_field="amount",
            volume_multiplier=1,
            volume_rule="BAOSTOCK_SHARES",
            amount_multiplier=Decimal("1"),
            amount_rule="BAOSTOCK_CNY",
            response_received_at=received,
            source_record_identity=source_identity,
        )
        return ProviderProbe(
            capability=capability,
            symbol=symbol,
            trade_date=trade_date,
            mode=mode,
            status="VALID" if record else "INVALID",
            row_count=1,
            returned_trade_dates=dates,
            response_received_at=received,
            provider_update_time=None,
            source_record_identity=source_identity,
            record=record,
            failure_reason=failure,
            error_code="0",
        )


class AKShareEastmoneyDailyPriceProvider:
    provider_key = "AKSHARE_EASTMONEY"

    def __init__(self, *, timeout_seconds: float = 20):
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def capability_check() -> ProviderCapability:
        try:
            import akshare as ak

            available = all(
                callable(getattr(ak, name, None))
                for name in ("stock_zh_a_hist", "index_zh_a_hist")
            )
            return ProviderCapability(
                provider_name="akshare",
                provider_version=str(getattr(ak, "__version__", "unknown")),
                underlying_source="AKShare/Eastmoney",
                supports_market=("CN",),
                supports_equity_daily=True,
                supports_index_daily=True,
                supports_raw=True,
                supports_qfq=True,
                provides_volume=True,
                provides_amount=True,
                provides_provider_update_time=False,
                provides_source_record_id=False,
                network_required=True,
                available=available,
                error_type=None if available else "INTERFACE_MISSING",
            )
        except Exception as exc:
            return ProviderCapability(
                provider_name="akshare",
                provider_version="unavailable",
                underlying_source="AKShare/Eastmoney",
                supports_market=("CN",),
                supports_equity_daily=True,
                supports_index_daily=True,
                supports_raw=True,
                supports_qfq=True,
                provides_volume=True,
                provides_amount=True,
                provides_provider_update_time=False,
                provides_source_record_id=False,
                network_required=True,
                available=False,
                error_type=type(exc).__name__,
            )

    def probe(
        self,
        *,
        symbol: str,
        trade_date: date,
        mode: PriceMode,
    ) -> ProviderProbe:
        capability = self.capability_check()
        endpoint = (
            "index_zh_a_hist"
            if symbol == "000300"
            else "stock_zh_a_hist"
        )
        source_identity = (
            f"AKShare/Eastmoney/{endpoint}/{symbol}/"
            f"{trade_date.isoformat()}/daily/{mode}"
        )
        if not capability.available:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=datetime.now(),
                source_record_identity=source_identity,
                status="ERROR",
                failure_reason="CAPABILITY_UNAVAILABLE",
                error_type=capability.error_type,
            )
        import akshare as ak

        try:
            if symbol == "000300":
                frame = ak.index_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=trade_date.strftime("%Y%m%d"),
                    end_date=trade_date.strftime("%Y%m%d"),
                )
            else:
                frame = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=trade_date.strftime("%Y%m%d"),
                    end_date=trade_date.strftime("%Y%m%d"),
                    adjust="qfq" if mode == "QFQ" else "",
                    timeout=self.timeout_seconds,
                )
            received = datetime.now()
        except Exception as exc:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=datetime.now(),
                source_record_identity=source_identity,
                status="ERROR",
                failure_reason=str(exc)[:300],
                error_type=type(exc).__name__,
            )
        rows = [] if frame is None else frame.to_dict(orient="records")
        dates = tuple(
            sorted(
                {
                    str(item.get("日期"))[:10]
                    for item in rows
                    if item.get("日期") is not None
                }
            )
        )
        if len(rows) != 1:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=received,
                source_record_identity=source_identity,
                status="INSUFFICIENT_DATA",
                row_count=len(rows),
                returned_trade_dates=dates,
                failure_reason="EXACT_DAILY_ROW_NOT_RETURNED",
            )
        record, failure = _normalize_record(
            capability=capability,
            symbol=symbol,
            trade_date=trade_date,
            mode=mode,
            row=rows[0],
            date_field="日期",
            open_field="开盘",
            high_field="最高",
            low_field="最低",
            close_field="收盘",
            volume_field="成交量",
            amount_field="成交额",
            volume_multiplier=100,
            volume_rule="EASTMONEY_HANDS_X100_TO_SHARES",
            amount_multiplier=Decimal("1"),
            amount_rule="EASTMONEY_CNY",
            response_received_at=received,
            source_record_identity=source_identity,
        )
        return ProviderProbe(
            capability=capability,
            symbol=symbol,
            trade_date=trade_date,
            mode=mode,
            status="VALID" if record else "INVALID",
            row_count=1,
            returned_trade_dates=dates,
            response_received_at=received,
            provider_update_time=None,
            source_record_identity=source_identity,
            record=record,
            failure_reason=failure,
        )


class AKShareTencentDailyPriceProvider:
    provider_key = "AKSHARE_TENCENT"

    def __init__(self, *, timeout_seconds: float = 20):
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def capability_check() -> ProviderCapability:
        try:
            import akshare as ak

            available = callable(getattr(ak, "stock_zh_a_hist_tx", None))
            return ProviderCapability(
                provider_name="akshare",
                provider_version=str(getattr(ak, "__version__", "unknown")),
                underlying_source="AKShare/Tencent",
                supports_market=("CN",),
                supports_equity_daily=True,
                supports_index_daily=True,
                supports_raw=True,
                supports_qfq=True,
                provides_volume=True,
                provides_amount=True,
                provides_provider_update_time=False,
                provides_source_record_id=False,
                network_required=True,
                available=available,
                error_type=None if available else "INTERFACE_MISSING",
            )
        except Exception as exc:
            return ProviderCapability(
                provider_name="akshare",
                provider_version="unavailable",
                underlying_source="AKShare/Tencent",
                supports_market=("CN",),
                supports_equity_daily=True,
                supports_index_daily=True,
                supports_raw=True,
                supports_qfq=True,
                provides_volume=True,
                provides_amount=True,
                provides_provider_update_time=False,
                provides_source_record_id=False,
                network_required=True,
                available=False,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _code(symbol: str) -> str:
        return f"{'sh' if symbol.startswith('6') or symbol == '000300' else 'sz'}{symbol}"

    def probe(
        self,
        *,
        symbol: str,
        trade_date: date,
        mode: PriceMode,
    ) -> ProviderProbe:
        capability = self.capability_check()
        code = self._code(symbol)
        source_identity = (
            f"AKShare/Tencent/stock_zh_a_hist_tx/{code}/"
            f"{trade_date.isoformat()}/daily/{mode}"
        )
        if not capability.available:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=datetime.now(),
                source_record_identity=source_identity,
                status="ERROR",
                failure_reason="CAPABILITY_UNAVAILABLE",
                error_type=capability.error_type,
            )
        import akshare as ak

        try:
            frame = ak.stock_zh_a_hist_tx(
                symbol=code,
                start_date=trade_date.strftime("%Y%m%d"),
                end_date=trade_date.strftime("%Y%m%d"),
                adjust="qfq" if mode == "QFQ" else "",
                timeout=self.timeout_seconds,
            )
            received = datetime.now()
        except Exception as exc:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=datetime.now(),
                source_record_identity=source_identity,
                status="ERROR",
                failure_reason=str(exc)[:300],
                error_type=type(exc).__name__,
            )
        rows = [] if frame is None else frame.to_dict(orient="records")
        dates = tuple(
            sorted(
                {
                    str(item.get("date"))[:10]
                    for item in rows
                    if item.get("date") is not None
                }
            )
        )
        if len(rows) != 1:
            return _empty_or_error_probe(
                capability=capability,
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
                response_received_at=received,
                source_record_identity=source_identity,
                status="INSUFFICIENT_DATA",
                row_count=len(rows),
                returned_trade_dates=dates,
                failure_reason="EXACT_DAILY_ROW_NOT_RETURNED",
            )
        # AKShare 1.18.78 documents this frame as shares/CNY, but its own
        # implementation skips the lots-to-shares conversion for sz000 and
        # sh000.  The patch is explicit, versioned, and covered against the
        # persisted BaoStock 2026-07-24 control sample.
        needs_patch = code.startswith(("sz000", "sh000"))
        record, failure = _normalize_record(
            capability=capability,
            symbol=symbol,
            trade_date=trade_date,
            mode=mode,
            row=rows[0],
            date_field="date",
            open_field="open",
            high_field="high",
            low_field="low",
            close_field="close",
            volume_field="volume",
            amount_field="amount",
            volume_multiplier=100 if needs_patch else 1,
            volume_rule=(
                "AKSHARE_TX_SZ000_SH000_HANDS_X100_PATCH_V1"
                if needs_patch
                else "AKSHARE_TX_DECLARED_SHARES"
            ),
            amount_multiplier=Decimal("1"),
            amount_rule="AKSHARE_TX_NORMALIZED_CNY",
            response_received_at=received,
            source_record_identity=source_identity,
        )
        return ProviderProbe(
            capability=capability,
            symbol=symbol,
            trade_date=trade_date,
            mode=mode,
            status="VALID" if record else "INVALID",
            row_count=1,
            returned_trade_dates=dates,
            response_received_at=received,
            provider_update_time=None,
            source_record_identity=source_identity,
            record=record,
            failure_reason=failure,
        )


class ProviderRegistry:
    def __init__(self, providers: list[DailyPriceProvider] | None = None):
        self.providers = providers or [
            BaoStockDailyPriceProvider(),
            AKShareEastmoneyDailyPriceProvider(),
            AKShareTencentDailyPriceProvider(),
        ]
        keys = [provider.provider_key for provider in self.providers]
        if len(keys) != len(set(keys)):
            raise ValueError("daily-price provider keys must be unique")

    def capabilities(self) -> list[ProviderCapability]:
        return [provider.capability_check() for provider in self.providers]


def _within(
    left: Decimal,
    right: Decimal,
    *,
    absolute: Decimal,
    relative: Decimal,
) -> tuple[bool, Decimal, Decimal]:
    difference = abs(left - right)
    base = max(abs(left), abs(right), Decimal("1"))
    allowed = max(absolute, base * relative)
    return difference <= allowed, difference, allowed


def compare_daily_prices(
    left: NormalizedDailyPrice,
    right: NormalizedDailyPrice,
) -> dict[str, Any]:
    if (left.symbol, left.trade_date, left.mode) != (
        right.symbol,
        right.trade_date,
        right.mode,
    ):
        return {
            "status": "MAJOR_CONFLICT",
            "failure_reason": "IDENTITY_MISMATCH",
        }
    policy = daily_price_provider_policy()
    raw_policy = policy["raw_cross_validation"]
    qfq_policy = policy["qfq_cross_validation"]
    fields: dict[str, Any] = {}
    conflict = False
    for field in ("open", "high", "low", "close"):
        tolerance = raw_policy if left.mode == "RAW" else qfq_policy
        valid, difference, allowed = _within(
            getattr(left, field),
            getattr(right, field),
            absolute=Decimal(str(tolerance["price_absolute_tolerance"])),
            relative=Decimal(str(tolerance["price_relative_tolerance"])),
        )
        fields[field] = {
            "left": format(getattr(left, field), "f"),
            "right": format(getattr(right, field), "f"),
            "absolute_difference": format(difference, "f"),
            "allowed_difference": format(allowed, "f"),
            "within_tolerance": valid,
        }
        conflict = conflict or not valid
    if left.mode == "RAW":
        valid, difference, allowed = _within(
            Decimal(left.volume_shares),
            Decimal(right.volume_shares),
            absolute=Decimal(
                str(raw_policy["volume_absolute_tolerance_shares"])
            ),
            relative=Decimal(str(raw_policy["volume_relative_tolerance"])),
        )
        fields["volume_shares"] = {
            "left": left.volume_shares,
            "right": right.volume_shares,
            "absolute_difference": int(difference),
            "allowed_difference": format(allowed, "f"),
            "within_tolerance": valid,
        }
        conflict = conflict or not valid
        valid, difference, allowed = _within(
            left.amount_cny,
            right.amount_cny,
            absolute=Decimal(
                str(raw_policy["amount_absolute_tolerance_cny"])
            ),
            relative=Decimal(str(raw_policy["amount_relative_tolerance"])),
        )
        fields["amount_cny"] = {
            "left": format(left.amount_cny, "f"),
            "right": format(right.amount_cny, "f"),
            "absolute_difference": format(difference, "f"),
            "allowed_difference": format(allowed, "f"),
            "within_tolerance": valid,
        }
        conflict = conflict or not valid
    differences = any(
        Decimal(str(item["absolute_difference"])) > 0
        for item in fields.values()
    )
    return {
        "left_provider": (
            f"{left.provider}/{left.underlying_source}/{left.provider_version}"
        ),
        "right_provider": (
            f"{right.provider}/{right.underlying_source}/{right.provider_version}"
        ),
        "symbol": left.symbol,
        "trade_date": left.trade_date,
        "mode": left.mode,
        "status": (
            "MAJOR_CONFLICT"
            if conflict
            else "DIFFERENCE_WITHIN_TOLERANCE"
            if differences
            else "MATCH"
        ),
        "tolerance_policy_version": str(policy["policy_version"]),
        "fields": fields,
    }


class DailyPriceProviderResolver:
    def __init__(self, registry: ProviderRegistry | None = None):
        self.registry = registry or ProviderRegistry()
        self.policy = daily_price_provider_policy()

    def resolve(
        self,
        *,
        symbol: str,
        trade_date: date,
    ) -> ProviderResolution:
        market, symbol = normalize_instrument(symbol, "CN")
        if market != "CN":
            raise ValueError("daily-price fallback supports CN only")
        index_mode = symbol == "000300"
        modes: tuple[PriceMode, ...] = (
            ("INDEX_UNADJUSTED_EQUIVALENT",)
            if index_mode
            else ("RAW", "QFQ")
        )
        probes = tuple(
            provider.probe(
                symbol=symbol,
                trade_date=trade_date,
                mode=mode,
            )
            for provider in self.registry.providers
            for mode in modes
        )
        valid_by_key: dict[str, dict[PriceMode, NormalizedDailyPrice]] = {}
        for provider in self.registry.providers:
            valid_by_key[provider.provider_key] = {
                probe.mode: probe.record
                for probe in probes
                if probe.capability.underlying_source
                == provider.capability_check().underlying_source
                and probe.status == "VALID"
                and probe.record is not None
            }
        comparisons: list[dict[str, Any]] = []
        for mode in modes:
            records = [
                values[mode]
                for values in valid_by_key.values()
                if mode in values
            ]
            for index, left in enumerate(records):
                for right in records[index + 1 :]:
                    comparisons.append(compare_daily_prices(left, right))
        if any(item["status"] == "MAJOR_CONFLICT" for item in comparisons):
            return ProviderResolution(
                symbol=symbol,
                trade_date=trade_date,
                status="INTEGRITY_CONFLICT",
                primary_provider_key=None,
                fallback_reason=None,
                raw=None,
                adjusted=None,
                probes=probes,
                comparisons=tuple(comparisons),
                failure_reasons=("CROSS_PROVIDER_MAJOR_CONFLICT",),
            )
        selected_key = None
        required_modes = set(modes)
        for key in self.policy["provider_priority"]:
            if required_modes.issubset(valid_by_key.get(str(key), {})):
                selected_key = str(key)
                break
        if selected_key is None:
            reasons = tuple(
                sorted(
                    {
                        (
                            f"{probe.capability.underlying_source}:"
                            f"{probe.mode}:{probe.failure_reason or probe.status}"
                        )
                        for probe in probes
                        if probe.status != "VALID"
                    }
                )
            )
            return ProviderResolution(
                symbol=symbol,
                trade_date=trade_date,
                status="INSUFFICIENT_DATA",
                primary_provider_key=None,
                fallback_reason=None,
                raw=None,
                adjusted=None,
                probes=probes,
                comparisons=tuple(comparisons),
                failure_reasons=reasons,
            )
        selected = valid_by_key[selected_key]
        ordered_keys = [
            str(key) for key in self.policy["provider_priority"]
        ]
        earlier = ordered_keys[: ordered_keys.index(selected_key)]
        fallback_reason = (
            None
            if selected_key == str(self.policy["provider_priority"][0])
            else "PRIMARY_PROVIDERS_NOT_READY:"
            + ",".join(earlier)
        )
        if index_mode:
            record = selected["INDEX_UNADJUSTED_EQUIVALENT"]
            return ProviderResolution(
                symbol=symbol,
                trade_date=trade_date,
                status="READY",
                primary_provider_key=selected_key,
                fallback_reason=fallback_reason,
                raw=record,
                adjusted=record,
                probes=probes,
                comparisons=tuple(comparisons),
                failure_reasons=(),
            )
        return ProviderResolution(
            symbol=symbol,
            trade_date=trade_date,
            status="READY",
            primary_provider_key=selected_key,
            fallback_reason=fallback_reason,
            raw=selected["RAW"],
            adjusted=selected["QFQ"],
            probes=probes,
            comparisons=tuple(comparisons),
            failure_reasons=(),
        )
