"""
旧代码适配器

将旧的 Toolkit 类中的工具适配到新的 ToolRegistry
"""

import logging
from typing import Dict, Any, List, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class LegacyToolkitAdapter:
    """
    将旧 Toolkit 适配到新 ToolRegistry
    
    用途：
    1. 在迁移过程中保持向后兼容
    2. 自动将 Toolkit 中的工具注册到新的 Registry
    """
    
    # 工具映射表：旧方法名 -> 新工具配置
    TOOL_MAPPING = {
        "get_reddit_news": {
            "id": "get_reddit_news",
            "name": "Reddit全球新闻",
            "category": "news",
            "description": "获取Reddit全球新闻",
        },
        "get_finnhub_news": {
            "id": "get_finnhub_news",
            "name": "Finnhub新闻",
            "category": "news",
            "description": "获取Finnhub股票新闻",
        },
        "get_reddit_stock_info": {
            "id": "get_reddit_stock_sentiment",
            "name": "Reddit股票情绪",
            "category": "social",
            "description": "获取Reddit股票讨论情绪",
        },
        "get_chinese_social_sentiment": {
            "id": "get_chinese_social_sentiment",
            "name": "中国社交媒体情绪",
            "category": "social",
            "description": "获取中国社交媒体股票情绪",
        },
        "get_stock_market_data_unified": {
            "id": "get_stock_market_data_unified",
            "name": "统一股票市场数据",
            "category": "market",
            "description": "获取统一格式的股票市场数据",
        },
        "get_stock_fundamentals_unified": {
            "id": "get_stock_fundamentals_unified",
            "name": "统一基本面数据",
            "category": "fundamentals",
            "description": "获取统一格式的股票基本面数据",
        },
        "get_YFin_data_online": {
            "id": "get_yfinance_data",
            "name": "Yahoo Finance数据",
            "category": "market",
            "description": "从Yahoo Finance获取股票数据",
        },
        "get_SEC_filings_analysis": {
            "id": "get_sec_filings",
            "name": "SEC文件分析",
            "category": "fundamentals",
            "description": "获取并分析SEC财务文件",
        },
        "get_simfin_balance_sheet": {
            "id": "get_balance_sheet",
            "name": "资产负债表",
            "category": "fundamentals",
            "description": "获取资产负债表数据",
        },
        "get_simfin_cashflow": {
            "id": "get_cashflow",
            "name": "现金流量表",
            "category": "fundamentals",
            "description": "获取现金流量表数据",
        },
        "get_simfin_income_stmt": {
            "id": "get_income_statement",
            "name": "利润表",
            "category": "fundamentals",
            "description": "获取利润表数据",
        },
    }
    
    @classmethod
    def register_all(cls, tool_registry=None) -> int:
        """
        将 Toolkit 中的工具注册到新 Registry
        
        Args:
            tool_registry: ToolRegistry 实例，如果为 None 则使用默认实例
            
        Returns:
            注册成功的工具数量
        """
        if tool_registry is None:
            from core.tools.registry import ToolRegistry
            tool_registry = ToolRegistry()
        
        registered = 0
        
        try:
            from tradingagents.agents.utils.agent_utils import Toolkit
            toolkit = Toolkit()
            
            for method_name, config in cls.TOOL_MAPPING.items():
                try:
                    # 获取原方法
                    if not hasattr(toolkit, method_name):
                        logger.warning(f"Toolkit 中找不到方法: {method_name}")
                        continue
                    
                    method = getattr(toolkit, method_name)
                    
                    # 注册到新 Registry
                    tool_registry.register_function(
                        tool_id=config["id"],
                        func=method,
                        name=config["name"],
                        category=config["category"],
                        description=config["description"],
                        is_legacy=True,
                    )
                    
                    registered += 1
                    logger.debug(f"注册旧工具: {method_name} -> {config['id']}")
                    
                except Exception as e:
                    logger.error(f"注册工具 {method_name} 失败: {e}")
            
            logger.info(f"✅ 从 Toolkit 注册了 {registered} 个工具")
            
        except ImportError as e:
            logger.warning(f"无法导入 Toolkit: {e}")
        except Exception as e:
            logger.error(f"注册旧工具失败: {e}")
        
        return registered
    
    @classmethod
    def get_tool_mapping(cls) -> Dict[str, Dict[str, Any]]:
        """获取工具映射表"""
        return cls.TOOL_MAPPING.copy()
    
    @classmethod
    def get_new_tool_id(cls, old_method_name: str) -> str:
        """根据旧方法名获取新工具ID"""
        if old_method_name in cls.TOOL_MAPPING:
            return cls.TOOL_MAPPING[old_method_name]["id"]
        return old_method_name

