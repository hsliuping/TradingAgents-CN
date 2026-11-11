from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.skill_runtime import standard_financial_apis as api


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, key, direction=1):
        reverse = direction == -1
        self.rows.sort(key=lambda row: str(row.get(key) or ""), reverse=reverse)
        return self

    def limit(self, limit):
        self.rows = self.rows[:limit]
        return self

    def __iter__(self):
        return iter(self.rows)


class FakeCollection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def find(self, *args, **kwargs):
        return FakeCursor(self.rows)


class FakeDb:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def __getitem__(self, name):
        return FakeCollection(self.rows)


@pytest.fixture
def sample_financial_records():
    return [
        {
            "report_period": f"{year}1231",
            "revenue": 1000 + (year - 2020) * 100,
            "net_profit": 200 + (year - 2020) * 20,
            "roe": 18 + (year - 2020),
            "roa": 10 + (year - 2020) * 0.5,
            "roic": 15 + (year - 2020) * 0.4,
            "gross_margin": 50 + (year - 2020),
            "netprofit_margin": 20 + (year - 2020) * 0.5,
            "operating_margin": 25 + (year - 2020) * 0.6,
            "oper_exp": 50,
            "admin_exp": 30,
            "fin_exp": 10,
            "n_cashflow_act": 220 + (year - 2020) * 22,
            "capex": 40,
            "total_assets": 3000 + (year - 2020) * 300,
            "total_liab": 900 + (year - 2020) * 60,
            "total_equity": 2100 + (year - 2020) * 240,
            "current_ratio": 2.0,
            "quick_ratio": 1.5,
            "source": "unit",
        }
        for year in range(2024, 2019, -1)
    ]


def test_price_risk_apis_compute_returns_volatility_and_drawdown(monkeypatch):
    rows = [
        {"trade_date": "20240101", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1000},
        {"trade_date": "20240102", "open": 10, "high": 12, "low": 10, "close": 12, "volume": 1100},
        {"trade_date": "20240103", "open": 12, "high": 12, "low": 8, "close": 9, "volume": 1200},
        {"trade_date": "20240104", "open": 9, "high": 10, "low": 8, "close": 10, "volume": 1300},
    ]
    monkeypatch.setattr(api, "get_stock_daily_quotes", lambda *args, **kwargs: rows)

    prices = api.get_adjusted_price_series("SH600519", start_date="2024-01-01", end_date="2024-01-04")
    assert prices["status"] == "success"
    assert prices["symbol"] == "600519"
    assert len(prices["records"]) == 4

    returns = api.get_return_series("600519", start_date="2024-01-01", end_date="2024-01-04")
    assert returns["coverage"]["return_sample_count"] == 3
    assert returns["records"][1]["return"] == pytest.approx(0.2)

    volatility = api.get_volatility_metrics("600519", start_date="2024-01-01", end_date="2024-01-04")
    assert volatility["status"] == "success"
    assert volatility["metrics"]["sample_count"] == 3
    assert volatility["metrics"]["annualized_volatility"] is not None

    drawdown = api.get_drawdown_metrics("600519", start_date="2024-01-01", end_date="2024-01-04")
    assert drawdown["status"] == "success"
    assert drawdown["metrics"]["max_drawdown"] == pytest.approx(-0.25)
    assert drawdown["metrics"]["max_drawdown_start"] == "2024-01-02"

    risk = api.get_single_stock_risk_profile("600519", start_date="2024-01-01", end_date="2024-01-04")
    assert risk["status"] == "insufficient_data"
    assert risk["metrics"]["sample_count"] == 3
    assert risk["metrics"]["worst_return"] == pytest.approx(-0.25)

    technical_rows = [
        {
            "trade_date": f"202401{day:02d}",
            "open": 10 + day * 0.1,
            "high": 11 + day * 0.1,
            "low": 9 + day * 0.1,
            "close": 10 + day * 0.1,
            "volume": 1000 + day,
        }
        for day in range(1, 31)
    ]
    monkeypatch.setattr(api, "get_stock_daily_quotes", lambda *args, **kwargs: technical_rows)
    technical = api.get_technical_indicator_series("600519", start_date="2024-01-01", end_date="2024-01-30", limit=30)
    assert technical["status"] == "success"
    assert technical["summary"]["sample_count"] == 30
    assert technical["latest"]["ma20"] is not None
    assert technical["latest"]["atr14"] is not None
    assert technical["latest"]["boll_upper"] >= technical["latest"]["boll_lower"]
    assert technical["latest"]["resistance_20"] >= technical["latest"]["support_20"]


