import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import akshare as ak
import pandas as pd
import requests

from app.core.database import get_mongo_db_sync


logger = logging.getLogger("webapi")


def is_a_share(code: str) -> bool:
    return re.fullmatch(r"(60|00|30|68)\d{4}", str(code)) is not None


def is_risk_stock(name: str) -> bool:
    upper_name = str(name or "").upper()
    return upper_name.startswith(("ST", "*ST", "SST", "S*ST", "PT")) or "退" in upper_name


def safe_float(value: Any) -> float:
    if value in (None, "", "-", "--"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class DianjinService:
    """点金术选股策略服务。"""

    REALTIME_BATCH_SIZE = 80
    REALTIME_MAX_WORKERS = 16
    KLINE_MAX_WORKERS = 16
    DIVIDEND_MAX_WORKERS = 8
    DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}

    def run_strategy(self, config: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()

        min_pe = float(config.get("min_pe", 0.1))
        max_pe = float(config.get("max_pe", 20.0))
        min_dividend = float(config.get("min_dividend", 3.0))
        max_dividend = float(config.get("max_dividend", 15.0))
        min_market_cap = float(config.get("min_market_cap", 50.0))
        ratio_threshold = float(config.get("ratio_threshold", 0.88))
        kline_days = int(config.get("kline_days", 1300))
        limit_count = int(config.get("limit_count", 0))
        dividend_mode = str(config.get("dividend_mode", "any"))
        min_pb = config.get("min_pb")
        max_pb = config.get("max_pb")

        stock_codes = self._load_target_stock_codes(
            specific_stocks=config.get("specific_stocks", ""),
            limit_count=limit_count,
        )

        stats = {
            "total_samples": len(stock_codes),
            "realtime_count": 0,
            "first_filter_count": 0,
            "ma120_pass_count": 0,
            "final_count": 0,
            "duration_ms": 0,
        }

        if not stock_codes:
            stats["duration_ms"] = int((time.perf_counter() - started) * 1000)
            return {"items": [], "stats": stats, "years": self._three_years()}

        realtime_records = self._fetch_realtime_records(stock_codes)
        stats["realtime_count"] = len(realtime_records)
        if not realtime_records:
            stats["duration_ms"] = int((time.perf_counter() - started) * 1000)
            return {"items": [], "stats": stats, "years": self._three_years()}

        filtered_records = self._apply_first_filter(
            realtime_records=realtime_records,
            min_pe=min_pe,
            max_pe=max_pe,
            min_dividend=min_dividend,
            max_dividend=max_dividend,
            min_market_cap=min_market_cap,
            min_pb=min_pb,
            max_pb=max_pb,
        )
        stats["first_filter_count"] = len(filtered_records)
        if not filtered_records:
            stats["duration_ms"] = int((time.perf_counter() - started) * 1000)
            return {"items": [], "stats": stats, "years": self._three_years()}

        ma120_records = self._filter_by_ma120(filtered_records, ratio_threshold, kline_days)
        stats["ma120_pass_count"] = len(ma120_records)
        if not ma120_records:
            stats["duration_ms"] = int((time.perf_counter() - started) * 1000)
            return {"items": [], "stats": stats, "years": self._three_years()}

        years = self._enrich_three_year_dividend(ma120_records)

        if dividend_mode == "all":
            final_records = [item for item in ma120_records if item.get("three_year_all_pass", False)]
        else:
            final_records = [item for item in ma120_records if item.get("three_year_dividend_pass", False)]

        final_records.sort(
            key=lambda item: (
                not item.get("three_year_all_pass", False),
                not item.get("three_year_dividend_pass", False),
                item.get("ma120_ratio", 999),
            )
        )

        stats["final_count"] = len(final_records)
        stats["duration_ms"] = int((time.perf_counter() - started) * 1000)
        return {"items": final_records, "stats": stats, "years": years}

    def _load_target_stock_codes(self, specific_stocks: Any, limit_count: int) -> List[str]:
        specific_code_list = self._normalize_specific_stocks(specific_stocks)
        if specific_code_list:
            return specific_code_list

        stock_codes = self._load_target_stock_codes_from_db()
        if not stock_codes:
            logger.warning("[dianjin] 本地数据库股票池为空，降级使用 akshare 拉取股票列表")
            stock_codes = self._load_target_stock_codes_from_akshare()

        if limit_count > 0:
            stock_codes = stock_codes[:limit_count]
        return stock_codes

    def _load_target_stock_codes_from_db(self) -> List[str]:
        try:
            db = get_mongo_db_sync()
            collection = db["stock_basic_info"]
            cursor = collection.find(
                {
                    "code": {"$regex": r"^(60|00|30|68)\d{4}$"},
                    "$or": [
                        {"market": {"$in": ["主板", "创业板", "科创板", "北交所"]}},
                        {"market": {"$exists": False}},
                        {"market": None},
                        {"market": ""}
                    ]
                },
                {"code": 1, "name": 1, "_id": 0}
            )

            codes: List[str] = []
            seen = set()
            for item in cursor:
                code = str(item.get("code") or "").zfill(6)
                name = str(item.get("name") or "")
                if not is_a_share(code) or is_risk_stock(name) or code in seen:
                    continue
                seen.add(code)
                codes.append(code)

            logger.info("[dianjin] 从本地数据库加载股票池成功: %s", len(codes))
            return codes
        except Exception as exc:
            logger.warning("[dianjin] 从本地数据库加载股票池失败: %s", exc)
            return []

    def _load_target_stock_codes_from_akshare(self) -> List[str]:
        stock_data = ak.stock_info_a_code_name()
        stock_data["code_str"] = stock_data["code"].astype(str).str.zfill(6)
        stock_data = stock_data[stock_data["code_str"].map(is_a_share)]
        stock_data = stock_data[~stock_data["name"].map(is_risk_stock)]
        stock_data = stock_data.drop_duplicates("code").reset_index(drop=True)
        return stock_data["code_str"].tolist()

    def _normalize_specific_stocks(self, specific_stocks: Any) -> List[str]:
        if isinstance(specific_stocks, list):
            candidates = [str(item).strip() for item in specific_stocks]
        else:
            text = str(specific_stocks or "").replace("，", ",")
            candidates = [item.strip() for item in text.split(",")]
        return [code for code in candidates if is_a_share(code)]

    def _fetch_realtime_records(self, stock_codes: List[str]) -> List[Dict[str, Any]]:
        batches = [
            stock_codes[index:index + self.REALTIME_BATCH_SIZE]
            for index in range(0, len(stock_codes), self.REALTIME_BATCH_SIZE)
        ]

        records: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.REALTIME_MAX_WORKERS) as executor:
            futures = [executor.submit(self._fetch_realtime_batch, batch) for batch in batches]
            for future in as_completed(futures):
                try:
                    records.extend(future.result())
                except Exception as exc:
                    logger.warning("[dianjin] 获取实时行情批次失败: %s", exc)
        return records

    def _fetch_realtime_batch(self, batch: List[str]) -> List[Dict[str, Any]]:
        symbols = [("sh" if code.startswith("6") else "sz") + code for code in batch]
        url = "https://qt.gtimg.cn/q=" + ",".join(symbols)

        response = requests.get(url, timeout=(5, 15), headers=self.DEFAULT_HEADERS)
        response.encoding = "gbk"
        rows: List[Dict[str, Any]] = []
        for line in response.text.split(";"):
            if "v_pv_none_match" in line or not line.strip():
                continue
            match = re.search(r'v_\w+="(.+?)"', line)
            if not match:
                continue
            fields = match.group(1).split("~")
            if len(fields) < 65:
                continue

            code = str(fields[2]).strip().zfill(6)
            price = safe_float(fields[3])
            if price <= 0:
                continue

            rows.append(
                {
                    "code": code,
                    "name": fields[1].strip(),
                    "price": price,
                    "pe_ttm": safe_float(fields[39]),
                    "dividend_yield": safe_float(fields[64]),
                    "market_cap": safe_float(fields[44]),
                    "pb": safe_float(fields[46]) if len(fields) > 46 else 0.0,
                }
            )
        return rows

    def _apply_first_filter(
        self,
        realtime_records: List[Dict[str, Any]],
        min_pe: float,
        max_pe: float,
        min_dividend: float,
        max_dividend: float,
        min_market_cap: float,
        min_pb: Optional[float],
        max_pb: Optional[float],
    ) -> List[Dict[str, Any]]:
        df = pd.DataFrame(realtime_records)
        if df.empty:
            return []

        pe_mask = (df["pe_ttm"] >= min_pe) & (df["pe_ttm"] <= max_pe)
        div_mask = (df["dividend_yield"] >= min_dividend) & (df["dividend_yield"] <= max_dividend)
        cap_mask = df["market_cap"] >= min_market_cap
        mask = pe_mask & div_mask & cap_mask

        if min_pb is not None and max_pb is not None:
            pb_mask = (df["pb"] >= float(min_pb)) & (df["pb"] <= float(max_pb))
            mask = mask & pb_mask

        filtered_df = df[mask].copy()
        return filtered_df.to_dict("records")

    def _filter_by_ma120(
        self,
        records: List[Dict[str, Any]],
        ratio_threshold: float,
        kline_days: int,
    ) -> List[Dict[str, Any]]:
        passed: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.KLINE_MAX_WORKERS) as executor:
            futures = [executor.submit(self._fetch_and_check_kline, record, ratio_threshold, kline_days) for record in records]
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as exc:
                    logger.warning("[dianjin] K线校验失败: %s", exc)
                    continue
                if result:
                    passed.append(result)

        passed.sort(key=lambda item: item.get("ma120_ratio", 999))
        return passed

    def _fetch_and_check_kline(
        self,
        record: Dict[str, Any],
        ratio_threshold: float,
        kline_days: int,
    ) -> Optional[Dict[str, Any]]:
        code = str(record["code"])
        symbol = ("sh" if code.startswith("6") else "sz") + code
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{kline_days},qfq"

        response = requests.get(url, timeout=(5, 15), headers=self.DEFAULT_HEADERS)
        payload = response.json()
        stock_payload = payload.get("data", {}).get(symbol, {})
        klines = stock_payload.get("qfqday") or stock_payload.get("day") or []

        closes: List[float] = []
        for item in klines:
            if len(item) >= 3:
                close = safe_float(item[2])
                if close > 0:
                    closes.append(close)

        if len(closes) < 120:
            return None

        ma120 = sum(closes[-120:]) / 120.0
        if ma120 <= 0:
            return None

        current_price = safe_float(record.get("price"))
        ratio = current_price / ma120
        if ratio > ratio_threshold:
            return None

        enriched = dict(record)
        enriched["ma120_ratio"] = ratio
        return enriched

    def _three_years(self) -> List[int]:
        current_year = datetime.now().year
        return [current_year - 1, current_year - 2, current_year - 3]

    def _enrich_three_year_dividend(self, records: List[Dict[str, Any]]) -> List[int]:
        years = self._three_years()
        with ThreadPoolExecutor(max_workers=self.DIVIDEND_MAX_WORKERS) as executor:
            futures = [executor.submit(self._fill_dividend_record, record, years) for record in records]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.warning("[dianjin] 三年股息率查询失败: %s", exc)
        return years

    def _fill_dividend_record(self, record: Dict[str, Any], years: List[int]) -> None:
        code = str(record["code"])
        try:
            dividends_by_year = self._fetch_dividend_history(code, years)
            prices_by_year = self._fetch_year_end_prices(code, years)

            dividend_rates: List[float] = []
            for year in years:
                total_dividend = dividends_by_year.get(year, 0.0)
                year_end_price = prices_by_year.get(year, 0.0)
                if total_dividend > 0 and year_end_price > 0:
                    dividend_rates.append((total_dividend / year_end_price) * 100)
                else:
                    dividend_rates.append(0.0)

            record["three_year_dividend"] = dividend_rates
            record["three_year_dividend_pass"] = any(rate >= 3.0 for rate in dividend_rates)
            record["three_year_all_pass"] = all(rate >= 3.0 for rate in dividend_rates)
        except Exception:
            record["three_year_dividend"] = [0.0, 0.0, 0.0]
            record["three_year_dividend_pass"] = False
            record["three_year_all_pass"] = False

    def _fetch_dividend_history(self, code: str, years: List[int]) -> Dict[int, float]:
        url = "https://datacenter.eastmoney.com/api/data/v1/get"
        params = {
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "50",
            "pageNumber": "1",
            "reportName": "RPT_SHAREBONUS_DET",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "source": "WEB",
            "client": "WEB",
        }
        response = requests.get(url, params=params, timeout=(5, 15), headers=self.DEFAULT_HEADERS)
        payload = response.json()
        items = payload.get("result", {}).get("data", []) if payload.get("result") else []

        totals = {year: 0.0 for year in years}
        for item in items:
            report_date = item.get("REPORT_DATE", "")
            if not report_date:
                continue
            try:
                year = int(report_date[:4])
            except (TypeError, ValueError):
                continue
            if year not in totals:
                continue
            cash = item.get("PRETAX_BONUS_RMB")
            if cash:
                totals[year] += safe_float(cash) / 10.0
        return totals

    def _fetch_year_end_prices(self, code: str, years: List[int]) -> Dict[int, float]:
        symbol = ("sh" if code.startswith("6") else "sz") + code
        prices: Dict[int, float] = {}
        for year in years:
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{year}-12-15,{year}-12-31,10,qfq"
            try:
                response = requests.get(url, timeout=(5, 15), headers=self.DEFAULT_HEADERS)
                payload = response.json()
                stock_payload = payload.get("data", {}).get(symbol, {})
                klines = stock_payload.get("qfqday") or stock_payload.get("day") or []
                if klines:
                    close = safe_float(klines[-1][2])
                    if close > 0:
                        prices[year] = close
            except Exception:
                continue
        return prices
