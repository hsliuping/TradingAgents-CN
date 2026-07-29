"""Strict contracts for versioned AlphaGuard production market inputs.

These records describe market data only.  They cannot authorize an order,
change a strategy, or relax an execution safety check.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PRODUCTION_DATA_SCHEMA_VERSION = "alphaguard-production-data-v1"


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def production_data_hash(
    value: Any,
    *,
    exclude: set[str] | None = None,
) -> str:
    excluded = exclude or set()
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="python", exclude=excluded)
    elif isinstance(value, dict):
        payload = {key: item for key, item in value.items() if key not in excluded}
    else:
        payload = value
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ProductionDataSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        allow_inf_nan=False,
    )


class ProductionMarketContextSource(ProductionDataSchema):
    source_id: str = Field(min_length=1)
    market: Literal["CN"] = "CN"
    trade_date: date
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    underlying_source: str | None = None
    universe_provider: str | None = None
    universe_provider_version: str | None = None
    normalization_version: str = Field(min_length=1)
    source_record_count: int = Field(ge=0)
    expected_universe_count: int = Field(ge=0)
    normalized_records: list[dict[str, Any]]
    market_amount_window: list[dict[str, Any]]
    sector_records: list[dict[str, Any]]
    benchmark_records: list[dict[str, Any]]
    source_response_hashes: dict[str, str]
    available_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    collected_at: datetime
    schema_version: str = PRODUCTION_DATA_SCHEMA_VERSION


class SecurityMasterSourceRecord(ProductionDataSchema):
    source_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    provider_endpoint: Literal["query_stock_basic"]
    normalization_version: str = Field(min_length=1)
    raw_fields: dict[str, str]
    name: str = Field(min_length=1)
    listing_date: date
    security_type: str = Field(min_length=1)
    listing_status: str = Field(min_length=1)
    available_at: datetime
    collected_at: datetime
    data_version: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = PRODUCTION_DATA_SCHEMA_VERSION


class ProductionMarketContext(ProductionDataSchema):
    context_id: str = Field(min_length=1)
    ref_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    market: Literal["CN"] = "CN"
    trade_date: date
    business_date: datetime
    available_at: datetime
    collected_at: datetime
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    calculation_version: str = Field(min_length=1)

    benchmark_symbol: Literal["000300"] = "000300"
    benchmark_close: Decimal | None = Field(default=None, gt=0)
    benchmark_ma20: Decimal | None = Field(default=None, gt=0)
    benchmark_ma60: Decimal | None = Field(default=None, gt=0)
    benchmark_ma20_slope_5d: Decimal | None = None
    benchmark_volatility20: Decimal | None = Field(default=None, ge=0)

    total_amount: Decimal | None = Field(default=None, ge=0)
    amount_ratio20: Decimal | None = Field(default=None, ge=0)
    advance_count: int | None = Field(default=None, ge=0)
    decline_count: int | None = Field(default=None, ge=0)
    unchanged_count: int | None = Field(default=None, ge=0)
    market_breadth: Decimal | None = Field(default=None, ge=-1, le=1)
    new_high_count: int | None = Field(default=None, ge=0)
    new_low_count: int | None = Field(default=None, ge=0)
    new_high_low_ratio: Decimal | None = Field(default=None, ge=-1, le=1)
    industry_diffusion: Decimal | None = Field(default=None, ge=0, le=1)
    extreme_risk_flag: bool | None = None

    universe_coverage: Decimal = Field(ge=0, le=1)
    high_low_coverage: Decimal = Field(ge=0, le=1)
    sector_coverage: Decimal = Field(ge=0, le=1)
    calculation_status: Literal[
        "READY",
        "INSUFFICIENT_DATA",
        "INVALID_SOURCE",
    ]
    missing_fields: list[str] = Field(default_factory=list)
    methodology: dict[str, str]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = PRODUCTION_DATA_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_readiness(self) -> "ProductionMarketContext":
        required = (
            self.benchmark_close,
            self.benchmark_ma20,
            self.benchmark_ma60,
            self.benchmark_ma20_slope_5d,
            self.benchmark_volatility20,
            self.advance_count,
            self.decline_count,
            self.market_breadth,
            self.industry_diffusion,
        )
        if self.calculation_status == "READY":
            if any(value is None for value in required):
                raise ValueError("READY production MarketContext lacks required inputs")
            if self.missing_fields:
                raise ValueError("READY production MarketContext cannot list missing fields")
        elif not self.missing_fields:
            raise ValueError("non-ready production MarketContext requires missing fields")
        return self


class MarketContextWindowManifest(ProductionDataSchema):
    """Create-only lock over the ordered production context input window."""

    manifest_id: str = Field(min_length=1)
    ref_id: str = Field(min_length=1)
    market: Literal["CN"] = "CN"
    as_of_trade_date: date
    required_count: int = Field(gt=0)
    actual_count: int = Field(gt=0)
    ordered_trade_dates: list[date] = Field(min_length=1)
    ordered_context_ids: list[str] = Field(min_length=1)
    ordered_context_hashes: list[str] = Field(min_length=1)
    context_version: str = Field(min_length=1)
    window_start: date
    window_end: date
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    available_at: datetime
    created_at: datetime
    schema_version: str = PRODUCTION_DATA_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_window(self) -> "MarketContextWindowManifest":
        lengths = {
            len(self.ordered_trade_dates),
            len(self.ordered_context_ids),
            len(self.ordered_context_hashes),
        }
        if (
            lengths != {self.required_count}
            or self.actual_count != self.required_count
        ):
            raise ValueError(
                "MarketContext window must contain exactly required_count rows"
            )
        if self.ordered_trade_dates != sorted(set(self.ordered_trade_dates)):
            raise ValueError("MarketContext window dates must be unique and ordered")
        if self.window_start != self.ordered_trade_dates[0]:
            raise ValueError("window_start does not match the first context date")
        if self.window_end != self.ordered_trade_dates[-1]:
            raise ValueError("window_end does not match the last context date")
        if self.window_end != self.as_of_trade_date:
            raise ValueError("MarketContext window must include the as-of trade date")
        if any(
            len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
            for value in self.ordered_context_hashes
        ):
            raise ValueError("ordered context hashes must be lowercase SHA-256 values")
        return self


class SecurityTradingStatus(ProductionDataSchema):
    trading_status_id: str = Field(min_length=1)
    ref_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    trade_date: date
    business_date: datetime
    available_at: datetime
    collected_at: datetime

    previous_close: Decimal = Field(gt=0)
    price_limit_rule: str = Field(min_length=1)
    upper_limit_price: Decimal | None = Field(default=None, gt=0)
    lower_limit_price: Decimal | None = Field(default=None, gt=0)
    is_st: bool
    is_suspended: bool
    listing_board: Literal[
        "SSE_MAIN",
        "SZSE_MAIN",
        "CHINEXT",
        "STAR",
        "BSE",
        "UNKNOWN",
    ]
    listing_date: date | None
    listing_session_number: int | None = Field(default=None, ge=1)
    special_status: str
    tick_size: Decimal = Field(gt=0)
    lot_size: int = Field(gt=0)

    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    source_price_data_version: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    calculation_version: str = Field(min_length=1)
    calculation_status: Literal[
        "READY",
        "INSUFFICIENT_DATA",
        "INVALID_SOURCE",
    ]
    missing_fields: list[str] = Field(default_factory=list)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = PRODUCTION_DATA_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_limits(self) -> "SecurityTradingStatus":
        if self.calculation_status == "READY":
            if self.upper_limit_price is None or self.lower_limit_price is None:
                raise ValueError("READY trading status requires explicit price limits")
            if self.lower_limit_price >= self.upper_limit_price:
                raise ValueError("lower limit must be below upper limit")
            if self.missing_fields:
                raise ValueError("READY trading status cannot list missing fields")
        elif not self.missing_fields:
            raise ValueError("non-ready trading status requires missing fields")
        return self
