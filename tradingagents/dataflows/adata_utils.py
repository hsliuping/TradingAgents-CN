#!/usr/bin/env python3
"""
AData数据源集成模块
集成AData作为新的中国股票数据源
"""

import os
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class ADataProvider:
    """AData数据源提供者"""
    
    def __init__(self):
        """初始化AData提供商"""
        self.name = "adata"
        self.cache = {}
        
    def check_availability(self) -> bool:
        """检查AData是否可用"""
        try:
            import adata
            return True
        except ImportError:
            return False
    
    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """
        获取股票历史数据
        
        Args:
            symbol: 股票代码 (如: 000001, 600519)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: 股票数据
        """
        try:
            import adata
            
            # 设置默认日期范围
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            # 获取股票历史数据
            stock_code = str(symbol).zfill(6)
            
            # 根据股票代码判断是上证还是深证
            if stock_code.startswith(('600', '601', '603', '605', '688')):
                # 上证股票
                market = 'sh'
            elif stock_code.startswith(('000', '001', '002', '003', '300', '301', '400')):
                # 深证股票
                market = 'sz'
            else:
                # 默认使用上证
                market = 'sh'
            
            # 获取数据
            df = adata.stock.market.get_market_stock(
                stock_code=stock_code,
                market=market,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and not df.empty:
                # 标准化数据格式
                df = self._standardize_data(df)
                return df
            else:
                return None
                
        except Exception as e:
            print(f"AData获取股票数据失败: {e}")
            return None
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票基本信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 股票基本信息
        """
        try:
            import adata
            
            stock_code = str(symbol).zfill(6)
            
            # 获取股票基本信息
            info = adata.stock.info.get_stock_base_info(stock_code=stock_code)
            
            if info is not None and not info.empty:
                # 转换为字典格式
                info_dict = info.iloc[0].to_dict()
                
                # 标准化信息格式
                return {
                    'symbol': symbol,
                    'name': info_dict.get('name', f'股票{symbol}'),
                    'industry': info_dict.get('industry', '未知'),
                    'area': info_dict.get('area', '未知'),
                    'list_date': info_dict.get('list_date', '未知'),
                    'market': self._get_market_name(stock_code),
                    'source': 'adata'
                }
            else:
                return {
                    'symbol': symbol,
                    'name': f'股票{symbol}',
                    'industry': '未知',
                    'area': '未知',
                    'list_date': '未知',
                    'market': self._get_market_name(stock_code),
                    'source': 'adata'
                }
                
        except Exception as e:
            print(f"AData获取股票信息失败: {e}")
            return {
                'symbol': symbol,
                'name': f'股票{symbol}',
                'source': 'adata',
                'error': str(e)
            }
    
    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时股票数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            Dict: 实时股票数据
        """
        try:
            import adata
            
            stock_code = str(symbol).zfill(6)
            
            # 获取实时行情
            realtime = adata.stock.market.get_market_stock_min(
                stock_code=stock_code,
                period='1d'
            )
            
            if realtime is not None and not realtime.empty:
                latest = realtime.iloc[-1]
                return {
                    'symbol': symbol,
                    'price': latest.get('close', 0),
                    'change': latest.get('change', 0),
                    'change_percent': latest.get('pct_chg', 0),
                    'volume': latest.get('vol', 0),
                    'timestamp': latest.get('trade_time', datetime.now().strftime('%H:%M:%S'))
                }
            else:
                return None
                
        except Exception as e:
            print(f"AData获取实时数据失败: {e}")
            return None
    
    def _standardize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化数据格式"""
        # 重命名列名以统一格式
        rename_map = {
            'trade_date': 'date',
            'open_price': 'open',
            'close_price': 'close',
            'high_price': 'high',
            'low_price': 'low',
            'volume': 'vol',
            'turnover': 'amount',
            'pct_chg': 'change_pct'
        }
        
        # 应用重命名
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        
        # 确保必要的列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'vol']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0
        
        # 按日期排序
        if 'date' in df.columns:
            df = df.sort_values('date')
        
        return df
    
    def _get_market_name(self, stock_code: str) -> str:
        """根据股票代码获取市场名称"""
        if stock_code.startswith(('600', '601', '603', '605', '688')):
            return '上海证券交易所'
        elif stock_code.startswith(('000', '001', '002', '003', '300', '301')):
            return '深圳证券交易所'
        elif stock_code.startswith(('400', '430', '830', '831')):
            return '北京证券交易所'
        else:
            return '未知市场'


def get_adata_provider() -> ADataProvider:
    """获取AData提供者实例"""
    return ADataProvider()


def get_china_stock_data_adata(symbol: str, start_date: str = None, end_date: str = None) -> str:
    """
    获取中国股票数据的AData接口
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        str: 格式化的股票数据
    """
    provider = get_adata_provider()
    
    if not provider.check_availability():
        return "❌ AData数据源不可用: 未安装adata库"
    
    try:
        data = provider.get_stock_data(symbol, start_date, end_date)
        
        if data is not None and not data.empty:
            result = f"股票代码: {symbol}\n"
            result += f"数据源: AData\n"
            
            if start_date and end_date:
                result += f"数据期间: {start_date} 至 {end_date}\n"
            
            result += f"数据条数: {len(data)}条\n\n"
            result += "最新数据:\n"
            
            # 显示最新5条数据
            latest_data = data.tail(5)
            latest_str = latest_data.to_string(
                index=False,
                formatters={
                    'date': lambda x: str(x)[:10],
                    'open': lambda x: f"{x:.2f}",
                    'high': lambda x: f"{x:.2f}",
                    'low': lambda x: f"{x:.2f}",
                    'close': lambda x: f"{x:.2f}",
                    'vol': lambda x: f"{int(x):,}"
                }
            )
            result += latest_str
            
            return result
        else:
            return f"❌ 未能获取{symbol}的股票数据"
            
    except Exception as e:
        return f"❌ AData数据获取失败: {e}"


def get_china_stock_info_adata(symbol: str) -> str:
    """
    获取中国股票信息的AData接口
    
    Args:
        symbol: 股票代码
        
    Returns:
        str: 格式化的股票信息
    """
    provider = get_adata_provider()
    
    if not provider.check_availability():
        return "❌ AData数据源不可用: 未安装adata库"
    
    try:
        info = provider.get_stock_info(symbol)
        
        result = f"股票代码: {info['symbol']}\n"
        result += f"股票名称: {info['name']}\n"
        result += f"所属行业: {info['industry']}\n"
        result += f"所属地区: {info['area']}\n"
        result += f"上市市场: {info['market']}\n"
        result += f"上市日期: {info['list_date']}\n"
        result += f"数据源: {info['source']}\n"
        
        return result
        
    except Exception as e:
        return f"❌ AData信息获取失败: {e}"