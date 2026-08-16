#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据流通用工具模块单元测试
覆盖 tradingagents/utils/dataflow_utils.py 的保存、日期与装饰器等核心逻辑
"""

import datetime as _dt
import pandas as pd
from unittest import mock

import tradingagents.utils.dataflow_utils as dfu
from tradingagents.utils.dataflow_utils import (
    save_output,
    get_current_date,
    decorate_all_methods,
    get_next_weekday,
    get_trading_date_range,
)


# ---------- save_output：保存 DataFrame ----------

def test_save_output_writes_csv(tmp_path):
    """传入 save_path 时应写出 CSV 文件"""
    df = pd.DataFrame({"code": ["600000"], "close": [10.5]})
    path = tmp_path / "result.csv"

    save_output(df, "result", str(path))

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "code" in content
    assert "600000" in content


def test_save_output_skips_when_no_path(tmp_path):
    """不传 save_path 时不应产生任何文件"""
    df = pd.DataFrame({"code": ["600000"]})
    before = set(tmp_path.iterdir())

    save_output(df, "result", None)

    assert set(tmp_path.iterdir()) == before


# ---------- get_current_date：当前日期 ----------

def test_get_current_date_format():
    """返回的日期应满足 YYYY-MM-DD 格式"""
    real_date = _dt.date
    with mock.patch.object(dfu, "date") as m_date:
        m_date.today.return_value = real_date(2025, 10, 13)
        assert get_current_date() == "2025-10-13"


def test_get_current_date_matches_today():
    """默认行为应等于当天日期"""
    assert get_current_date() == _dt.date.today().strftime("%Y-%m-%d")


# ---------- decorate_all_methods：类方法装饰器 ----------

def test_decorate_all_methods():
    """装饰器应作用于类的所有方法"""
    def plus_one(func):
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs) + 1
        return wrapper

    @decorate_all_methods(plus_one)
    class Example:
        def add(self, x):
            return x

        def double(self, x):
            return x * 2

    instance = Example()
    assert instance.add(1) == 2
    assert instance.double(3) == 7


# ---------- get_next_weekday：下一个工作日 ----------

def test_get_next_weekday_from_string_saturday():
    """2025-10-04 是周六，应返回下周一 2025-10-06"""
    result = get_next_weekday("2025-10-04")
    assert result == _dt.datetime(2025, 10, 6, 0, 0)


def test_get_next_weekday_from_string_sunday():
    """2025-10-05 是周日，应返回下周一 2025-10-06"""
    result = get_next_weekday("2025-10-05")
    assert result == _dt.datetime(2025, 10, 6, 0, 0)


def test_get_next_weekday_from_datetime():
    """传入 datetime 对象也应正常工作"""
    result = get_next_weekday(_dt.datetime(2025, 10, 4))
    assert result == _dt.datetime(2025, 10, 6, 0, 0)


def test_get_next_weekday_on_weekday_returns_same_day():
    """工作日应原样返回"""
    result = get_next_weekday(_dt.datetime(2025, 10, 6))  # 周一
    assert result == _dt.datetime(2025, 10, 6, 0, 0)


# ---------- get_trading_date_range：交易日期范围 ----------

def test_get_trading_date_range_string_target():
    start, end = get_trading_date_range("2025-10-13", 10)
    assert start == "2025-10-03"
    assert end == "2025-10-13"


def test_get_trading_date_range_datetime_target():
    start, end = get_trading_date_range(_dt.datetime(2025, 10, 13, 15, 0, 0), 5)
    assert start == "2025-10-08"
    assert end == "2025-10-13"


def test_get_trading_date_range_none_uses_today():
    """target_date 为空时应以今天为基准"""
    real_dt = _dt.datetime
    with mock.patch("datetime.datetime", wraps=real_dt) as m_dt:
        m_dt.now.return_value = real_dt(2025, 10, 13, 9, 0, 0)
        start, end = get_trading_date_range(None, 5)
    assert end == "2025-10-13"
    assert start == "2025-10-08"


def test_get_trading_date_range_future_date_clamps_to_today():
    """未来日期应回退到今天"""
    real_dt = _dt.datetime
    with mock.patch("datetime.datetime", wraps=real_dt) as m_dt:
        m_dt.now.return_value = real_dt(2025, 10, 13, 9, 0, 0)
        start, end = get_trading_date_range("2026-01-01", 10)
    assert end == "2025-10-13"
    assert start == "2025-10-03"