def test_financial_p0_apis_compute_annual_and_solvency(monkeypatch, sample_financial_records):
    monkeypatch.setattr(api, "get_stock_financial_periods", lambda *args, **kwargs: sample_financial_records)

    series = api.get_historical_financial_annual_series("600519", years=5)
    assert series["status"] == "success"
    assert series["coverage"]["available_years"] == 5
    assert series["records"][0]["free_cashflow"] == 268

    stability = api.get_profitability_stability_metrics("600519", years=5)
    assert stability["metrics"]["revenue"]["count"] == 5
    assert stability["metrics"]["net_profit_growth_yoy"]["count"] == 4

    cashflow = api.get_cashflow_quality_trend("600519", years=5)
    assert cashflow["summary"]["ocf_to_net_profit"]["count"] == 5

    solvency = api.get_debt_solvency_trend("600519", years=5)
    assert solvency["status"] == "success"
    assert solvency["trend"][0]["current_ratio"] == 2.0
    assert solvency["summary"]["debt_to_assets"]["count"] == 5

    margin = api.get_margin_stability_metrics("600519", years=5)
    assert margin["status"] == "success"
    assert margin["metrics"]["gross_margin"]["count"] == 5
    assert margin["trend"][0]["expense_ratio"] is not None

    efficiency = api.get_capital_efficiency_trend("600519", years=5)
    assert efficiency["status"] == "success"
    assert efficiency["summary"]["roe"]["count"] == 5
    assert efficiency["trend"][0]["asset_turnover"] is not None

    growth = api.get_growth_quality_metrics("600519", years=5)
    assert growth["status"] == "success"
    assert growth["cagr"]["revenue"] is not None
    assert len(growth["annual_growth"]) == 4


def test_security_and_peer_apis(monkeypatch):
    monkeypatch.setattr(api, "get_stock_basic_info", lambda symbol: {
        "symbol": symbol,
        "name": "贵州茅台",
        "industry": "白酒",
        "total_mv": 10000,
        "pe_ttm": 20,
        "pb": 5,
        "roe": 25,
        "list_date": "20010827",
        "source": "unit",
    })
    monkeypatch.setattr(api, "get_market_quotes", lambda symbol: {"close": 100, "trade_date": "20240628"})
    peers = [
        {"symbol": "000001", "name": "同行A", "industry": "白酒", "pe_ttm": 10, "pb": 2, "roe": 10},
        {"symbol": "000002", "name": "同行B", "industry": "白酒", "pe_ttm": 30, "pb": 8, "roe": 30},
    ]
    monkeypatch.setattr(api, "get_industry_peer_basic_info", lambda *args, **kwargs: peers)
    monkeypatch.setattr(api, "summarize_industry_valuation", lambda *args, **kwargs: {
        "average": 20,
        "median": 20,
        "min": 10,
        "max": 30,
        "count": 2,
        "samples": [{"pe": 10}, {"pe": 30}, {"pb": 2}, {"pb": 8}],
    })

    master = api.get_security_master("600519.SH")
    assert master["status"] == "success"
    assert master["symbol"] == "600519"
    assert master["exchange"] == "SH"

    snapshot = api.get_current_valuation_snapshot("600519")
    assert snapshot["metrics"]["pe_ttm"] == 20

    peer_group = api.get_peer_group("600519", limit=20)
    assert peer_group["coverage"]["peer_count"] == 2

    peer_quality = api.get_peer_relative_quality("600519", metrics=["roe"])
    assert peer_quality["metrics"]["roe"]["peer_count"] == 2
    assert peer_quality["metrics"]["roe"]["peer_percentile"] == pytest.approx(50.0)

    peer_valuation = api.get_peer_relative_valuation("600519", metrics=["pe"])
    assert peer_valuation["metrics"]["pe"]["peer_count"] == 2

    industry = api.get_industry_fundamental_summary("600519", peer_limit=20)
    assert industry["status"] == "success"
    assert industry["coverage"]["peer_count"] == 2
    assert industry["metrics"]["roe"]["count"] == 2


