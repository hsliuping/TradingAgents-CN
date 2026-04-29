from app.services.financial_data_service import FinancialDataService


def test_extract_latest_period_and_indicators_from_akshare_matrix_records():
    service = FinancialDataService()

    financial_data = {
        "main_indicators": [
            {"指标": "营业总收入", "20260331": 129131041000.0, "20251231": 423701834000.0},
            {"指标": "归母净利润", "20260331": 20737710000.0, "20251231": 72201280000.0},
            {"指标": "股东权益合计(净资产)", "20260331": 394232291000.0, "20251231": 371026300000.0},
            {"指标": "净资产收益率_平均", "20260331": 5.973097, "20251231": 24.72487},
            {"指标": "资产负债率", "20260331": 62.32234, "20251231": 61.93928},
        ],
        "balance_sheet": [],
        "income_statement": [],
    }

    period = service._extract_latest_period(financial_data)
    indicators = service._extract_akshare_indicators(financial_data)

    assert period == "20260331"
    assert indicators["revenue"] == 129131041000.0
    assert indicators["net_income"] == 20737710000.0
    assert indicators["total_equity"] == 394232291000.0
    assert indicators["roe"] == 5.973097
    assert indicators["debt_to_assets"] == 62.32234