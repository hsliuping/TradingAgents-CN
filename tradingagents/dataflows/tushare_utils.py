#!/usr/bin/env python3
"""
Tushare数据源工具类
提供A股市场数据获取功能，包括实时行情、历史数据、财务数据等
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union
import warnings
import time
warnings.filterwarnings('ignore')

# 导入缓存管理器
try:
    from .cache_manager import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    print("⚠️ 缓存管理器不可用")

# 导入Tushare
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    print("❌ Tushare库未安装，请运行: pip install tushare")


class TushareProvider:
    """Tushare数据提供器"""
    
    def __init__(self, token: str = None, enable_cache: bool = True):
        """
        初始化Tushare提供器
        
        Args:
            token: Tushare API token
            enable_cache: 是否启用缓存
        """
        self.connected = False
        self.enable_cache = enable_cache and CACHE_AVAILABLE
        self.api = None
        
        # 初始化缓存管理器
        self.cache_manager = None
        if self.enable_cache:
            try:
                from .cache_manager import get_cache
                self.cache_manager = get_cache()
            except Exception as e:
                print(f"⚠️ 缓存管理器初始化失败: {e}")
                self.enable_cache = False
        
        # 获取API token
        if not token:
            token = os.getenv('TUSHARE_TOKEN')
        
        if not token:
            print("⚠️ 未找到Tushare API token，请设置TUSHARE_TOKEN环境变量")
            return
        
        # 初始化Tushare API
        if TUSHARE_AVAILABLE:
            try:
                ts.set_token(token)
                self.api = ts.pro_api()
                self.connected = True
                print("✅ Tushare API连接成功")
            except Exception as e:
                print(f"❌ Tushare API连接失败: {e}")
        else:
            print("❌ Tushare库不可用")
    
    def get_stock_list(self) -> pd.DataFrame:
        """
        获取A股股票列表
        
        Returns:
            DataFrame: 股票列表数据
        """
        if not self.connected:
            print("❌ Tushare未连接")
            return pd.DataFrame()
        
        try:
            # 尝试从缓存获取
            if self.enable_cache:
                cache_key = self.cache_manager.find_cached_stock_data(
                    symbol="tushare_stock_list",
                    max_age_hours=24  # 股票列表缓存24小时
                )
                
                if cache_key:
                    cached_data = self.cache_manager.load_stock_data(cache_key)
                    if cached_data is not None:
                        # 检查是否为DataFrame且不为空
                        if hasattr(cached_data, 'empty') and not cached_data.empty:
                            print(f"📦 从缓存获取股票列表: {len(cached_data)}条")
                            return cached_data
                        elif isinstance(cached_data, str) and cached_data.strip():
                            print(f"📦 从缓存获取股票列表: 字符串格式")
                            return cached_data
            
            print("🔄 从Tushare获取A股股票列表...")
            
            # 获取股票基本信息
            stock_list = self.api.stock_basic(
                exchange='',
                list_status='L',  # 上市状态
                fields='ts_code,symbol,name,area,industry,market,list_date'
            )
            
            if stock_list is not None and not stock_list.empty:
                print(f"✅ 获取股票列表成功: {len(stock_list)}条")
                
                # 缓存数据
                if self.enable_cache and self.cache_manager:
                    try:
                        cache_key = self.cache_manager.save_stock_data(
                            symbol="tushare_stock_list",
                            data=stock_list,
                            data_source="tushare"
                        )
                        print(f"💾 A股股票列表已缓存: tushare_stock_list (tushare) -> {cache_key}")
                    except Exception as e:
                        print(f"⚠️ 缓存保存失败: {e}")
                
                return stock_list
            else:
                print("⚠️ Tushare返回空数据")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ 获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def get_stock_daily(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            symbol: 股票代码（如：000001.SZ）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            
        Returns:
            DataFrame: 日线数据
        """
        if not self.connected:
            print("❌ Tushare未连接")
            return pd.DataFrame()
        
        try:
            # 标准化股票代码
            ts_code = self._normalize_symbol(symbol)
            
            # 设置默认日期
            if end_date is None:
                end_date = datetime.now().strftime('%Y%m%d')
            else:
                end_date = end_date.replace('-', '')
            
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            else:
                start_date = start_date.replace('-', '')
            
            print(f"🔄 从Tushare获取{ts_code}数据 ({start_date} 到 {end_date})...")
            
            # 获取日线数据
            data = self.api.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if data is not None and not data.empty:
                # 数据预处理
                data = data.sort_values('trade_date')
                data['trade_date'] = pd.to_datetime(data['trade_date'])
                
                print(f"✅ 获取{ts_code}数据成功: {len(data)}条")
                
                # 缓存数据
                if self.enable_cache and self.cache_manager:
                    try:
                        cache_key = self.cache_manager.save_stock_data(
                            symbol=symbol,
                            data=data,
                            data_source="tushare"
                        )
                        print(f"💾 A股历史数据已缓存: {symbol} (tushare) -> {cache_key}")
                    except Exception as e:
                        print(f"⚠️ 缓存保存失败: {e}")
                
                return data
            else:
                print(f"⚠️ Tushare返回空数据: {ts_code}")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ 获取{symbol}数据失败: {e}")
            return pd.DataFrame()
    
    def get_stock_info(self, symbol: str) -> Dict:
        """
        获取股票基本信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 股票基本信息
        """
        if not self.connected:
            return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'unknown'}
        
        try:
            ts_code = self._normalize_symbol(symbol)
            
            # 获取股票基本信息
            basic_info = self.api.stock_basic(
                ts_code=ts_code,
                fields='ts_code,symbol,name,area,industry,market,list_date'
            )
            
            if basic_info is not None and not basic_info.empty:
                info = basic_info.iloc[0]
                return {
                    'symbol': symbol,
                    'ts_code': info['ts_code'],
                    'name': info['name'],
                    'area': info.get('area', ''),
                    'industry': info.get('industry', ''),
                    'market': info.get('market', ''),
                    'list_date': info.get('list_date', ''),
                    'source': 'tushare'
                }
            else:
                return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'unknown'}
                
        except Exception as e:
            print(f"❌ 获取{symbol}股票信息失败: {e}")
            return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'unknown'}
    
    def get_financial_data(self, symbol: str, period: str = "20231231") -> Dict:
        """
        获取财务数据
        
        Args:
            symbol: 股票代码
            period: 报告期（YYYYMMDD）
            
        Returns:
            Dict: 财务数据
        """
        if not self.connected:
            return {}
        
        try:
            ts_code = self._normalize_symbol(symbol)
            
            financials = {}
            
            # 获取资产负债表
            try:
                balance_sheet = self.api.balancesheet(
                    ts_code=ts_code,
                    period=period,
                    fields='ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,total_assets,total_liab,total_hldr_eqy_exc_min_int'
                )
                financials['balance_sheet'] = balance_sheet.to_dict('records') if balance_sheet is not None and not balance_sheet.empty else []
            except Exception as e:
                print(f"⚠️ 获取资产负债表失败: {e}")
                financials['balance_sheet'] = []
            
            # 获取利润表
            try:
                income_statement = self.api.income(
                    ts_code=ts_code,
                    period=period,
                    fields='ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,total_revenue,total_cogs,operate_profit,total_profit,n_income'
                )
                financials['income_statement'] = income_statement.to_dict('records') if income_statement is not None and not income_statement.empty else []
            except Exception as e:
                print(f"⚠️ 获取利润表失败: {e}")
                financials['income_statement'] = []
            
            # 获取现金流量表
            try:
                cash_flow = self.api.cashflow(
                    ts_code=ts_code,
                    period=period,
                    fields='ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,net_profit,finan_exp,c_fr_sale_sg,c_paid_goods_s'
                )
                financials['cash_flow'] = cash_flow.to_dict('records') if cash_flow is not None and not cash_flow.empty else []
            except Exception as e:
                print(f"⚠️ 获取现金流量表失败: {e}")
                financials['cash_flow'] = []
            
            return financials
            
        except Exception as e:
            print(f"❌ 获取{symbol}财务数据失败: {e}")
            return {}
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码为Tushare格式
        
        Args:
            symbol: 原始股票代码
            
        Returns:
            str: Tushare格式的股票代码
        """
        # 移除可能的前缀
        symbol = symbol.replace('sh.', '').replace('sz.', '')
        
        # 如果已经是Tushare格式，直接返回
        if '.' in symbol:
            return symbol
        
        # 根据代码判断交易所
        if symbol.startswith('6'):
            return f"{symbol}.SH"  # 上海证券交易所
        elif symbol.startswith(('0', '3')):
            return f"{symbol}.SZ"  # 深圳证券交易所
        elif symbol.startswith('8'):
            return f"{symbol}.BJ"  # 北京证券交易所
        else:
            # 默认深圳
            return f"{symbol}.SZ"
    
    def search_stocks(self, keyword: str) -> pd.DataFrame:
        """
        搜索股票
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            DataFrame: 搜索结果
        """
        try:
            stock_list = self.get_stock_list()
            
            if stock_list.empty:
                return pd.DataFrame()
            
            # 按名称和代码搜索
            mask = (
                stock_list['name'].str.contains(keyword, na=False) |
                stock_list['symbol'].str.contains(keyword, na=False) |
                stock_list['ts_code'].str.contains(keyword, na=False)
            )
            
            results = stock_list[mask]
            print(f"🔍 搜索'{keyword}'找到{len(results)}只股票")
            
            return results
            
        except Exception as e:
            print(f"❌ 搜索股票失败: {e}")
            return pd.DataFrame()


# 全局提供器实例
_tushare_provider = None

def get_tushare_provider() -> TushareProvider:
    """获取全局Tushare提供器实例"""
    global _tushare_provider
    if _tushare_provider is None:
        _tushare_provider = TushareProvider()
    return _tushare_provider


def get_china_stock_data_tushare(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    获取中国股票数据的便捷函数（Tushare数据源）
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        DataFrame: 股票数据
    """
    provider = get_tushare_provider()
    return provider.get_stock_daily(symbol, start_date, end_date)


def get_china_stock_info_tushare(symbol: str) -> Dict:
    """
    获取中国股票信息的便捷函数（Tushare数据源）
    
    Args:
        symbol: 股票代码
        
    Returns:
        Dict: 股票信息
    """
    provider = get_tushare_provider()
    return provider.get_stock_info(symbol)