def test_industry_market_and_peer_growth_apis(monkeypatch, sample_financial_records):
    monkeypatch.setattr(api, "get_stock_basic_info", lambda symbol: {
        "symbol": symbol,
        "name": "测试股票",
        "industry": "白酒",
        "roe": 20,
        "source": "unit",
    })
    peers = [
        {"symbol": "000001", "name": "同行A", "industry": "白酒"},
        {"symbol": "000002", "name": "同行B", "industry": "白酒"},
    ]
    monkeypatch.setattr(api, "get_industry_peer_basic_info", lambda *args, **kwargs: peers)
    monkeypatch.setattr(api, "_load_tushare_industry_moneyflow_rows", lambda *args, **kwargs: [
        {"trade_date": "20240102", "industry": "白酒", "pct_change": 1.2, "net_amount": 3.4}
    ])

    price_map = {
        "600519": [10, 12],
        "000001": [10, 11],
        "000002": [10, 9],
    }

    def fake_price(symbol, *args, **kwargs):
        values = price_map.get(symbol, [10, 10])
        return {
            "status": "success",
            "symbol": symbol,
            "records": [
                {"trade_date": "2024-01-01", "close": values[0], "high": values[0] + 1, "low": values[0] - 1, "amount": 100},
                {"trade_date": "2024-01-02", "close": values[1], "high": values[1] + 1, "low": values[1] - 1, "amount": 200, "pct_chg": 1},
            ],
            "warnings": [],
        }

    monkeypatch.setattr(api, "get_adjusted_price_series", fake_price)
    industry_market = api.get_industry_market_performance("600519", start_date="2024-01-01", end_date="2024-01-02", peer_limit=10)
    assert industry_market["status"] == "success"
    assert industry_market["summary"]["peer_count"] == 2
    assert industry_market["summary"]["target_return"] == pytest.approx(0.2)
    assert industry_market["coverage"]["moneyflow_sample_count"] == 1

    growth_map = {
        "600519": {"revenue": 0.2, "net_profit": 0.3, "operating_cashflow": 0.25, "free_cashflow": 0.22},
        "000001": {"revenue": 0.1, "net_profit": 0.1, "operating_cashflow": 0.1, "free_cashflow": 0.1},
        "000002": {"revenue": 0.3, "net_profit": 0.4, "operating_cashflow": 0.2, "free_cashflow": 0.15},
    }
    monkeypatch.setattr(api, "get_growth_quality_metrics", lambda symbol, years=5: {"status": "success", "years_used": years, "cagr": growth_map[symbol]})
    peer_growth = api.get_peer_relative_growth("600519", metrics=["revenue_cagr", "net_profit_cagr"], years=5, peer_limit=10)
    assert peer_growth["status"] == "success"
    assert peer_growth["metrics"]["revenue_cagr"]["peer_count"] == 2
    assert peer_growth["metrics"]["revenue_cagr"]["peer_percentile"] == pytest.approx(50.0)


def test_capital_flow_series_falls_back_to_tushare(monkeypatch):
    monkeypatch.setattr(api, "_get_db", lambda: FakeDb([]))
    monkeypatch.setattr(api, "_load_tushare_moneyflow_rows", lambda *args, **kwargs: [
        {
            "ts_code": "600519.SH",
            "trade_date": "20240102",
            "net_amount": 1234.5,
            "net_amount_rate": 2.5,
            "buy_elg_amount": 300.0,
            "buy_lg_amount": 200.0,
            "buy_md_amount": 100.0,
            "buy_sm_amount": -50.0,
        }
    ])

    flow = api.get_capital_flow_series("600519", start_date="2024-01-01", end_date="2024-01-31")

    assert flow["status"] == "success"
    assert flow["data_source"] == "tushare"
    assert flow["coverage"]["sample_count"] == 1
    assert flow["records"][0]["trade_date"] == "2024-01-02"
    assert flow["records"][0]["main_net_inflow"] == 1234.5
    assert flow["records"][0]["main_net_inflow_pct"] == 2.5
    assert flow["records"][0]["extra_large_net_inflow"] == 300.0
    assert flow["summary"]["positive_flow_ratio"] == 1.0


def test_valuation_percentile_annual_lows(monkeypatch):
    rows = []
    # 2024: 最低 pe 10.0 出现在 2 月 5 日
    for day in range(1, 28):
        rows.append({"trade_date": f"2024-01-{day:02d}", "pe_ttm": 20 + day * 0.1})
    for day in range(1, 20):
        rows.append({"trade_date": f"2024-02-{day:02d}", "pe_ttm": 10.0 if day == 5 else 18 + day * 0.1})
    # 2025: 最低 12.0 出现在 4 月 9 日
    for day in range(1, 20):
        rows.append({"trade_date": f"2025-04-{day:02d}", "pe_ttm": 12.0 if day == 9 else 16 + day * 0.1})
    # 最近窗口: 平段 15.0（当前值）
    for day in range(1, 15):
        rows.append({"trade_date": f"2026-11-{day:02d}", "pe_ttm": 15.0})
    monkeypatch.setattr(
        api,
        "get_external_valuation_data",
        lambda symbol, start, end, **kwargs: {"source": "tushare", "data": rows},
    )

    result = api.get_historical_valuation_percentile("600519", metrics=["pe_ttm"], lookback_years=15)

    assert result["status"] == "success"
    pe = result["metrics"]["pe_ttm"]
    assert pe["status"] == "success"
    assert pe["current_value"] == 15.0
    assert pe["min"] == 10.0
    assert pe["current_vs_min_pct"] == pytest.approx(50.0)
    lows = pe["annual_lows"]
    assert [low["year"] for low in lows] == [2024, 2025, 2026]
    assert lows[0]["value"] == 10.0
    assert lows[0]["date"] == "2024-02-05"
    assert lows[0]["current_vs_low_pct"] == pytest.approx(50.0)
    assert lows[1]["current_vs_low_pct"] == pytest.approx(25.0)
    assert lows[2]["current_vs_low_pct"] == pytest.approx(0.0)


