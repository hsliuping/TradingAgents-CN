#!/usr/bin/env python3
"""
直连 Tushare 检查股息率与分红数据是否可用。

用途：
1. 查询指定股票在 recent daily_basic 中是否有 dv_ratio / dv_ttm
2. 查询 Tushare dividend 接口是否能返回分红明细
3. 帮助区分“接口本身没数据”还是“数据库同步没写入”

使用方法：
    python scripts/check_tushare_dividend_data.py --code 600036
    python scripts/check_tushare_dividend_data.py --code 600036 --days 20 --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tradingagents.dataflows.providers.china.tushare import TushareProvider  # noqa: E402


def print_section(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print(f"{'=' * 80}")


def normalize_ts_code(code: str) -> str:
    text = (code or "").strip().upper()
    if "." in text:
        return text
    if text.startswith(("60", "68", "90")):
        return f"{text}.SH"
    if text.startswith(("00", "20", "30")):
        return f"{text}.SZ"
    if text.startswith(("43", "83", "87")):
        return f"{text}.BJ"
    return text


async def find_recent_daily_basic(provider: TushareProvider, ts_code: str, days: int) -> tuple[str | None, list[dict[str, Any]]]:
    today = datetime.now()
    fields = "ts_code,trade_date,close,pe,pb,total_mv,dv_ratio,dv_ttm"

    for offset in range(days):
        trade_date = (today - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            df = await asyncio.to_thread(
                provider.api.daily_basic,
                ts_code=ts_code,
                trade_date=trade_date,
                fields=fields,
            )
        except Exception as exc:
            print(f"[{trade_date}] daily_basic 调用失败: {exc}")
            continue

        if df is None or df.empty:
            continue

        rows = df.to_dict("records")
        return trade_date, rows

    return None, []


async def query_dividend(provider: TushareProvider, ts_code: str, limit: int) -> list[dict[str, Any]]:
    try:
        records = await provider.get_dividend_data(ts_code, limit=limit)
        return records or []
    except Exception as exc:
        print(f"dividend 接口调用失败: {exc}")
        return []


def print_daily_basic_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("未查到 daily_basic 记录")
        return

    for idx, row in enumerate(rows, start=1):
        print(
            f"{idx}. trade_date={row.get('trade_date')}, close={row.get('close')}, pe={row.get('pe')}, "
            f"pb={row.get('pb')}, total_mv={row.get('total_mv')}, dv_ratio={row.get('dv_ratio')}, dv_ttm={row.get('dv_ttm')}"
        )


def print_dividend_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("未查到 dividend 分红记录")
        return

    for idx, row in enumerate(rows, start=1):
        print(
            f"{idx}. end_date={row.get('end_date')}, ann_date={row.get('ann_date')}, div_proc={row.get('div_proc')}, "
            f"cash_div_tax={row.get('cash_div_tax')}, cash_div={row.get('cash_div')}, "
            f"stk_bo_rate={row.get('stk_bo_rate')}, stk_co_rate={row.get('stk_co_rate')}, ex_date={row.get('ex_date')}"
        )


async def main_async(code: str, days: int, limit: int) -> int:
    ts_code = normalize_ts_code(code)

    provider = TushareProvider()
    connected = await provider.connect()
    if not connected or not provider.is_available():
        print_section("连接失败")
        print("Tushare 不可用，请先检查 Web 配置或 .env 中的 TUSHARE_TOKEN。")
        return 1

    print_section("Tushare 连接信息")
    print(f"股票代码: {code}")
    print(f"ts_code: {ts_code}")
    print(f"Token 来源: {getattr(provider, 'token_source', None)}")

    print_section("daily_basic: dv_ratio / dv_ttm")
    found_date, daily_rows = await find_recent_daily_basic(provider, ts_code, days)
    if found_date:
        print(f"命中的最近交易日: {found_date}")
    else:
        print(f"最近 {days} 天未查到 daily_basic 记录")
    print_daily_basic_rows(daily_rows)

    print_section("dividend: 分红明细")
    dividend_rows = await query_dividend(provider, ts_code, limit)
    print_dividend_rows(dividend_rows)

    print_section("结论建议")
    has_daily_dividend = any((row.get("dv_ratio") is not None or row.get("dv_ttm") is not None) for row in daily_rows)
    has_dividend_records = len(dividend_rows) > 0

    print(f"daily_basic 是否有股息率字段值: {has_daily_dividend}")
    print(f"dividend 接口是否有分红记录: {has_dividend_records}")

    if has_daily_dividend and has_dividend_records:
        print("结论: Tushare 接口本身有分红相关数据，数据库未同步大概率是同步字段没取或入库映射缺失。")
    elif (not has_daily_dividend) and has_dividend_records:
        print("结论: Tushare dividend 明细有数据，但 daily_basic 的股息率字段没有返回；高分红筛选不能只依赖 daily_basic。")
    elif has_daily_dividend and (not has_dividend_records):
        print("结论: daily_basic 有股息率，但 dividend 明细没有返回，可能是权限、时间窗口或该股票暂无分红记录。")
    else:
        print("结论: 当前直接查 Tushare 也没有拿到分红/股息率数据，需要进一步确认权限、股票本身是否有分红、或接口参数范围。")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="直连 Tushare 检查股息率与分红数据")
    parser.add_argument("--code", required=True, help="股票代码，例如 600036")
    parser.add_argument("--days", type=int, default=20, help="向前回溯多少天寻找 daily_basic 数据")
    parser.add_argument("--limit", type=int, default=10, help="dividend 接口最多展示多少条记录")
    args = parser.parse_args()
    return asyncio.run(main_async(args.code, args.days, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())