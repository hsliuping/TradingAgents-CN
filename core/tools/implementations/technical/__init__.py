"""
技术指标计算库

这是一个独立的技术指标计算库，提供纯函数式的指标计算功能。
不注册为LangChain工具，供其他模块直接调用。

支持的指标：
- MA (移动平均线)
- EMA (指数移动平均线)
- MACD (平滑异同移动平均线)
- RSI (相对强弱指标，支持3种计算风格)
- BOLL (布林带)
- ATR (平均真实波幅)
- KDJ (随机指标)

使用示例：
    from core.tools.implementations.technical import ma, rsi, macd

    # 计算MA
    ma_values = ma(df['close'], n=20)

    # 计算RSI（国际标准）
    rsi_values = rsi(df['close'], n=14, method='ema')

    # 计算RSI（中国风格）
    rsi_values = rsi(df['close'], n=14, method='china')

    # 计算MACD
    macd_df = macd(df['close'], fast=12, slow=26, signal=9)
"""

from .indicators import (
    # 基础指标
    ma,
    ema,
    macd,
    rsi,
    boll,
    atr,
    kdj,

    # 辅助函数
    compute_indicator,
    compute_many,
    last_values,
    add_all_indicators,

    # 数据类
    IndicatorSpec,
    SUPPORTED,
)

__all__ = [
    # 基础指标
    "ma",
    "ema",
    "macd",
    "rsi",
    "boll",
    "atr",
    "kdj",

    # 辅助函数
    "compute_indicator",
    "compute_many",
    "last_values",
    "add_all_indicators",

    # 数据类
    "IndicatorSpec",
    "SUPPORTED",
]