def test_news_proxy_apis_detect_risk_and_announcements(monkeypatch):
    rows = [
        {"title": "公司发布年度报告公告", "publish_time": datetime(2024, 3, 1), "content": "披露年报"},
        {"title": "公司收到监管警示函", "publish_time": datetime(2024, 4, 1), "content": "监管处罚"},
        {"title": "控股股东计划减持", "publish_time": datetime(2024, 5, 1), "content": "减持"},
    ]
    monkeypatch.setattr(api, "get_stock_news_by_date_range", lambda *args, **kwargs: rows)

    announcements = api.get_company_announcements("600519", lookback_days=365)
    assert announcements["status"] == "success"
    assert announcements["coverage"]["announcement_count"] >= 1

    flags = api.get_risk_event_flags("600519", lookback_days=365)
    assert flags["status"] == "success"
    assert "regulatory_penalty" in flags["hit_flags"]
    assert "shareholder_reduction" in flags["hit_flags"]

    timeline = api.get_company_event_timeline("600519", lookback_days=365)
    assert timeline["status"] == "success"
    assert timeline["summary"]["event_count"] == 3
    assert timeline["summary"]["type_counts"]["regulatory_penalty"] == 1
    assert timeline["data_source"] == "stock_news_proxy"


def test_business_segment_shareholder_return_and_portfolio_risk(monkeypatch, sample_financial_records):
    financial_rows = []
    for year in (2024, 2023):
        financial_rows.append({
            "report_period": f"{year}1231",
            "revenue": 1000,
            "net_profit": 200,
            "n_cashflow_act": 240,
            "capex": 40,
            "main_business": [
                {"end_date": f"{year}1231", "bz_type": "产品", "bz_item": "产品A", "bz_sales": 700, "bz_cost": 300},
                {"end_date": f"{year}1231", "bz_type": "产品", "bz_item": "产品B", "bz_sales": 300, "bz_cost": 180},
            ],
        })
    monkeypatch.setattr(api, "get_stock_financial_periods", lambda *args, **kwargs: financial_rows)
    segment = api.get_business_segment_trend("600519", years=2)
    assert segment["status"] == "success"
    assert segment["coverage"]["period_count"] == 2
    assert segment["periods"][0]["concentration"]["top1_share"] == pytest.approx(0.7)

    monkeypatch.setattr(api, "_read_local_collection_rows", lambda *args, **kwargs: ([], None))
    monkeypatch.setattr(api, "_load_tushare_dividend_rows", lambda *args, **kwargs: [
        {"end_date": "20231231", "ann_date": "20240301", "div_proc": "实施", "cash_div_tax": 2.0},
        {"end_date": "20221231", "ann_date": "20230301", "div_proc": "实施", "cash_div_tax": 1.5},
    ])
    # get_shareholder_return_metrics 内部经 get_latest_stock_price 取现价（不经过 get_current_valuation_snapshot），
    # patch 点必须对齐调用链，否则真实库有行情缓存时 monkeypatch 失效
    monkeypatch.setattr(api, "get_latest_stock_price", lambda *args, **kwargs: 100.0)
    monkeypatch.setattr(api, "get_historical_financial_annual_series", lambda *args, **kwargs: {"status": "success", "records": [{"free_cashflow": 200}, {"free_cashflow": 180}]})
    shareholder = api.get_shareholder_return_metrics("600519", years=2)
    assert shareholder["status"] == "success"
    assert shareholder["metrics"]["latest_cash_dividend_per_share"] == 2.0
    assert shareholder["metrics"]["latest_dividend_yield"] == pytest.approx(0.02)

    monkeypatch.setattr(api, "get_security_master", lambda symbol: {"symbol": symbol, "name": symbol, "industry": "测试行业"})
    return_rows = [{"trade_date": f"2024-01-{day:02d}", "return": 0.01 if day % 2 == 0 else -0.005} for day in range(1, 31)]
    monkeypatch.setattr(api, "get_return_series", lambda *args, **kwargs: {"status": "success", "records": return_rows, "coverage": {"return_sample_count": 30}})
    portfolio = api.get_portfolio_risk_profile([
        {"symbol": "600519", "market_value": 60000},
        {"symbol": "000001", "market_value": 40000},
    ], start_date="2024-01-01", end_date="2024-01-30")
    assert portfolio["status"] == "success"
    assert portfolio["metrics"]["sample_count"] == 30
    assert portfolio["metrics"]["top1_weight"] == pytest.approx(0.6)
    assert portfolio["metrics"]["concentration_hhi"] == pytest.approx(0.52)


def test_real_data_smoke_for_core_standard_apis():
    checks = []
    checks.append(api.get_security_master("600519"))
    checks.append(api.get_adjusted_price_series("600519", start_date="2024-01-01", end_date="2024-03-31", limit=80))
    checks.append(api.get_historical_financial_annual_series("600519", years=3))
    checks.append(api.get_current_valuation_snapshot("600519"))

    assert any(item.get("status") == "success" for item in checks), "至少一个标准 API 应能从本地数据取到真实样本"
    price = checks[1]
    if price.get("status") == "success":
        assert price["coverage"]["sample_count"] > 0
    financial = checks[2]
    if financial.get("status") == "success":
        assert financial["coverage"]["available_years"] > 0


