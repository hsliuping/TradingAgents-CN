"""测试板块资金流向多日聚合功能"""
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

import asyncio


async def test_tushare_api():
    """Test 1: Tushare API date range support"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider
    p = TushareProvider()
    await p.connect()

    print("=== Test moneyflow_ind_ths with date range ===")
    df = await p.get_moneyflow_ind_ths(start_date='20260201', end_date='20260213')
    if df is not None and not df.empty:
        dates = sorted(df['trade_date'].unique())
        print(f"OK: {len(df)} rows, {len(dates)} trading days")
        print(f"Dates: {dates}")
    else:
        print("FAILED: empty result")

    print()
    print("=== Test moneyflow_cnt_ths with date range ===")
    df = await p.get_moneyflow_cnt_ths(start_date='20260201', end_date='20260213')
    if df is not None and not df.empty:
        dates = sorted(df['trade_date'].unique())
        print(f"OK: {len(df)} rows, {len(dates)} trading days")
        print(f"Dates: {dates}")
    else:
        print("FAILED: empty result")


async def test_sector_rotation():
    """Test 2: get_sector_rotation with lookback_days"""
    from core.tools.sector_tools import get_sector_rotation

    print("\n" + "=" * 60)
    print("=== Test get_sector_rotation lookback_days=30 ===")
    print("=" * 60)
    result = await get_sector_rotation(
        trade_date='2026-02-13',
        top_n=5,
        lookback_days=30
    )
    print(result)


def test_tool_registration():
    """Test 3: Tool registration with new parameter"""
    from core.tools.config import BUILTIN_TOOLS
    from core.tools.fc_converter import tool_metadata_to_openai

    tool_meta = BUILTIN_TOOLS.get('get_fund_flow_data')
    if not tool_meta:
        print("FAILED: get_fund_flow_data not in BUILTIN_TOOLS")
        return

    openai_tool = tool_metadata_to_openai(tool_meta)
    params = openai_tool['function']['parameters']['properties']
    print(f"\n=== get_fund_flow_data OpenAI tool schema ===")
    print(f"Parameters: {list(params.keys())}")
    if 'lookback_days' in params:
        print(f"lookback_days: {params['lookback_days']}")
        print("OK: lookback_days parameter present")
    else:
        print("FAILED: lookback_days parameter missing")


async def main():
    await test_tushare_api()
    await test_sector_rotation()
    test_tool_registration()


if __name__ == '__main__':
    asyncio.run(main())

