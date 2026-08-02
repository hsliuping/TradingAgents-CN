"""Provider boundary for historical decision-grade fundamental evidence."""

from __future__ import annotations

import math
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

import requests

from tradingagents.alphaguard.instruments import normalize_instrument

from .real_data_ingestion_service import real_data_hash


EASTMONEY_STATEMENT_VERSION = "akshare-eastmoney-statement-v1"
CNINFO_EVIDENCE_VERSION = "akshare-cninfo-evidence-v1"
QOQ_CALCULATION_VERSION = "single-quarter-from-cumulative-v1"
ROE_CALCULATION_VERSION = "annualized-parent-profit-average-equity-v1"
FREE_CASH_FLOW_CALCULATION_VERSION = "operating-cashflow-minus-capex-v1"
MAX_ANNOUNCEMENT_EVIDENCE = 5
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_ANNOUNCEMENT_TEXT = 6000


class DecisionEvidenceProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class DecisionEvidenceFetchResult:
    provider_versions: dict[str, str]
    financial_records: tuple[dict[str, Any], ...]
    dividend_records: tuple[dict[str, Any], ...]
    announcement_records: tuple[dict[str, Any], ...]
    corporate_action_records: tuple[dict[str, Any], ...]
    source_statuses: dict[str, str]
    source_response_hashes: dict[str, str]
    source_errors: dict[str, str]