def test_real_data_strict_matrix_for_600519():
    results = {
        "security": api.get_security_master("600519"),
        "price": api.get_adjusted_price_series("600519", start_date="2024-01-01", end_date="2024-12-31", limit=300),
        "returns": api.get_return_series("600519", start_date="2024-01-01", end_date="2024-12-31", limit=300),
        "volatility": api.get_volatility_metrics("600519", start_date="2024-01-01", end_date="2024-12-31", limit=300),
        "drawdown": api.get_drawdown_metrics("600519", start_date="2024-01-01", end_date="2024-12-31", limit=300),
        "financial": api.get_historical_financial_annual_series("600519", years=5),
        "stability": api.get_profitability_stability_metrics("600519", years=5),
        "cashflow": api.get_cashflow_quality_trend("600519", years=5),
        "solvency": api.get_debt_solvency_trend("600519", years=5),
        "valuation": api.get_current_valuation_snapshot("600519"),
        "valuation_percentile": api.get_historical_valuation_percentile("600519", metrics=["pe_ttm", "pb"], lookback_years=1),
        "peer_group": api.get_peer_group("600519", limit=20),
        "peer_valuation": api.get_peer_relative_valuation("600519", metrics=["pe", "pb"], peer_limit=50),
        "peer_quality": api.get_peer_relative_quality("600519", metrics=["pb"], peer_limit=50),
        "announcements": api.get_company_announcements("600519", lookback_days=365, limit=20),
        "risk_flags": api.get_risk_event_flags("600519", lookback_days=365, limit=20),
    }

    assert results["security"]["status"] == "success"
    assert results["security"]["name"]
    assert results["security"]["industry"]

    assert results["price"]["status"] == "success"
    assert results["price"]["coverage"]["sample_count"] >= 20
    closes = [row.get("close") for row in results["price"]["records"] if row.get("close") is not None]
    assert closes and all(0 < value < 10000 for value in closes)

    assert results["returns"]["coverage"]["return_sample_count"] >= 20
    return_values = [row.get("return") for row in results["returns"]["records"] if row.get("return") is not None]
    assert return_values and all(-0.5 < value < 0.5 for value in return_values)

    assert results["volatility"]["status"] == "success"
    assert 0 < results["volatility"]["metrics"]["annualized_volatility"] < 3

    assert results["drawdown"]["status"] == "success"
    assert -1 < results["drawdown"]["metrics"]["max_drawdown"] <= 0

    assert results["financial"]["status"] == "success"
    assert results["financial"]["coverage"]["available_years"] >= 3
    assert all((row.get("revenue") or 0) > 0 for row in results["financial"]["records"][:3])

    assert results["stability"]["status"] == "success"
    assert results["stability"]["metrics"]["revenue"]["count"] >= 3

    assert results["cashflow"]["status"] == "success"
    assert len(results["cashflow"]["trend"]) >= 3

    assert results["solvency"]["status"] == "success"
    assert len(results["solvency"]["trend"]) >= 3
    assert all(0 <= (row.get("debt_to_assets") or 0) <= 100 for row in results["solvency"]["trend"] if row.get("debt_to_assets") is not None)

    margin = api.get_margin_stability_metrics("600519", years=5)
    assert margin["status"] == "success"
    assert margin["metrics"]["gross_margin"]["count"] >= 3
    margin_values = [row.get("gross_margin") for row in margin["trend"] if row.get("gross_margin") is not None]
    assert margin_values and all(0 <= value <= 100 for value in margin_values)

    efficiency = api.get_capital_efficiency_trend("600519", years=5)
    assert efficiency["status"] == "success"
    assert len(efficiency["trend"]) >= 3
    roe_values = [row.get("roe") for row in efficiency["trend"] if row.get("roe") is not None]
    assert roe_values and all(-100 <= value <= 200 for value in roe_values)

    growth = api.get_growth_quality_metrics("600519", years=5)
    assert growth["status"] == "success"
    assert len(growth["annual_growth"]) >= 2

    risk_profile = api.get_single_stock_risk_profile("600519", start_date="2024-01-01", end_date="2024-12-31", limit=300)
    assert risk_profile["status"] == "success"
    assert risk_profile["metrics"]["sample_count"] >= 20
    assert -1 < risk_profile["metrics"]["max_drawdown"] <= 0

    assert results["valuation"]["status"] == "success"
    assert 0 < (results["valuation"]["metrics"].get("pe_ttm") or results["valuation"]["metrics"].get("pe") or 0) < 500
    assert 0 < (results["valuation"]["metrics"].get("pb") or results["valuation"]["metrics"].get("pb_mrq") or 0) < 100

    assert results["valuation_percentile"]["status"] == "success"
    for metric in ("pe_ttm", "pb"):
        item = results["valuation_percentile"]["metrics"][metric]
        assert item["sample_count"] >= 60
        assert 0 <= item["percentile"] <= 100

    assert results["peer_group"]["status"] == "success"
    assert results["peer_group"]["coverage"]["peer_count"] >= 5

    assert results["peer_valuation"]["status"] == "success"
    assert results["peer_valuation"]["metrics"]["pe"]["peer_count"] >= 5

    assert results["peer_quality"]["status"] in {"success", "partial_or_no_data"}
    assert results["peer_quality"]["metrics"]["pb"]["peer_count"] >= 5

    industry_summary = api.get_industry_fundamental_summary("600519", peer_limit=50)
    assert industry_summary["status"] == "success"
    assert industry_summary["coverage"]["peer_count"] >= 5
    assert industry_summary["metrics"]["pb"]["count"] >= 5

    capital_flow = api.get_capital_flow_series("600519", start_date="2024-01-01", end_date="2024-12-31", limit=300)
    assert capital_flow["status"] in {"success", "no_data"}
    if capital_flow["status"] == "success":
        assert capital_flow["coverage"]["sample_count"] > 0
        assert all(row.get("trade_date") for row in capital_flow["records"])

    technical = api.get_technical_indicator_series("600519", start_date="2024-01-01", end_date="2024-12-31", limit=300)
    assert technical["status"] == "success"
    assert technical["summary"]["sample_count"] >= 20
    assert technical["latest"].get("ma20") is not None
    assert technical["latest"].get("atr14") is not None
    assert technical["latest"].get("support_20") is not None
    assert technical["latest"].get("resistance_20") is not None

    industry_market = api.get_industry_market_performance("600519", start_date="2024-01-01", end_date="2024-12-31", lookback_days=20, peer_limit=30)
    assert industry_market["status"] in {"success", "no_data"}
    if industry_market["status"] == "success":
        assert industry_market["coverage"]["peer_price_sample_count"] > 0
        industry_return = industry_market["summary"].get("industry_return")
        if industry_return is not None:
            assert -1 < industry_return < 3

    peer_growth = api.get_peer_relative_growth("600519", metrics=["revenue_cagr", "net_profit_cagr"], years=5, peer_limit=20)
    assert peer_growth["status"] in {"success", "partial_or_no_data"}
    if peer_growth["status"] == "success":
        assert peer_growth["metrics"]["revenue_cagr"]["peer_count"] >= 1
        percentile = peer_growth["metrics"]["revenue_cagr"].get("peer_percentile")
        if percentile is not None:
            assert 0 <= percentile <= 100

    events = api.get_company_event_timeline("600519", lookback_days=365, limit=20)
    assert events["status"] in {"success", "no_data"}
    if events["status"] == "success":
        assert events["summary"]["event_count"] >= 1
        assert all(item.get("event_types") for item in events["events"])

    segment = api.get_business_segment_trend("600519", years=3)
    assert segment["status"] in {"success", "no_data"}
    if segment["status"] == "success":
        assert segment["coverage"]["period_count"] >= 1
        first_period = segment["periods"][0]
        assert 0 <= (first_period["concentration"].get("top1_share") or 0) <= 1

    shareholder = api.get_shareholder_return_metrics("600519", years=5)
    assert shareholder["status"] in {"success", "no_data"}
    if shareholder["status"] == "success":
        assert shareholder["coverage"]["dividend_record_count"] >= 1
        dividend_yield = shareholder["metrics"].get("latest_dividend_yield")
        if dividend_yield is not None:
            assert 0 <= dividend_yield <= 0.2

    moat = api.get_moat_metrics("600519", years=5)
    assert moat["status"] == "success"
    assert moat["dimension_status"]["capital_efficiency"] == "success"
    assert (moat["dimensions"]["capital_efficiency"]["summary"].get("roe") or {}).get("count", 0) >= 3
    assert "不做" in moat["note"]

    intrinsic = api.get_intrinsic_value_range("600519", lookback_years=5)
    assert intrinsic["status"] == "success"
    assert (intrinsic["per_share_basis"].get("eps_annual") or 0) > 0
    band = intrinsic["price_band"]["combined"]
    assert band and 0 < band["low"] <= band["neutral"] <= band["high"]
    assert intrinsic["position"].get("pe_percentile") is not None

    portfolio = api.get_portfolio_risk_profile([
        {"symbol": "600519", "market_value": 60000},
        {"symbol": "000001", "market_value": 40000},
    ], start_date="2024-01-01", end_date="2024-12-31", limit=300)
    assert portfolio["status"] in {"success", "insufficient_data"}
    assert portfolio["metrics"]["top1_weight"] == pytest.approx(0.6)
    assert 0 <= portfolio["metrics"]["concentration_hhi"] <= 1
    if portfolio["status"] == "success":
        assert portfolio["metrics"]["sample_count"] >= 20
        assert -1 < portfolio["metrics"]["max_drawdown"] <= 0

    chip = api.get_chip_distribution_context("600519", trade_date="2024-12-31")
    assert chip["status"] in {"success", "no_data", "error"}
    if chip["status"] == "success":
        assert 0 <= (chip["metrics"].get("profit_ratio") or 0) <= 1
        assert (chip["metrics"].get("avg_cost") or 0) > 0

    # 外部接口抖动防护（参照 margin 对账行集防护先例）：茅台一年内公告/新闻必然存在，
    # no_data 说明东财接口网络抖动或限频（远端断连），跳过本轮真连验收，避免把
    # 外部可用性问题误报为代码回归
    if results["announcements"]["status"] == "no_data":
        pytest.skip("公告接口外部拉取失败（no_data），跳过本轮真连验收")
    assert results["announcements"]["status"] == "success"
    assert results["announcements"]["coverage"]["announcement_count"] >= 1

    if results["risk_flags"]["status"] == "no_data":
        pytest.skip("风险事件接口外部拉取失败（no_data），跳过本轮真连验收")
    assert results["risk_flags"]["status"] == "success"
    assert results["risk_flags"]["news_count"] >= 1


