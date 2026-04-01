from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.skill_runtime.data_access import get_stock_valuation_context, get_stock_financial_data


def main():
    symbol = "600519"
    ctx = get_stock_valuation_context(symbol)
    print("=== valuation context ===")
    print("current_price:", ctx.get("current_price"))
    print("pe_ttm:", ctx.get("pe_ttm"))
    print("pb:", ctx.get("pb"))
    print("ps_ttm:", ctx.get("ps_ttm"))

    financial_data = ctx.get("financial_data") or []
    print("financial_data_count:", len(financial_data))

    for idx, item in enumerate(financial_data[:3], start=1):
        print(f"--- financial[{idx}] top-level keys ---")
        print(sorted(item.keys()))
        print("report_period:", item.get("report_period"))
        print("report_date:", item.get("report_date"))
        print("net_profit:", item.get("net_profit"))
        print("net_income:", item.get("net_income"))
        raw_data = item.get("raw_data") if isinstance(item, dict) else None
        indicators = raw_data.get("financial_indicators") if isinstance(raw_data, dict) else None
        if isinstance(indicators, dict):
            print("financial_indicators keys:", sorted(indicators.keys())[:40])
            print("netprofit_yoy:", indicators.get("netprofit_yoy"))
            print("growth_YOYNI:", indicators.get("growth_YOYNI"))
            print("basic_eps_yoy:", indicators.get("basic_eps_yoy"))
        else:
            print("financial_indicators: None")

    print("=== direct get_stock_financial_data ===")
    direct_fin = get_stock_financial_data(symbol, limit=8)
    print("direct_financial_count:", len(direct_fin))
    for idx, item in enumerate(direct_fin[:5], start=1):
        print(f"#{idx}", {
            "report_period": item.get("report_period"),
            "report_date": item.get("report_date"),
            "net_profit": item.get("net_profit"),
            "net_income": item.get("net_income"),
        })


if __name__ == "__main__":
    main()