class DecisionEvidenceProvider(Protocol):
    name: str

    def capability_check(self) -> dict[str, Any]: ...

    def fetch(
        self,
        *,
        symbol: str,
        decision_time: datetime,
    ) -> DecisionEvidenceFetchResult: ...


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    return [
        {str(key): _clean_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if math.isnan(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


def _number(value: Any) -> float | None:
    value = _clean_scalar(value)
    if value in (None, "", "--"):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _datetime(value: Any) -> datetime | None:
    value = _clean_scalar(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except ValueError:
        return None


def _percent_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / abs(previous) * 100, 6)


def _statement_rows(
    frame: Any,
    *,
    symbol: str,
    decision_time: datetime,
) -> dict[date, dict[str, Any]]:
    selected: dict[date, dict[str, Any]] = {}
    for row in _records(frame):
        if str(row.get("SECURITY_CODE") or "") != symbol:
            continue
        report_at = _datetime(row.get("REPORT_DATE"))
        notice_at = _datetime(row.get("NOTICE_DATE"))
        update_at = _datetime(row.get("UPDATE_DATE")) or notice_at
        if report_at is None or notice_at is None or notice_at > decision_time:
            continue
        current = selected.get(report_at.date())
        current_key = (
            _datetime(current.get("UPDATE_DATE")) or _datetime(current.get("NOTICE_DATE"))
            if current
            else None
        )
        if current is None or (update_at and current_key and update_at > current_key):
            selected[report_at.date()] = row
    return selected


def _single_quarter_value(
    rows: dict[date, dict[str, Any]],
    report_date: date,
    field: str,
) -> float | None:
    cumulative = _number(rows.get(report_date, {}).get(field))
    if cumulative is None:
        return None
    quarter = (report_date.month - 1) // 3 + 1
    if quarter == 1:
        return cumulative
    previous_report = date(report_date.year, (quarter - 1) * 3, 1)
    if previous_report.month in {3, 12}:
        previous_report = previous_report.replace(
            day=31
        )
    else:
        previous_report = previous_report.replace(day=30)
    previous_cumulative = _number(rows.get(previous_report, {}).get(field))
    if previous_cumulative is None:
        return None
    return cumulative - previous_cumulative


def _previous_quarter_date(report_date: date) -> date:
    quarter = (report_date.month - 1) // 3 + 1
    if quarter == 1:
        return date(report_date.year - 1, 12, 31)
    month = (quarter - 1) * 3
    day = 31 if month == 3 else 30
    return date(report_date.year, month, day)


def _qoq(
    rows: dict[date, dict[str, Any]],
    report_date: date,
    field: str,
) -> float | None:
    return _percent_change(
        _single_quarter_value(rows, report_date, field),
        _single_quarter_value(rows, _previous_quarter_date(report_date), field),
    )


def _annualized_roe(
    *,
    report_date: date,
    parent_profit: float | None,
    balance_rows: dict[date, dict[str, Any]],
) -> float | None:
    current_equity = _number(
        balance_rows.get(report_date, {}).get("TOTAL_PARENT_EQUITY")
    ) or _number(balance_rows.get(report_date, {}).get("TOTAL_EQUITY"))
    prior_date = date(report_date.year - 1, 12, 31)
    prior_equity = _number(
        balance_rows.get(prior_date, {}).get("TOTAL_PARENT_EQUITY")
    ) or _number(balance_rows.get(prior_date, {}).get("TOTAL_EQUITY"))
    if parent_profit is None or current_equity is None or prior_equity is None:
        return None
    average_equity = (current_equity + prior_equity) / 2
    if average_equity == 0:
        return None
    quarter = (report_date.month - 1) // 3 + 1
    return round(parent_profit * (4 / quarter) / average_equity * 100, 6)


def _financial_record(
    *,
    symbol: str,
    decision_time: datetime,
    profit_frame: Any,
    balance_frame: Any,
    cashflow_frame: Any,
) -> dict[str, Any] | None:
    profits = _statement_rows(
        profit_frame, symbol=symbol, decision_time=decision_time
    )
    balances = _statement_rows(
        balance_frame, symbol=symbol, decision_time=decision_time
    )
    cashflows = _statement_rows(
        cashflow_frame, symbol=symbol, decision_time=decision_time
    )
    common_dates = sorted(set(profits) & set(balances) & set(cashflows))
    if not common_dates:
        return None
    report_date = common_dates[-1]
    profit = profits[report_date]
    balance = balances[report_date]
    cashflow = cashflows[report_date]
    notices = [
        item
        for item in (
            _datetime(profit.get("NOTICE_DATE")),
            _datetime(balance.get("NOTICE_DATE")),
            _datetime(cashflow.get("NOTICE_DATE")),
        )
        if item is not None
    ]
    published_at = max(notices)
    revenue = _number(profit.get("TOTAL_OPERATE_INCOME"))
    net_income = _number(profit.get("NETPROFIT"))
    parent_profit = _number(profit.get("PARENT_NETPROFIT"))
    deducted_profit = _number(profit.get("DEDUCT_PARENT_NETPROFIT"))
    operate_income = _number(profit.get("OPERATE_INCOME"))
    operate_cost = _number(profit.get("OPERATE_COST"))
    gross_margin = (
        round((operate_income - operate_cost) / operate_income * 100, 6)
        if operate_income not in (None, 0) and operate_cost is not None
        else None
    )
    total_assets = _number(balance.get("TOTAL_ASSETS"))
    total_liabilities = _number(balance.get("TOTAL_LIABILITIES"))
    debt_ratio = (
        round(total_liabilities / total_assets * 100, 6)
        if total_assets not in (None, 0) and total_liabilities is not None
        else None
    )
    operating_cashflow = _number(cashflow.get("NETCASH_OPERATE"))
    investing_cashflow = _number(cashflow.get("NETCASH_INVEST"))
    capex = _number(cashflow.get("CONSTRUCT_LONG_ASSET"))
    free_cashflow = (
        operating_cashflow - capex
        if operating_cashflow is not None and capex is not None
        else None
    )
    cashflow_match = (
        round(operating_cashflow / net_income, 6)
        if operating_cashflow is not None and net_income not in (None, 0)
        else None
    )
    source_record_id = (
        f"{symbol}:eastmoney-statements:{report_date.isoformat()}:"
        f"{published_at.isoformat()}"
    )
    return {
        "source_record_id": source_record_id,
        "symbol": symbol,
        "market": "CN",
        "report_period": report_date,
        "report_type": str(profit.get("REPORT_TYPE") or "UNKNOWN"),
        "published_at": published_at,
        "currency": str(profit.get("CURRENCY") or "CNY"),
        "revenue": revenue,
        "net_income": net_income,
        "net_profit": parent_profit,
        "deducted_net_profit": deducted_profit,
        "gross_margin": gross_margin,
        "asset_liability_ratio": debt_ratio,
        "roe": _annualized_roe(
            report_date=report_date,
            parent_profit=parent_profit,
            balance_rows=balances,
        ),
        "revenue_yoy": _number(profit.get("TOTAL_OPERATE_INCOME_YOY")),
        "net_profit_yoy": _number(profit.get("PARENT_NETPROFIT_YOY")),
        "deducted_net_profit_yoy": _number(
            profit.get("DEDUCT_PARENT_NETPROFIT_YOY")
        ),
        "revenue_qoq": _qoq(profits, report_date, "TOTAL_OPERATE_INCOME"),
        "net_profit_qoq": _qoq(profits, report_date, "PARENT_NETPROFIT"),
        "deducted_net_profit_qoq": _qoq(
            profits, report_date, "DEDUCT_PARENT_NETPROFIT"
        ),
        "operating_cash_flow": operating_cashflow,
        "investing_cash_flow": investing_cashflow,
        "capital_expenditure": capex,
        "free_cash_flow": free_cashflow,
        "operating_cash_flow_to_net_income": cashflow_match,
        "provider": "AKShare/Eastmoney",
        "underlying_source": "Eastmoney",
        "data_version": EASTMONEY_STATEMENT_VERSION,
        "calculation_versions": {
            "qoq": QOQ_CALCULATION_VERSION,
            "roe": ROE_CALCULATION_VERSION,
            "free_cash_flow": FREE_CASH_FLOW_CALCULATION_VERSION,
        },
        "source_response_hashes": {
            "profit": real_data_hash(profit),
            "balance": real_data_hash(balance),
            "cashflow": real_data_hash(cashflow),
        },
    }


def _announcement_category(title: str) -> str:
    categories = (
        ("DIVIDEND", ("分红", "分配", "派息", "权益分派", "除权除息")),
        ("REPURCHASE", ("回购",)),
        ("REDUCTION", ("减持",)),
        ("PLACEMENT", ("配股", "增发", "定向发行", "配售")),
        ("FINANCIAL_REPORT", ("年度报告", "季度报告", "半年度报告")),
        ("RISK", ("风险提示", "退市", "停牌")),
    )
    for category, keywords in categories:
        if any(keyword in title for keyword in keywords):
            return category
    return "GENERAL"


def _pdf_text(session: requests.Session, adjunct_url: str) -> tuple[str, str, str]:
    from pypdf import PdfReader

    url = f"https://static.cninfo.com.cn/{adjunct_url.lstrip('/')}"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    if len(response.content) > MAX_PDF_BYTES or not response.content.startswith(b"%PDF"):
        raise DecisionEvidenceProviderError("CNINFO_ATTACHMENT_INVALID")
    attachment_hash = hashlib.sha256(response.content).hexdigest()
    reader = PdfReader(BytesIO(response.content))
    fragments: list[str] = []
    for page in reader.pages[:12]:
        text = page.extract_text() or ""
        if text:
            fragments.append(text)
        if sum(len(item) for item in fragments) >= MAX_ANNOUNCEMENT_TEXT:
            break
    excerpt = re.sub(r"\s+", " ", " ".join(fragments)).strip()
    if not excerpt:
        raise DecisionEvidenceProviderError("CNINFO_PDF_TEXT_UNAVAILABLE")
    return url, attachment_hash, excerpt[:MAX_ANNOUNCEMENT_TEXT]


class AKShareDecisionEvidenceProvider:
    """AKShare facade with explicit Eastmoney and CNInfo provenance."""

    name = "akshare-decision-evidence"

    @staticmethod
    def capability_check() -> dict[str, Any]:
        try:
            import akshare as ak
            import pypdf

            required = (
                "stock_profit_sheet_by_report_em",
                "stock_balance_sheet_by_report_em",
                "stock_cash_flow_sheet_by_report_em",
                "stock_dividend_cninfo",
                "stock_zh_a_disclosure_report_cninfo",
            )
            missing = [name for name in required if not callable(getattr(ak, name, None))]
            return {
                "provider": AKShareDecisionEvidenceProvider.name,
                "available": not missing,
                "provider_versions": {
                    "akshare": str(getattr(ak, "__version__", "unknown")),
                    "pypdf": str(getattr(pypdf, "__version__", "unknown")),
                },
                "underlying_sources": ["Eastmoney", "CNInfo"],
                "missing_capabilities": missing,
                "network_required": True,
            }
        except Exception as exc:
            return {
                "provider": AKShareDecisionEvidenceProvider.name,
                "available": False,
                "error_code": type(exc).__name__,
                "network_required": True,
            }

    @staticmethod
    def _announcements(
        *,
        symbol: str,
        decision_time: datetime,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        import akshare as ak

        start = (decision_time.date() - timedelta(days=370)).strftime("%Y%m%d")
        end = decision_time.date().strftime("%Y%m%d")
        wrapper = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=symbol,
            market="沪深京",
            start_date=start,
            end_date=end,
        )
        wrapper_rows = _records(wrapper)
        org_id = None
        for row in wrapper_rows:
            query = parse_qs(urlparse(str(row.get("公告链接") or "")).query)
            candidate = (query.get("orgId") or [None])[0]
            if candidate:
                org_id = str(candidate)
                break
        if not org_id:
            return [], [], real_data_hash(wrapper_rows)
        payload = {
            "pageNum": "1",
            "pageSize": "30",
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{symbol},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{start[:4]}-{start[4:6]}-{start[6:]}~{end[:4]}-{end[4:6]}-{end[6:]}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        session = requests.Session()
        response = session.post(
            "http://www.cninfo.com.cn/new/hisAnnouncement/query",
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        page_count = int(body.get("totalpages") or 1)
        raw_rows = list(body.get("announcements") or [])
        for page in range(2, page_count + 1):
            payload["pageNum"] = str(page)
            page_response = session.post(
                "http://www.cninfo.com.cn/new/hisAnnouncement/query",
                data=payload,
                timeout=30,
            )
            page_response.raise_for_status()
            raw_rows.extend(page_response.json().get("announcements") or [])
        eligible: list[tuple[datetime, dict[str, Any]]] = []
        local_timezone = timezone(timedelta(hours=8))
        for raw in raw_rows:
            timestamp = _number(raw.get("announcementTime"))
            if timestamp is None:
                continue
            published_at = datetime.fromtimestamp(
                timestamp / 1000,
                tz=local_timezone,
            ).replace(tzinfo=None)
            if published_at > decision_time:
                continue
            eligible.append((published_at, raw))
        eligible.sort(key=lambda item: (item[0], str(item[1].get("announcementId"))), reverse=True)
        announcements: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        for published_at, raw in eligible:
            if len(announcements) >= MAX_ANNOUNCEMENT_EVIDENCE:
                break
            adjunct_url = str(raw.get("adjunctUrl") or "")
            if not adjunct_url or str(raw.get("adjunctType") or "").upper() != "PDF":
                continue
            try:
                attachment_url, attachment_hash, excerpt = _pdf_text(
                    session, adjunct_url
                )
            except Exception:
                continue
            title = re.sub(r"<[^>]+>", "", str(raw.get("announcementTitle") or "")).strip()
            record = {
                "source_record_id": str(raw.get("announcementId") or ""),
                "symbol": symbol,
                "market": "CN",
                "title": title,
                "announcement_category": _announcement_category(title),
                "published_at": published_at,
                "evidence_excerpt": excerpt,
                "attachment_url": attachment_url,
                "attachment_content_hash": attachment_hash,
                "provider": "AKShare/CNInfo",
                "underlying_source": "CNInfo",
                "data_version": CNINFO_EVIDENCE_VERSION,
            }
            announcements.append(record)
            if record["announcement_category"] in {
                "DIVIDEND",
                "REPURCHASE",
                "REDUCTION",
                "PLACEMENT",
            }:
                actions.append(dict(record))
        return announcements, actions, real_data_hash(raw_rows)

    @classmethod
    def fetch(
        cls,
        *,
        symbol: str,
        decision_time: datetime,
    ) -> DecisionEvidenceFetchResult:
        import akshare as ak

        market, symbol = normalize_instrument(symbol, "CN")
        if market != "CN":
            raise DecisionEvidenceProviderError("decision evidence supports CN only")
        capability = cls.capability_check()
        if not capability.get("available"):
            raise DecisionEvidenceProviderError("PROVIDER_CAPABILITY_UNAVAILABLE")
        prefix = "SH" if symbol.startswith("6") else "SZ"
        provider_versions = dict(capability["provider_versions"])
        source_statuses: dict[str, str] = {}
        response_hashes: dict[str, str] = {}
        errors: dict[str, str] = {}
        financial_records: list[dict[str, Any]] = []
        dividend_records: list[dict[str, Any]] = []
        announcement_records: list[dict[str, Any]] = []
        corporate_action_records: list[dict[str, Any]] = []

        try:
            profit = ak.stock_profit_sheet_by_report_em(symbol=f"{prefix}{symbol}")
            balance = ak.stock_balance_sheet_by_report_em(symbol=f"{prefix}{symbol}")
            cashflow = ak.stock_cash_flow_sheet_by_report_em(symbol=f"{prefix}{symbol}")
            response_hashes["financial_evidence"] = real_data_hash(
                {
                    "profit": _records(profit),
                    "balance": _records(balance),
                    "cashflow": _records(cashflow),
                }
            )
            record = _financial_record(
                symbol=symbol,
                decision_time=decision_time,
                profit_frame=profit,
                balance_frame=balance,
                cashflow_frame=cashflow,
            )
            if record is not None:
                financial_records.append(record)
            source_statuses["financial_evidence"] = "READY"
            source_statuses["cashflow_evidence"] = "READY"
            response_hashes["cashflow_evidence"] = response_hashes[
                "financial_evidence"
            ]
        except Exception as exc:
            code = type(exc).__name__
            source_statuses["financial_evidence"] = "SOURCE_UNAVAILABLE"
            source_statuses["cashflow_evidence"] = "SOURCE_UNAVAILABLE"
            errors["financial_evidence"] = code
            errors["cashflow_evidence"] = code

        try:
            dividends = _records(ak.stock_dividend_cninfo(symbol=symbol))
            response_hashes["dividend_evidence"] = real_data_hash(dividends)
            eligible_dividends = [
                row
                for row in dividends
                if (published := _datetime(row.get("实施方案公告日期"))) is not None
                and published <= decision_time
            ]
            eligible_dividends.sort(
                key=lambda row: _datetime(row.get("实施方案公告日期")) or datetime.min,
                reverse=True,
            )
            if eligible_dividends:
                latest = eligible_dividends[0]
                published_at = _datetime(latest.get("实施方案公告日期"))
                assert published_at is not None
                dividend_records.append(
                    {
                        "source_record_id": (
                            f"{symbol}:cninfo-dividend:{published_at.date().isoformat()}:"
                            f"{latest.get('报告时间') or 'UNKNOWN'}"
                        ),
                        "symbol": symbol,
                        "market": "CN",
                        "published_at": published_at,
                        "dividend_type": latest.get("分红类型"),
                        "cash_dividend_per_ten_shares": _number(latest.get("派息比例")),
                        "stock_dividend_per_ten_shares": _number(latest.get("送股比例")),
                        "capitalization_per_ten_shares": _number(latest.get("转增比例")),
                        "record_date": _datetime(latest.get("股权登记日")),
                        "ex_dividend_date": _datetime(latest.get("除权日")),
                        "payment_date": _datetime(latest.get("派息日")),
                        "plan_description": str(latest.get("实施方案分红说明") or ""),
                        "report_period_label": str(latest.get("报告时间") or ""),
                        "provider": "AKShare/CNInfo",
                        "underlying_source": "CNInfo",
                        "data_version": CNINFO_EVIDENCE_VERSION,
                    }
                )
            source_statuses["dividend_evidence"] = "READY"
        except Exception as exc:
            source_statuses["dividend_evidence"] = "SOURCE_UNAVAILABLE"
            errors["dividend_evidence"] = type(exc).__name__

        try:
            (
                announcement_records,
                corporate_action_records,
                response_hash,
            ) = cls._announcements(symbol=symbol, decision_time=decision_time)
            response_hashes["announcement_evidence"] = response_hash
            response_hashes["corporate_action_evidence"] = response_hash
            source_statuses["announcement_evidence"] = "READY"
            source_statuses["corporate_action_evidence"] = "READY"
        except Exception as exc:
            source_statuses["announcement_evidence"] = "SOURCE_UNAVAILABLE"
            source_statuses["corporate_action_evidence"] = "SOURCE_UNAVAILABLE"
            errors["announcement_evidence"] = type(exc).__name__
            errors["corporate_action_evidence"] = type(exc).__name__

        return DecisionEvidenceFetchResult(
            provider_versions=provider_versions,
            financial_records=tuple(financial_records),
            dividend_records=tuple(dividend_records),
            announcement_records=tuple(announcement_records),
            corporate_action_records=tuple(corporate_action_records),
            source_statuses=source_statuses,
            source_response_hashes=response_hashes,
            source_errors=errors,
        )
