#!/usr/bin/env python3
"""
CYQ Analyzer Skill - 筹码分布分析工具

这个包包含筹码分布分析所需的核心模块：
- cyq_analyzer: 筹码分布计算和图表生成
- stock_cache_v3: 股票数据缓存系统

使用示例：
    from scripts.cyq_analyzer import calculate_cyq, analyze_and_plot
    from scripts.stock_cache_v3 import get_stock_data, get_cache_stats
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__description__ = "股票筹码分布分析工具，支持获利盘、主力成本区、筹码集中度等指标"

# 可选：导出常用函数，方便外部导入
from .cyq_analyzer import calculate_cyq, analyze_and_plot, fetch_stock_data
from .stock_cache_v3 import get_stock_data, get_cache_stats, list_cached_stocks

__all__ = [
    # cyq_analyzer 导出
    'calculate_cyq',
    'analyze_and_plot',
    'fetch_stock_data',
    # stock_cache_v3 导出
    'get_stock_data',
    'get_cache_stats',
    'list_cached_stocks'
]