def test_moat_metrics_aggregates_dimension_statistics(monkeypatch):
    monkeypatch.setattr(api, "get_capital_efficiency_trend", lambda symbol, years=10: {
        "status": "success", "symbol": symbol, "years_used": years,
        "trend": [
            {"year": 2024, "roe": 20.0, "roa": 10.0, "roic": 15.0},
            {"year": 2023, "roe": 18.0, "roa": 9.0, "roic": 14.0},
            {"year": 2022, "roe": 16.0, "roa": 8.0, "roic": 13.0},
        ],
        "summary": {"roe": {"count": 3, "median": 18.0}, "roa": {"count": 3}, "roic": {"count": 3}},
    })
    monkeypatch.setattr(api, "get_margin_stability_metrics", lambda symbol, years=10: {
        "status": "success", "symbol": symbol, "years_used": years,
        "trend": [{"year": 2024, "gross_margin": 91.0}],
        "metrics": {"gross_margin": {"count": 3, "median": 91.0}, "netprofit_margin": {"count": 3}},
    })
    monkeypatch.setattr(api, "get_cashflow_quality_trend", lambda symbol, years=10: {
        "status": "success", "symbol": symbol, "years_used": years,
        "trend": [{"year": 2024, "ocf_to_net_profit": 1.1}],
        "summary": {"ocf_to_net_profit": {"count": 3, "median": 1.05}},
    })
    monkeypatch.setattr(api, "get_debt_solvency_trend", lambda symbol, years=10: {
        "status": "success", "symbol": symbol, "years_used": years,
        "trend": [{"year": 2024, "debt_to_assets": 20.0}],
        "summary": {"debt_to_assets": {"count": 3, "median": 21.0}},
    })
    monkeypatch.setattr(api, "get_growth_quality_metrics", lambda symbol, years=10: {
        "status": "success", "symbol": symbol, "years_used": years,
        "cagr": {"revenue": 0.10, "net_profit": 0.15},
        "quality_flags": {"revenue_positive_year_ratio": 0.8, "profit_positive_year_ratio": 1.0},
    })
    monkeypatch.setattr(api, "get_shareholder_return_metrics", lambda symbol, years=5, allow_remote_fetch=False: {
        "status": "success", "symbol": symbol,
        "coverage": {"annual_count": years},
        "metrics": {"latest_dividend_yield": 0.02, "dividend_continuity_ratio": 1.0},
    })

    moat = api.get_moat_metrics("600519", years=10)
    assert moat["status"] == "success"
    assert moat["symbol"] == "600519"
    assert set(moat["dimension_status"].values()) == {"success"}
    capital = moat["dimensions"]["capital_efficiency"]
    # 年报序列按年份降序，trend[0] 即最近年报
    assert capital["latest"]["roe"] == 20.0
    assert capital["summary"]["roe"]["count"] == 3
    assert moat["dimensions"]["growth"]["cagr"]["net_profit"] == pytest.approx(0.15)
    assert moat["dimensions"]["shareholder_return"]["metrics"]["latest_dividend_yield"] == pytest.approx(0.02)
    assert "不做" in moat["note"]
    assert moat["warnings"] == []

    # 单维度失败不阻断其余维度
    def _boom(symbol, years=10):
        raise RuntimeError("db down")

    monkeypatch.setattr(api, "get_capital_efficiency_trend", _boom)
    degraded = api.get_moat_metrics("600519", years=10)
    assert degraded["status"] == "success"
    assert degraded["dimension_status"]["capital_efficiency"] == "no_data"
    assert any("资本回报维度计算失败" in item for item in degraded["warnings"])


