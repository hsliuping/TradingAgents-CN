"""
交易时间判断工具模块

提供统一的交易时间判断逻辑，用于判断当前是否在A股交易时间内。
"""

from datetime import datetime, time as dtime
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.config import settings


def is_trading_time(now: Optional[datetime] = None) -> bool:
    """
    判断是否在A股交易时间或收盘后缓冲期

    交易时间：
    - 上午：9:30-11:30
    - 下午：13:00-15:00
    - 收盘后缓冲期：15:00-15:30（确保获取到收盘价）

    收盘后缓冲期说明：
    - 交易时间结束后继续获取30分钟
    - 假设6分钟一次，可以增加5次同步机会
    - 大大降低错过收盘价的风险

    Args:
        now: 指定时间，默认为当前时间（使用配置的时区）

    Returns:
        bool: 是否在交易时间内
    """
    tz = ZoneInfo(settings.TIMEZONE)
    now = now or datetime.now(tz)
    
    # 工作日 Mon-Fri
    if now.weekday() > 4:
        return False
    
    t = now.time()
    
    # 上交所/深交所常规交易时段
    morning = dtime(9, 30)
    noon = dtime(11, 30)
    afternoon_start = dtime(13, 0)
    # 收盘后缓冲期（延长30分钟到15:30）
    buffer_end = dtime(15, 30)
    
    return (morning <= t <= noon) or (afternoon_start <= t <= buffer_end)


def is_strict_trading_time(now: Optional[datetime] = None) -> bool:
    """
    判断是否在严格的A股交易时间内（不包含缓冲期）

    交易时间：
    - 上午：9:30-11:30
    - 下午：13:00-15:00

    Args:
        now: 指定时间，默认为当前时间（使用配置的时区）

    Returns:
        bool: 是否在严格交易时间内
    """
    tz = ZoneInfo(settings.TIMEZONE)
    now = now or datetime.now(tz)
    
    # 工作日 Mon-Fri
    if now.weekday() > 4:
        return False
    
    t = now.time()
    
    # 上交所/深交所常规交易时段
    morning = dtime(9, 30)
    noon = dtime(11, 30)
    afternoon_start = dtime(13, 0)
    afternoon_end = dtime(15, 0)
    
    return (morning <= t <= noon) or (afternoon_start <= t <= afternoon_end)


def is_pre_market_time(now: Optional[datetime] = None) -> bool:
    """
    判断是否在盘前时间（9:00-9:30）

    Args:
        now: 指定时间，默认为当前时间（使用配置的时区）

    Returns:
        bool: 是否在盘前时间
    """
    tz = ZoneInfo(settings.TIMEZONE)
    now = now or datetime.now(tz)
    
    # 工作日 Mon-Fri
    if now.weekday() > 4:
        return False
    
    t = now.time()
    pre_market_start = dtime(9, 0)
    pre_market_end = dtime(9, 30)
    
    return pre_market_start <= t < pre_market_end


def is_after_market_time(now: Optional[datetime] = None) -> bool:
    """
    判断是否在盘后时间（15:00-15:30）

    Args:
        now: 指定时间，默认为当前时间（使用配置的时区）

    Returns:
        bool: 是否在盘后时间
    """
    tz = ZoneInfo(settings.TIMEZONE)
    now = now or datetime.now(tz)
    
    # 工作日 Mon-Fri
    if now.weekday() > 4:
        return False
    
    t = now.time()
    after_market_start = dtime(15, 0)
    after_market_end = dtime(15, 30)
    
    return after_market_start <= t <= after_market_end


def get_trading_status(now: Optional[datetime] = None) -> str:
    """
    获取当前交易状态

    Args:
        now: 指定时间，默认为当前时间（使用配置的时区）

    Returns:
        str: 交易状态
            - "pre_market": 盘前
            - "morning_session": 上午交易时段
            - "noon_break": 午间休市
            - "afternoon_session": 下午交易时段
            - "after_market": 盘后缓冲期
            - "closed": 休市
    """
    tz = ZoneInfo(settings.TIMEZONE)
    now = now or datetime.now(tz)
    
    # 周末
    if now.weekday() > 4:
        return "closed"
    
    t = now.time()
    
    # 定义时间点
    pre_market_start = dtime(9, 0)
    morning_start = dtime(9, 30)
    noon = dtime(11, 30)
    afternoon_start = dtime(13, 0)
    afternoon_end = dtime(15, 0)
    after_market_end = dtime(15, 30)
    
    # 判断状态
    if pre_market_start <= t < morning_start:
        return "pre_market"
    elif morning_start <= t <= noon:
        return "morning_session"
    elif noon < t < afternoon_start:
        return "noon_break"
    elif afternoon_start <= t <= afternoon_end:
        return "afternoon_session"
    elif afternoon_end < t <= after_market_end:
        return "after_market"
    else:
        return "closed"

