"""Versioned CN daily trading-status and price-limit derivation.

The service uses persisted provider facts plus an audited regulatory rule
version.  Unsupported or ambiguous cases remain ``INSUFFICIENT_DATA``.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.instruments import normalize_instrument
from tradingagents.alphaguard.production_data_schemas import (
    SecurityTradingStatus,
    production_data_hash,
)

from .production_data_config import cn_price_limit_policy


class TradingStatusError(RuntimeError):
    pass


class TradingStatusConflict(TradingStatusError):
    pass


def _business_timestamp(value: date, *, hour: int = 0) -> datetime:
    return datetime.combine(value, time(hour=hour))


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit() and len(text) == 8:
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return _business_timestamp(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except ValueError:
        return None


def _explicit_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().upper()
    if normalized in {"1", "TRUE", "Y", "YES", "ST", "SUSPENDED", "停牌"}:
        return True
    if normalized in {"0", "FALSE", "N", "NO", "NORMAL", "交易"}:
        return False
    return None


def _board(symbol: str, policy: dict[str, Any]) -> str:
    matches = []
    for board_name, definition in policy["boards"].items():
        if any(symbol.startswith(str(prefix)) for prefix in definition["prefixes"]):
            matches.append(str(board_name))
    if len(matches) != 1:
        return "UNKNOWN"
    return matches[0]


def _rounded_limit(
    previous_close: Decimal,
    rate: Decimal,
    tick_size: Decimal,
    *,
    upper: bool,
) -> Decimal:
    multiplier = Decimal("1") + rate if upper else Decimal("1") - rate
    ticks = (previous_close * multiplier / tick_size).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return ticks * tick_size


def derive_security_trading_status(
    *,
    quote: dict[str, Any],
    instrument: dict[str, Any],
    trade_date: date,
    listing_session_number: int | None,
    policy: dict[str, Any] | None = None,
    collected_at: datetime | None = None,
) -> SecurityTradingStatus:
    policy = policy or cn_price_limit_policy()
    collected_at = collected_at or datetime.utcnow()
    market, symbol = normalize_instrument(
        quote.get("symbol") or quote.get("code"),
        quote.get("market") or "CN",
    )
    if market != "CN":
        raise TradingStatusError("trading-status derivation supports CN only")
    quote_date = _as_date(quote.get("trade_date"))
    if quote_date != trade_date:
        raise TradingStatusError("price row does not match requested trade date")
    previous_close_raw = quote.get("prev_close")
    if previous_close_raw is None:
        previous_close_raw = quote.get("pre_close")
    try:
        previous_close = Decimal(str(previous_close_raw))
    except Exception as exc:
        raise TradingStatusError("price row lacks valid previous close") from exc
    if previous_close <= 0:
        raise TradingStatusError("previous close must be positive")

    is_st = _explicit_bool(
        quote.get("st_status")
        if "st_status" in quote
        else quote.get("isST")
    )
    is_suspended = _explicit_bool(
        quote.get("suspended")
        if "suspended" in quote
        else (
            None
            if quote.get("tradestatus") is None
            else str(quote.get("tradestatus")).strip() != "1"
        )
    )
    board = _board(symbol, policy)
    listing_date = _as_date(
        instrument.get("list_date")
        or instrument.get("listing_date")
        or instrument.get("ipo_date")
    )
    name = str(
        instrument.get("name")
        or instrument.get("stock_name")
        or instrument.get("code_name")
        or ""
    ).strip()
    missing = []
    if is_st is None:
        missing.append("is_st")
    if is_suspended is None:
        missing.append("is_suspended")
    if board == "UNKNOWN":
        missing.append("listing_board")
    if listing_date is None:
        missing.append("listing_date")
    if listing_session_number is None:
        missing.append("listing_session_number")
    if "退" in name:
        missing.append("delisting_or_special_treatment_rule")
    if is_st is not None:
        name_indicates_st = name.upper().startswith(("ST", "*ST"))
        if name_indicates_st != is_st:
            missing.append("st_status_name_conflict")

    tick_size = Decimal(str(policy["tick_size"]))
    lot_size = int(policy["lot_size"])
    upper = lower = None
    rule = "UNRESOLVED"
    special_status = "NORMAL"
    if is_st is True:
        special_status = "ST"
    elif "退" in name:
        special_status = "DELISTING_OR_SPECIAL"

    no_limit = False
    if (
        not missing
        and listing_date is not None
        and listing_session_number is not None
        and listing_session_number <= int(policy["initial_no_limit_sessions"])
    ):
        if board in {"CHINEXT", "STAR", "BSE"}:
            no_limit = True
        elif board in {"SSE_MAIN", "SZSE_MAIN"}:
            effective = _as_date(policy["registration_mainboard_effective_date"])
            if effective is None:
                missing.append("registration_mainboard_effective_date")
            elif listing_date >= effective:
                no_limit = True
            else:
                # Pre-registration IPO-day rules include additional auction
                # constraints that this first production adapter does not
                # pretend to reconstruct.
                missing.append("legacy_mainboard_initial_listing_rule")

    if no_limit:
        rule = "NO_PRICE_LIMIT_INITIAL_LISTING_SESSION"
        missing.append("execution_snapshot_no_limit_day_unsupported")
    elif not missing:
        board_rule = policy["boards"][board]
        rate = Decimal(
            str(
                board_rule[
                    "st_limit_rate" if is_st is True else "normal_limit_rate"
                ]
            )
        )
        if board == "CHINEXT":
            reform = _as_date(policy["chinext_reform_effective_date"])
            if reform is None:
                missing.append("chinext_reform_effective_date")
            elif trade_date < reform:
                rate = Decimal("0.05") if is_st else Decimal("0.10")
        if not missing:
            upper = _rounded_limit(previous_close, rate, tick_size, upper=True)
            lower = _rounded_limit(previous_close, rate, tick_size, upper=False)
            rule = f"{board}_{'ST' if is_st else 'NORMAL'}_{rate}"

    calculation_status = "READY" if not missing else "INSUFFICIENT_DATA"
    price_ref = str(quote.get("ref_id") or quote.get("data_ref") or "")
    if price_ref.startswith("stock_daily_quotes:"):
        price_ref = price_ref.split(":", 1)[1]
    if not price_ref:
        raise TradingStatusError("price row lacks stable source reference")
    instrument_ref = str(
        instrument.get("ref_id")
        or instrument.get("source_record_id")
        or instrument.get("_id")
        or ""
    )
    if not instrument_ref:
        raise TradingStatusError("instrument row lacks stable source reference")
    source_price_version = str(
        quote.get("price_data_version") or quote.get("data_version") or ""
    )
    if not source_price_version:
        raise TradingStatusError("price row lacks data version")
    security_master_version = str(
        instrument.get("security_master_data_version") or instrument_ref
    )
    source_available_times = [
        value
        for value in (
            _business_timestamp(trade_date, hour=15),
            _as_datetime(quote.get("available_at")),
            _as_datetime(quote.get("collected_at")),
            _as_datetime(instrument.get("available_at")),
            _as_datetime(instrument.get("collected_at")),
            collected_at,
        )
        if value is not None
    ]
    available_at = max(source_available_times)
    data_version = (
        f"{policy['policy_id']}@{policy['policy_version']}:"
        f"{policy['calculation_version']}:{source_price_version}:"
        f"{production_data_hash(security_master_version)[:16]}"
    )
    source_refs = [
        f"stock_daily_quotes:{price_ref}",
        f"stock_basic_info:{instrument_ref}",
        *[
            str(item)
            for item in quote.get("trading_status_source_refs", [])
            if item
        ],
    ]
    business = {
        "ref_id": (
            f"trading-status-{symbol}-{trade_date.isoformat()}-"
            f"{production_data_hash(data_version)[:16]}"
        ),
        "symbol": symbol,
        "market": "CN",
        "trade_date": trade_date,
        "business_date": _business_timestamp(trade_date),
        "available_at": available_at,
        "previous_close": previous_close,
        "price_limit_rule": rule,
        "upper_limit_price": upper,
        "lower_limit_price": lower,
        "is_st": bool(is_st) if is_st is not None else False,
        "is_suspended": (
            bool(is_suspended) if is_suspended is not None else False
        ),
        "listing_board": board,
        "listing_date": listing_date,
        "listing_session_number": listing_session_number,
        "special_status": special_status,
        "tick_size": tick_size,
        "lot_size": lot_size,
        "source": "PERSISTED_PROVIDER_FACTS+VERSIONED_RULE",
        "source_version": (
            f"{quote.get('provider', 'unknown')}:"
            f"{quote.get('provider_version', 'unknown')}+"
            f"{policy['policy_id']}@{policy['policy_version']}+"
            f"{security_master_version}"
        ),
        "source_record_id": str(
            quote.get("source_record_id") or price_ref
        ),
        "source_refs": source_refs,
        "source_price_data_version": source_price_version,
        "data_version": data_version,
        "calculation_version": str(policy["calculation_version"]),
        "calculation_status": calculation_status,
        "missing_fields": sorted(set(missing)),
    }
    business["content_hash"] = production_data_hash(business)
    return SecurityTradingStatus(
        trading_status_id=str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:trading-status:"
                f"{symbol}:CN:{trade_date}:{data_version}",
            )
        ),
        collected_at=collected_at,
        **business,
    )


class CNTradingStatusService:
    COLLECTION = "ag_security_trading_statuses"

    def __init__(self, db):
        self.db = db
        self.policy = cn_price_limit_policy()

    async def _instrument(self, symbol: str) -> dict[str, Any]:
        rows = await self.db["stock_basic_info"].find(
            {"$or": [{"symbol": symbol}, {"code": symbol}]}
        ).to_list(length=None)
        if not rows:
            raise TradingStatusError(f"stock_basic_info lacks {symbol}")
        usable = [
            clean_document(row)
            for row in rows
            if _as_date(
                row.get("list_date")
                or row.get("listing_date")
                or row.get("ipo_date")
            )
            is not None
        ]
        if not usable:
            raise TradingStatusError(f"stock_basic_info lacks listing date for {symbol}")
        listing_dates = {
            _as_date(
                row.get("list_date")
                or row.get("listing_date")
                or row.get("ipo_date")
            )
            for row in usable
        }
        names = {
            str(row.get("name") or row.get("stock_name") or row.get("code_name") or "")
            for row in usable
        }
        if len(listing_dates) != 1 or len({item for item in names if item}) > 1:
            raise TradingStatusError(
                f"stock_basic_info has conflicting identity facts for {symbol}"
            )
        usable.sort(
            key=lambda row: (
                str(row.get("source") or row.get("provider") or ""),
                str(row.get("ref_id") or row.get("_id") or ""),
            )
        )
        return usable[0]

    async def _listing_session_number(
        self,
        listing_date: date,
        trade_date: date,
    ) -> int | None:
        if listing_date > trade_date:
            return None
        # More than 30 calendar days guarantees the security is beyond the
        # first five open sessions, without needing an IPO-era calendar.
        if (trade_date - listing_date).days > 30:
            return 6
        rows = await self.db["trading_calendar"].find(
            {
                "market": "CN",
                "session_date": {
                    "$gte": _business_timestamp(listing_date),
                    "$lte": _business_timestamp(trade_date),
                },
                "is_open": True,
            }
        ).sort("session_date", 1).to_list(length=None)
        if not rows:
            return None
        first = _as_date(rows[0].get("session_date"))
        last = _as_date(rows[-1].get("session_date"))
        if first != listing_date or last != trade_date:
            return None
        return len(rows)

    async def _enrich_persisted_status_facts(
        self,
        *,
        quote: dict[str, Any],
        instrument: dict[str, Any],
        symbol: str,
        trade_date: date,
    ) -> dict[str, Any]:
        """Fill only facts that can be proved from persisted repositories."""

        result = dict(quote)
        source_refs = list(result.get("trading_status_source_refs") or [])
        if result.get("prev_close") is None and result.get("pre_close") is None:
            previous_session = await self.db["trading_calendar"].find_one(
                {
                    "market": "CN",
                    "session_date": {"$lt": _business_timestamp(trade_date)},
                    "is_open": True,
                },
                sort=[("session_date", -1)],
            )
            previous_date = _as_date(
                (previous_session or {}).get("session_date")
            )
            if previous_date is not None:
                previous_rows = await self.db["stock_daily_quotes"].find(
                    {
                        "symbol": symbol,
                        "market": "CN",
                        "period": "daily",
                        "trade_date": _business_timestamp(previous_date),
                    }
                ).to_list(length=None)
                if len(previous_rows) == 1:
                    previous = clean_document(previous_rows[0])
                    previous_close = previous.get("close")
                    if previous_close is not None:
                        result["prev_close"] = previous_close
                        previous_ref = str(
                            previous.get("ref_id")
                            or previous.get("data_ref")
                            or ""
                        )
                        if previous_ref.startswith("stock_daily_quotes:"):
                            previous_ref = previous_ref.split(":", 1)[1]
                        if previous_ref:
                            source_refs.append(
                                f"stock_daily_quotes:{previous_ref}"
                            )
                        result["previous_close_resolution"] = (
                            "PREVIOUS_PERSISTED_OPEN_SESSION_RAW_CLOSE"
                        )
        if "st_status" not in result and "isST" not in result:
            name = str(
                instrument.get("name")
                or instrument.get("stock_name")
                or instrument.get("code_name")
                or ""
            ).strip()
            if name:
                result["st_status"] = name.upper().startswith(("ST", "*ST"))
                result["st_status_resolution"] = (
                    "VERSIONED_SECURITY_MASTER_NAME"
                )
        if "suspended" not in result and "tradestatus" not in result:
            try:
                volume = Decimal(
                    str(result.get("volume_shares", result.get("volume")))
                )
            except Exception:
                volume = Decimal("-1")
            if volume > 0:
                result["suspended"] = False
                result["suspension_resolution"] = (
                    "FORMAL_DAILY_BAR_POSITIVE_VOLUME"
                )
        result["trading_status_source_refs"] = sorted(set(source_refs))
        return result

    async def sync(
        self,
        *,
        symbols: list[str],
        trade_date: date,
        execute: bool,
        collected_at: datetime | None = None,
    ) -> dict[str, Any]:
        collected_at = collected_at or datetime.utcnow()
        collected_at = collected_at.replace(
            microsecond=(collected_at.microsecond // 1000) * 1000
        )
        calendar = await self.db["trading_calendar"].find_one(
            {
                "market": "CN",
                "session_date": _business_timestamp(trade_date),
                "is_open": True,
            }
        )
        if calendar is None:
            raise TradingStatusError(
                "persisted CN calendar does not confirm requested open session"
            )
        results = []
        for raw_symbol in sorted(set(symbols)):
            market, symbol = normalize_instrument(raw_symbol, "CN")
            if market != "CN":
                raise TradingStatusError("CN trading-status service supports CN only")
            rows = await self.db["stock_daily_quotes"].find(
                {
                    "symbol": symbol,
                    "market": "CN",
                    "period": "daily",
                    "trade_date": _business_timestamp(trade_date),
                }
            ).to_list(length=None)
            if len(rows) != 1:
                raise TradingStatusError(
                    f"{symbol} exact-date daily price identity is ambiguous"
                )
            quote = clean_document(rows[0])
            instrument = await self._instrument(symbol)
            quote = await self._enrich_persisted_status_facts(
                quote=quote,
                instrument=instrument,
                symbol=symbol,
                trade_date=trade_date,
            )
            listing_date = _as_date(
                instrument.get("list_date")
                or instrument.get("listing_date")
                or instrument.get("ipo_date")
            )
            assert listing_date is not None
            session_number = await self._listing_session_number(
                listing_date, trade_date
            )
            status = derive_security_trading_status(
                quote=quote,
                instrument=instrument,
                trade_date=trade_date,
                listing_session_number=session_number,
                policy=self.policy,
                collected_at=collected_at,
            )
            identity = {
                "symbol": symbol,
                "market": "CN",
                "trade_date": _business_timestamp(trade_date),
                "data_version": status.data_version,
            }
            existing = clean_document(
                await self.db[self.COLLECTION].find_one(identity)
            )
            if existing is not None:
                first_collected_at = _as_datetime(existing.get("collected_at"))
                if first_collected_at is None:
                    raise TradingStatusConflict(
                        "existing trading status lacks collected_at"
                    )
                status = derive_security_trading_status(
                    quote=quote,
                    instrument=instrument,
                    trade_date=trade_date,
                    listing_session_number=session_number,
                    policy=self.policy,
                    collected_at=first_collected_at,
                )
            if (
                existing is not None
                and str(existing.get("content_hash")) != status.content_hash
            ):
                raise TradingStatusConflict(
                    "same symbol + trade_date + data_version has different content"
                )
            action = "REUSED" if existing else "WOULD_CREATE"
            if execute and existing is None:
                await self.db[self.COLLECTION].insert_one(model_document(status))
                action = "CREATED"
                await self.db["ag_production_data_events"].update_one(
                    {
                        "event_id": str(
                            uuid5(
                                NAMESPACE_URL,
                                f"trading-status:{status.trading_status_id}",
                            )
                        )
                    },
                    {
                        "$setOnInsert": {
                            "event_id": str(
                                uuid5(
                                    NAMESPACE_URL,
                                    f"trading-status:{status.trading_status_id}",
                                )
                            ),
                            "event_type": "SECURITY_TRADING_STATUS_CREATED",
                            "market": "CN",
                            "symbol": symbol,
                            "trade_date": _business_timestamp(trade_date),
                            "trading_status_id": status.trading_status_id,
                            "input_hash": production_data_hash(status.source_refs),
                            "result_hash": status.content_hash,
                            "created_at": collected_at,
                            "schema_version": "alphaguard-production-data-event-v1",
                        }
                    },
                    upsert=True,
                )
            results.append(
                {
                    "symbol": symbol,
                    "previous_close": status.previous_close,
                    "calculation_status": status.calculation_status,
                    "price_limit_rule": status.price_limit_rule,
                    "upper_limit_price": status.upper_limit_price,
                    "lower_limit_price": status.lower_limit_price,
                    "is_st": status.is_st,
                    "is_suspended": status.is_suspended,
                    "listing_board": status.listing_board,
                    "tick_size": status.tick_size,
                    "lot_size": status.lot_size,
                    "source": status.source,
                    "source_version": status.source_version,
                    "source_refs": status.source_refs,
                    "missing_fields": status.missing_fields,
                    "data_version": status.data_version,
                    "content_hash": status.content_hash,
                    "action": action,
                }
            )
        return {
            "market": "CN",
            "trade_date": trade_date,
            "write": execute,
            "policy_id": self.policy["policy_id"],
            "policy_version": self.policy["policy_version"],
            "results": results,
        }