def test_intrinsic_value_range_builds_price_band_from_centers(monkeypatch):
    monkeypatch.setattr(api, "get_current_valuation_snapshot", lambda symbol: {
        "status": "success", "symbol": symbol, "name": "测试酒业", "current_price": 25.0, "metrics": {},
    })
    monkeypatch.setattr(api, "get_historical_valuation_percentile", lambda symbol, metrics=None, lookback_years=10: {
        "status": "success", "symbol": symbol,
        "metrics": {
            "pe_ttm": {"status": "success", "median": 20.0, "average": 21.0, "min": 10.0, "max": 30.0,
                        "percentile": 55.0, "sample_count": 120},
            "pb": {"status": "success", "median": 4.0, "average": 4.0, "min": 2.0, "max": 6.0,
                    "percentile": 60.0, "sample_count": 120},
        },
    })
    monkeypatch.setattr(api, "get_stock_financial_periods", lambda symbol, limit=40: [
        {"report_period": "20251231", "report_type": "annual", "eps": 1.5, "bps": 15.0},
        {"report_period": "20250930", "report_type": "quarterly"},
    ])

    result = api.get_intrinsic_value_range("600519")
    assert result["status"] == "success"
    assert result["name"] == "测试酒业"
    assert result["current_price"] == 25.0
    basis = result["per_share_basis"]
    assert basis["eps_annual"] == pytest.approx(1.5)
    assert basis["bps_annual"] == pytest.approx(15.0)
    assert basis["eps_period"] == "20251231"
    assert "非 DCF" in result["method_note"]
    pe = result["price_band"]["pe_channel"]
    assert pe["conservative"] == pytest.approx(15.0)
    assert pe["neutral"] == pytest.approx(30.0)
    assert pe["optimistic"] == pytest.approx(45.0)
    pb = result["price_band"]["pb_channel"]
    assert pb["conservative"] == pytest.approx(30.0)
    assert pb["neutral"] == pytest.approx(60.0)
    assert pb["optimistic"] == pytest.approx(90.0)
    combined = result["price_band"]["combined"]
    assert combined["low"] == pytest.approx(15.0)
    assert combined["neutral"] == pytest.approx(45.0)
    assert combined["high"] == pytest.approx(90.0)
    position = result["position"]
    assert position["current_vs_combined"] == "within_band"
    assert position["position_pct"] == pytest.approx((25.0 - 15.0) / (90.0 - 15.0), abs=1e-4)
    assert position["pe_percentile"] == pytest.approx(55.0)
    assert position["pb_percentile"] == pytest.approx(60.0)


