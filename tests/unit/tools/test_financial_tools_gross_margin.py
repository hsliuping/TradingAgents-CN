"""专项财务工具毛利率字段优先级测试。"""

from core.tools.implementations.fundamentals import financial_tools


def test_income_analysis_prefers_reasonable_grossprofit_margin(monkeypatch) -> None:
    payload = {
        "report_period": "20240930",
        "revenue": 12800000000,
        "revenue_ttm": 25600000000,
        "net_profit": 1680000000,
        "net_profit_ttm": 3360000000,
        "oper_profit": 2100000000,
        "oper_cost": 9100000000,
        "gross_margin": 139609610.88,
        "netprofit_margin": 12.9,
        "rd_exp": 250000000,
        "raw_data": {
            "income_statement": [],
            "financial_indicators": [
                {
                    "end_date": "20240930",
                    "gross_margin": 139609610.88,
                    "grossprofit_margin": 26.8,
                    "netprofit_margin": 12.9,
                    "roe": 11.6,
                }
            ],
        },
    }

    monkeypatch.setattr(
        financial_tools,
        "_get_financial_data_from_cache_or_api",
        lambda ticker, limit=8: payload,
    )

    result = financial_tools.get_income_analysis.invoke({"ticker": "000001", "periods": 4})

    assert "- **毛利率**: 26.80%" in result
    assert "139609610.88%" not in result
