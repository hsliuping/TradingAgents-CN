"""基本面因子毛利率字段优先级测试。"""

from core.skill_runtime import fundamental_factors


def test_estimate_gross_margin_prefers_grossprofit_margin_over_raw_gross_margin() -> None:
    record = {
        "financial_indicators": {
            "gross_margin": 139609610.88,
            "grossprofit_margin": 26.8,
        }
    }

    assert fundamental_factors._estimate_gross_margin(record) == 26.8