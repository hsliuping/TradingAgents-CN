"""
验证 Tushare margin 接口是否返回全市场两融汇总数据。

功能：
1. 从仓库根目录 .env 读取 TUSHARE_TOKEN
2. 调用 Tushare `margin` 接口
3. 检查每个交易日返回了哪些交易所（SSE/SZSE/BSE）
4. 输出最近交易日的覆盖情况，帮助判断是否只拿到了上证数据

用法示例：
  python scripts/validation/validate_tushare_margin_coverage.py
  python scripts/validation/validate_tushare_margin_coverage.py --trade-date 20260411
  python scripts/validation/validate_tushare_margin_coverage.py --start-date 20260320 --end-date 20260411
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
from typing import Dict, Iterable, Optional, Set

import pandas as pd
import tushare as ts


EXPECTED_EXCHANGES: Set[str] = {"SSE", "SZSE", "BSE"}


def _parse_env_file(env_path: Path) -> Dict[str, str]:
    """读取 .env 的键值对，忽略注释和空行。"""
    values: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _load_tushare_token(repo_root: Path) -> str:
    """优先读取环境变量，其次读取仓库 .env。"""
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if token:
        return token

    env_path = repo_root / ".env"
    if not env_path.exists():
        raise RuntimeError("未找到 .env，且环境变量 TUSHARE_TOKEN 为空")

    env_values = _parse_env_file(env_path)
    token = env_values.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError(".env 中未找到 TUSHARE_TOKEN")

    return token


def _normalize_date(date_str: str) -> str:
    clean = date_str.strip().replace("-", "")
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"日期格式错误: {date_str}，期望 YYYYMMDD 或 YYYY-MM-DD")
    return clean


def _default_date_range() -> tuple[str, str]:
    end = dt.date.today()
    start = end - dt.timedelta(days=20)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _format_yyyymmdd(date_str: str) -> str:
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def _safe_sum(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    return pd.to_numeric(df[column], errors="coerce").fillna(0).sum()


def _print_group_summary(df: pd.DataFrame, trade_dates: Iterable[str]) -> None:
    print("\n=== 每个交易日交易所覆盖情况 ===")
    for trade_date in trade_dates:
        day_df = df[df["trade_date"] == trade_date]
        exchanges = sorted(set(day_df["exchange_id"].dropna().astype(str)))
        exchange_set = set(exchanges)
        missing = sorted(EXPECTED_EXCHANGES - exchange_set)
        coverage_text = "完整" if not missing else f"缺失: {','.join(missing)}"

        rzye = _safe_sum(day_df, "rzye") / 100000000
        rqye = _safe_sum(day_df, "rqye") / 100000000
        rzrqye = _safe_sum(day_df, "rzrqye") / 100000000

        print(
            f"{trade_date} ({_format_yyyymmdd(trade_date)}): "
            f"交易所={exchanges} | 覆盖={coverage_text} | "
            f"融资余额={rzye:.2f}亿 融券余额={rqye:.2f}亿 两融余额={rzrqye:.2f}亿"
        )


def _query_margin(
    pro,
    trade_date: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> pd.DataFrame:
    if trade_date:
        return pro.margin(trade_date=trade_date)
    return pro.margin(start_date=start_date, end_date=end_date)


def main() -> None:
    parser = argparse.ArgumentParser(description="验证 Tushare 两融汇总是否覆盖全部交易所")
    parser.add_argument("--trade-date", type=str, default=None, help="单日查询，YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--start-date", type=str, default=None, help="开始日期，YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="结束日期，YYYYMMDD 或 YYYY-MM-DD")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    token = _load_tushare_token(repo_root)
    ts.set_token(token)
    pro = ts.pro_api()

    trade_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    if args.trade_date:
        trade_date = _normalize_date(args.trade_date)
        print(f"查询模式: 单日 trade_date={trade_date}")
    else:
        if args.start_date and args.end_date:
            start_date = _normalize_date(args.start_date)
            end_date = _normalize_date(args.end_date)
        else:
            start_date, end_date = _default_date_range()
        print(f"查询模式: 区间 start_date={start_date}, end_date={end_date}")

    df = _query_margin(pro, trade_date, start_date, end_date)
    if df is None or df.empty:
        print("未获取到 margin 数据。可能原因：日期无数据、积分权限不足、网络问题。")
        return

    required_columns = {"trade_date", "exchange_id", "rzye", "rqye", "rzrqye"}
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        print(f"返回字段缺失: {missing_columns}")
        print(f"实际字段: {list(df.columns)}")
        return

    df = df.copy()
    df["trade_date"] = df["trade_date"].astype(str)

    unique_dates = sorted(df["trade_date"].unique(), reverse=True)
    print(f"\n总行数: {len(df)}")
    print(f"交易日数量: {len(unique_dates)}")
    print(f"返回字段: {list(df.columns)}")

    # 打印最近最多 10 个交易日的覆盖情况
    _print_group_summary(df, unique_dates[:10])

    latest = unique_dates[0]
    latest_df = df[df["trade_date"] == latest]
    latest_exchanges = set(latest_df["exchange_id"].dropna().astype(str))
    latest_missing = sorted(EXPECTED_EXCHANGES - latest_exchanges)

    print("\n=== 最近交易日结论 ===")
    print(f"最近交易日: {latest} ({_format_yyyymmdd(latest)})")
    print(f"交易所集合: {sorted(latest_exchanges)}")
    if latest_missing:
        print(f"结论: 数据不完整，缺失交易所 {latest_missing}")
    else:
        print("结论: 数据覆盖完整（SSE/SZSE/BSE 均存在）")


if __name__ == "__main__":
    main()
