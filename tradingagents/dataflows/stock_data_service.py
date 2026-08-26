#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的股票数据获取服务
实现MongoDB -> Tushare数据接口的完整降级机制
"""

import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')

try:
    from tradingagents.config.database_manager import get_database_manager
    DATABASE_MANAGER_AVAILABLE = True
except ImportError:
    DATABASE_MANAGER_AVAILABLE = False

try:
    import sys
    import os
    # 添加utils目录到路径
    utils_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'utils')
    if utils_path not in sys.path:
        sys.path.append(utils_path)
    from enhanced_stock_list_fetcher import enhanced_fetch_stock_list
    ENHANCED_FETCHER_AVAILABLE = True
except ImportError:
    ENHANCED_FETCHER_AVAILABLE = False

logger = logging.getLogger(__name__)

class StockDataService:
    """
    统一的股票数据获取服务
    实现完整的降级机制：MongoDB -> Tushare数据接口 -> 缓存 -> 错误处理
    """
    
    def __init__(self):
        self.db_manager = None
        self._init_services()
    
    def _init_services(self):
        """初始化服务"""
        # 尝试初始化数据库管理器
        if DATABASE_MANAGER_AVAILABLE:
            try:
                self.db_manager = get_database_manager()
                if self.db_manager.is_mongodb_available():
                    logger.info(f"✅ MongoDB连接成功")
                else:
                    logger.error(f"⚠️ MongoDB连接失败，将使用其他数据源")
            except Exception as e:
                logger.error(f"⚠️ 数据库管理器初始化失败: {e}")
                self.db_manager = None
    
    def get_stock_basic_info(self, stock_code: str = None) -> Optional[Dict[str, Any]]:
        """
        获取股票基础信息（单个股票或全部股票）
        
        Args:
            stock_code: 股票代码，如果为None则返回所有股票
        
        Returns:
            Dict: 股票基础信息
        """
        logger.info(f"📊 获取股票基础信息: {stock_code or '全部股票'}")
        
        # 1. 优先从MongoDB获取
        if self.db_manager and self.db_manager.is_mongodb_available():
            try:
                result = self._get_from_mongodb(stock_code)
                if result:
                    logger.info(f"✅ 从MongoDB获取成功: {len(result) if isinstance(result, list) else 1}条记录")
                    return result
            except Exception as e:
                logger.error(f"⚠️ MongoDB查询失败: {e}")
        
        # 2. 降级到增强获取器
        logger.info(f"🔄 MongoDB不可用，降级到增强获取器")
        if ENHANCED_FETCHER_AVAILABLE:
            try:
                result = self._get_from_enhanced_fetcher(stock_code)
                if result:
                    logger.info(f"✅ 从增强获取器获取成功: {len(result) if isinstance(result, list) else 1}条记录")
                    # 尝试缓存到MongoDB（如果可用）
                    self._cache_to_mongodb(result)
                    return result
            except Exception as e:
                logger.error(f"⚠️ 增强获取器查询失败: {e}")
        
        # 3. 最后的降级方案
        logger.error(f"❌ 所有数据源都不可用")
        return self._get_fallback_data(stock_code)
    
    def _get_from_mongodb(self, stock_code: str = None) -> Optional[Dict[str, Any]]:
        """从MongoDB获取数据"""
        try:
            mongodb_client = self.db_manager.get_mongodb_client()
            if not mongodb_client:
                return None

            db = mongodb_client[self.db_manager.mongodb_config["database"]]
            collection = db['stock_basic_info']

            if stock_code:
                # 获取单个股票
                result = collection.find_one({'code': stock_code})
                return result if result else None
            else:
                # 获取所有股票
                cursor = collection.find({})
                results = list(cursor)
                return results if results else None

        except Exception as e:
            logger.error(f"MongoDB查询失败: {e}")
            return None
    
    def _get_from_enhanced_fetcher(self, stock_code: str = None) -> Optional[Dict[str, Any]]:
        """从增强获取器获取数据"""
        try:
            if stock_code:
                # 获取单个股票信息 - 使用增强获取器获取所有股票然后筛选
                stock_df = enhanced_fetch_stock_list(
                    type_='stock',
                    enable_server_failover=True,
                    max_retries=3
                )
                
                if stock_df is not None and not stock_df.empty:
                    # 查找指定股票代码
                    stock_row = stock_df[stock_df['code'] == stock_code]
                    if not stock_row.empty:
                        row = stock_row.iloc[0]
                        return {
                            'code': row.get('code', stock_code),
                            'name': row.get('name', ''),
                            'market': row.get('market', self._get_market_name(stock_code)),
                            'category': row.get('category', self._get_stock_category(stock_code)),
                            'source': 'enhanced_fetcher',
                            'updated_at': datetime.now().isoformat()
                        }
                    else:
                        # 如果没找到，返回基本信息
                        return {
                            'code': stock_code,
                            'name': '',
                            'market': self._get_market_name(stock_code),
                            'category': self._get_stock_category(stock_code),
                            'source': 'enhanced_fetcher',
                            'updated_at': datetime.now().isoformat()
                        }
            else:
                # 获取所有股票列表
                stock_df = enhanced_fetch_stock_list(
                    type_='stock',
                    enable_server_failover=True,
                    max_retries=3
                )
                
                if stock_df is not None and not stock_df.empty:
                    # 转换为字典列表
                    results = []
                    for _, row in stock_df.iterrows():
                        results.append({
                            'code': row.get('code', ''),
                            'name': row.get('name', ''),
                            'market': row.get('market', ''),
                            'category': row.get('category', ''),
                            'source': 'enhanced_fetcher',
                            'updated_at': datetime.now().isoformat()
                        })
                    return results
                    
        except Exception as e:
            logger.error(f"增强获取器查询失败: {e}")
            return None
    
    def _cache_to_mongodb(self, data: Any) -> bool:
        """将数据缓存到MongoDB"""
        if not self.db_manager or not self.db_manager.is_mongodb_available():
            return False

        try:
            collection = self.db_manager.get_mongodb_db()['stock_basic_info']
            
            if isinstance(data, list):
                # 批量插入
                for item in data:
                    collection.update_one(
                        {'code': item['code']},
                        {'$set': item},
                        upsert=True
                    )
                logger.info(f"💾 已缓存{len(data)}条记录到MongoDB")
            elif isinstance(data, dict):
                # 单条插入
                collection.update_one(
                    {'code': data['code']},
                    {'$set': data},
                    upsert=True
                )
                logger.info(f"💾 已缓存股票{data['code']}到MongoDB")
            
            return True
            
        except Exception as e:
            logger.error(f"缓存到MongoDB失败: {e}")
            return False
    
    def _get_fallback_data(self, stock_code: str = None) -> Dict[str, Any]:
        """最后的降级数据"""
        if stock_code:
            return {
                'code': stock_code,
                'name': f'股票{stock_code}',
                'market': self._get_market_name(stock_code),
                'category': '未知',
                'source': 'fallback',
                'updated_at': datetime.now().isoformat(),
                'error': '所有数据源都不可用'
            }
        else:
            return {
                'error': '无法获取股票列表，请检查网络连接和数据库配置',
                'suggestion': '请确保MongoDB已配置或网络连接正常以访问Tushare数据接口'
            }
    
    def _get_market_name(self, stock_code: str) -> str:
        """根据股票代码判断市场"""
        if stock_code.startswith(('60', '68', '90')):
            return '上海'
        elif stock_code.startswith(('00', '30', '20')):
            return '深圳'
        else:
            return '未知'
    
    def _get_stock_category(self, stock_code: str) -> str:
        """根据股票代码判断类别"""
        if stock_code.startswith('60'):
            return '沪市主板'
        elif stock_code.startswith('68'):
            return '科创板'
        elif stock_code.startswith('00'):
            return '深市主板'
        elif stock_code.startswith('30'):
            return '创业板'
        elif stock_code.startswith('20'):
            return '深市B股'
        else:
            return '其他'
    
    def get_stock_data_with_fallback(self, stock_code: str, start_date: str, end_date: str) -> str:
        """
        获取股票数据（带降级机制）
        这是对现有get_china_stock_data函数的增强
        """
        logger.info(f"📊 获取股票数据: {stock_code} ({start_date} 到 {end_date})")
        
        # 首先确保股票基础信息可用
        stock_info = self.get_stock_basic_info(stock_code)
        if stock_info and 'error' in stock_info:
            return f"❌ 无法获取股票{stock_code}的基础信息: {stock_info.get('error', '未知错误')}"
        
        # 调用统一的中国股票数据接口
        try:
            from .interface import get_china_stock_data_unified

            return get_china_stock_data_unified(stock_code, start_date, end_date)
        except Exception as e:
            return f"❌ 获取股票数据失败: {str(e)}\n\n💡 建议：\n1. 检查网络连接\n2. 确认股票代码格式正确\n3. 检查MongoDB配置"

# 全局服务实例
_stock_data_service = None

def get_stock_data_service() -> StockDataService:
    """获取股票数据服务实例（单例模式）"""
    global _stock_data_service
    if _stock_data_service is None:
        _stock_data_service = StockDataService()
    return _stock_data_service