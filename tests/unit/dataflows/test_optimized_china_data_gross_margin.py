"""统一基本面工具毛利率解析测试。"""

from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider


def test_parse_mongodb_financial_data_prefers_reasonable_grossprofit_margin() -> None:
    provider = OptimizedChinaDataProvider.__new__(OptimizedChinaDataProvider)
    financial_data = {
        "roe": 11.6,
        "roa": 0.84,
        "gross_margin": 139609610.88,
        "netprofit_margin": 12.9,
        "debt_to_assets": 45.2,
        "current_ratio": 1.6,
        "quick_ratio": 1.2,
        "cash_ratio": 0.8,
        "raw_data": {
            "financial_indicators": [
                {
                    "gross_margin": 139609610.88,
                    "grossprofit_margin": 26.8,
                }
            ]
        },
    }

    result = provider._parse_mongodb_financial_data(financial_data, 10.0)

    assert result.get("gross_margin") == "26.8%"