def test_intrinsic_value_range_falls_back_to_computed_eps_bps(monkeypatch):
    monkeypatch.setattr(api, "get_current_valuation_snapshot", lambda symbol: {
        "status": "success", "symbol": symbol, "name": "测试制造", "current_price": 10.0, "metrics": {},
    })
    monkeypatch.setattr(api, "get_historical_valuation_percentile", lambda symbol, metrics=None, lookback_years=10: {
        "status": "success", "symbol": symbol,
        "metrics": {"pe_ttm": {"status": "success", "median": 15.0, "average": 15.0, "min": 10.0, "max": 20.0,
                                "percentile": 50.0, "sample_count": 120}},
    })
    # 扁平字段缺 eps/bps（存量数据），用净利润/总股本、净资产/总股本兜底
    monkeypatch.setattr(api, "get_stock_financial_periods", lambda symbol, limit=40: [
        {
            "report_period": "20241231", "report_type": "annual",
            "net_profit": 1500.0, "total_equity": 150000.0,
            "balance_sheet": {"total_share": 10000.0},
        },
    ])

    result = api.get_intrinsic_value_range("600519")
    assert result["status"] == "success"
    basis = result["per_share_basis"]
    assert basis["eps_annual"] == pytest.approx(0.15)
    assert basis["eps_source"].startswith("计算值")
    assert basis["bps_annual"] == pytest.approx(15.0)
    assert basis["bps_source"].startswith("计算值")
    assert result["price_band"]["pb_channel"] is None
    pe = result["price_band"]["pe_channel"]
    assert pe["conservative"] == pytest.approx(1.5)
    assert pe["neutral"] == pytest.approx(2.25)
    assert pe["optimistic"] == pytest.approx(3.0)
    assert any("仅一条通道可用" in item for item in result["warnings"])
    assert result["price_band"]["combined"]["low"] == pytest.approx(1.5)


def test_flatten_financial_period_extracts_eps_bps():
    from core.skill_runtime.data_access import _flatten_financial_period_record

    record = {
        "report_period": "20241231",
        "income_statement": {"n_income_attr_p": 1500.0},
        "balance_sheet": {"total_equity": 150000.0, "total_share": 10000.0},
        "financial_indicators": {"eps": 0.15, "bps": 15.0, "roe": 1.0},
    }
    flattened = _flatten_financial_period_record(record)
    assert flattened["eps"] == pytest.approx(0.15)
    assert flattened["bps"] == pytest.approx(15.0)
    assert flattened["net_profit"] == pytest.approx(1500.0)
    assert flattened["total_equity"] == pytest.approx(150000.0)
