import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "external_skill_templates" / "dupont_analysis_skill.py"
MODULE_SPEC = importlib.util.spec_from_file_location("dupont_analysis_skill", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
dupont_skill = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(dupont_skill)


def test_analyze_a_share_dupont_uses_average_bases_and_quarter_annualization(monkeypatch):
    monkeypatch.setattr(
        dupont_skill,
        "get_stock_basic_info",
        lambda symbol: {"name": "测试公司", "industry": "白酒"},
    )
    monkeypatch.setattr(
        dupont_skill,
        "get_stock_financial_periods",
        lambda symbol, limit=8: [
            {
                "report_period": "20240930",
                "roe": 24.0,
                "netprofit_margin": 30.0,
                "gross_margin": 60.0,
                "revenue": 300.0,
                "total_assets": 1000.0,
                "total_equity": 500.0,
            },
            {
                "report_period": "20240630",
                "roe": 20.0,
                "netprofit_margin": 28.0,
                "gross_margin": 58.0,
                "revenue": 180.0,
                "total_assets": 900.0,
                "total_equity": 450.0,
            },
        ],
    )

    result = dupont_skill.analyze_a_share_dupont("600519", periods=2)

    latest = result["latest_dupont"]
    assert latest["annualization_factor"] == 4.0 / 3.0
    assert latest["average_total_assets"] == 950.0
    assert latest["average_total_equity"] == 475.0
    assert round(latest["asset_turnover"], 6) == round((300.0 * (4.0 / 3.0)) / 950.0, 6)
    assert round(latest["equity_multiplier"], 6) == round(950.0 / 475.0, 6)


def test_analyze_a_share_dupont_preserves_zero_values(monkeypatch):
    monkeypatch.setattr(
        dupont_skill,
        "get_stock_basic_info",
        lambda symbol: {"name": "测试公司", "industry": "制造业"},
    )
    monkeypatch.setattr(
        dupont_skill,
        "get_stock_financial_periods",
        lambda symbol, limit=8: [
            {
                "report_period": "20241231",
                "roe": 0.0,
                "netprofit_margin": 0.0,
                "gross_margin": 0.0,
                "revenue": 0.0,
                "total_assets": 1000.0,
                "total_equity": 400.0,
            },
            {
                "report_period": "20240930",
                "roe": 1.0,
                "netprofit_margin": 2.0,
                "gross_margin": 3.0,
                "revenue": 10.0,
                "total_assets": 900.0,
                "total_equity": 350.0,
            },
        ],
    )

    result = dupont_skill.analyze_a_share_dupont("600519", periods=2)
    latest = result["latest_dupont"]

    assert latest["roe_percent"] == 0.0
    assert latest["net_margin_percent"] == 0.0
    assert latest["gross_margin_percent"] == 0.0
    assert latest["asset_turnover"] == 0.0