"""
港股数据获取工具
提供港股数据的获取、处理和缓存功能
"""

import pandas as pd
import yfinance as yf
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import os

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')



class HKStockProvider:
    """港股数据提供器"""

    def __init__(self):
        """初始化港股数据提供器"""
        self.last_request_time = 0
        self.min_request_interval = 2.0  # 增加请求间隔到2秒
        self.timeout = 60  # 请求超时时间（增加到60秒）
        self.max_retries = 3  # 增加重试次数
        self.rate_limit_wait = 60  # 遇到限制时等待时间

        logger.info(f"🇭🇰 港股数据提供器初始化完成")
    
    def _wait_for_rate_limit(self):
        """等待速率限制"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """
        获取港股历史数据
        
        Args:
            symbol: 港股代码 (如: 0700.HK)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            DataFrame: 股票历史数据
        """
        try:
            # 标准化港股代码
            symbol = self._normalize_hk_symbol(symbol)
            
            # 设置默认日期
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            logger.info(f"🇭🇰 获取港股数据: {symbol} ({start_date} 到 {end_date})")
            
            # 多次重试获取数据
            for attempt in range(self.max_retries):
                try:
                    self._wait_for_rate_limit()
                    
                    # 使用yfinance获取数据
                    ticker = yf.Ticker(symbol)
                    data = ticker.history(
                        start=start_date,
                        end=end_date,
                        timeout=self.timeout
                    )
                    
                    if not data.empty:
                        # 数据预处理
                        data = data.reset_index()
                        data['Symbol'] = symbol
                        
                        logger.info(f"✅ 港股数据获取成功: {symbol}, {len(data)}条记录")
                        return data
                    else:
                        logger.warning(f"⚠️ 港股数据为空: {symbol} (尝试 {attempt + 1}/{self.max_retries})")
                        
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"❌ 港股数据获取失败 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")

                    # 检查是否是频率限制错误
                    if "Rate limited" in error_msg or "Too Many Requests" in error_msg:
                        if attempt < self.max_retries - 1:
                            logger.info(f"⏳ 检测到频率限制，等待{self.rate_limit_wait}秒...")
                            time.sleep(self.rate_limit_wait)
                        else:
                            logger.error(f"❌ 频率限制，跳过重试")
                            break
                    else:
                        if attempt < self.max_retries - 1:
                            time.sleep(2 ** attempt)  # 指数退避
                    
            logger.error(f"❌ 港股数据获取最终失败: {symbol}")
            return None

        except Exception as e:
            logger.error(f"❌ 港股数据获取异常: {e}")
            return None
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取港股基本信息
        
        Args:
            symbol: 港股代码
            
        Returns:
            Dict: 股票基本信息
        """
        try:
            symbol = self._normalize_hk_symbol(symbol)
            
            logger.info(f"🇭🇰 获取港股信息: {symbol}")
            
            self._wait_for_rate_limit()
            
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if info and 'symbol' in info:
                return {
                    'symbol': symbol,
                    'name': info.get('longName', info.get('shortName', f'港股{symbol}')),
                    'currency': info.get('currency', 'HKD'),
                    'exchange': info.get('exchange', 'HKG'),
                    'market_cap': info.get('marketCap'),
                    'sector': info.get('sector'),
                    'industry': info.get('industry'),
                    'source': 'yfinance_hk'
                }
            else:
                return {
                    'symbol': symbol,
                    'name': f'港股{symbol}',
                    'currency': 'HKD',
                    'exchange': 'HKG',
                    'source': 'yfinance_hk'
                }
                
        except Exception as e:
            logger.error(f"❌ 获取港股信息失败: {e}")
            return {
                'symbol': symbol,
                'name': f'港股{symbol}',
                'currency': 'HKD',
                'exchange': 'HKG',
                'source': 'unknown',
                'error': str(e)
            }
    
    def get_real_time_price(self, symbol: str) -> Optional[Dict]:
        """
        获取港股实时价格
        
        Args:
            symbol: 港股代码
            
        Returns:
            Dict: 实时价格信息
        """
        try:
            symbol = self._normalize_hk_symbol(symbol)
            
            self._wait_for_rate_limit()
            
            ticker = yf.Ticker(symbol)
            
            # 获取最新的历史数据（1天）
            data = ticker.history(period="1d", timeout=self.timeout)
            
            if not data.empty:
                latest = data.iloc[-1]
                return {
                    'symbol': symbol,
                    'price': latest['Close'],
                    'open': latest['Open'],
                    'high': latest['High'],
                    'low': latest['Low'],
                    'volume': latest['Volume'],
                    'timestamp': data.index[-1].strftime('%Y-%m-%d %H:%M:%S'),
                    'currency': 'HKD'
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取港股实时价格失败: {e}")
            return None
    
    def _normalize_hk_symbol(self, symbol: str) -> str:
        """
        标准化港股代码格式
        
        Args:
            symbol: 原始港股代码
            
        Returns:
            str: 标准化后的港股代码
        """
        if not symbol:
            return symbol
            
        symbol = str(symbol).strip().upper()
        
        # 如果是纯4-5位数字，添加.HK后缀
        if symbol.isdigit() and 4 <= len(symbol) <= 5:
            return f"{symbol}.HK"

        # 如果已经是正确格式，直接返回
        if symbol.endswith('.HK') and 7 <= len(symbol) <= 8:
            return symbol

        # 处理其他可能的格式
        if '.' not in symbol and symbol.isdigit():
            # 保持原有位数，不强制填充到4位
            return f"{symbol}.HK"
            
        return symbol

    def format_stock_data(self, symbol: str, data: pd.DataFrame, start_date: str, end_date: str) -> str:
        """
        格式化港股数据为文本格式
        
        Args:
            symbol: 股票代码
            data: 股票数据DataFrame
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            str: 格式化的股票数据文本
        """
        if data is None or data.empty:
            return f"❌ 无法获取港股 {symbol} 的数据"
        
        try:
            # 获取股票基本信息
            stock_info = self.get_stock_info(symbol)
            stock_name = stock_info.get('name', f'港股{symbol}')
            
            # 计算统计信息
            latest_price = data['Close'].iloc[-1]
            price_change = data['Close'].iloc[-1] - data['Close'].iloc[0]
            price_change_pct = (price_change / data['Close'].iloc[0]) * 100
            
            avg_volume = data['Volume'].mean()
            max_price = data['High'].max()
            min_price = data['Low'].min()
            
            # 格式化输出
            formatted_text = f"""
🇭🇰 港股数据报告
================

股票信息:
- 代码: {symbol}
- 名称: {stock_name}
- 货币: 港币 (HKD)
- 交易所: 香港交易所 (HKG)

价格信息:
- 最新价格: HK${latest_price:.2f}
- 期间涨跌: HK${price_change:+.2f} ({price_change_pct:+.2f}%)
- 期间最高: HK${max_price:.2f}
- 期间最低: HK${min_price:.2f}

交易信息:
- 数据期间: {start_date} 至 {end_date}
- 交易天数: {len(data)}天
- 平均成交量: {avg_volume:,.0f}股

最近5个交易日:
"""
            
            # 添加最近5天的数据
            recent_data = data.tail(5)
            for _, row in recent_data.iterrows():
                date = row['Date'].strftime('%Y-%m-%d') if 'Date' in row else row.name.strftime('%Y-%m-%d')
                formatted_text += f"- {date}: 开盘HK${row['Open']:.2f}, 收盘HK${row['Close']:.2f}, 成交量{row['Volume']:,.0f}\n"

            formatted_text += f"\n数据来源: Yahoo Finance (港股)\n"
            
            return formatted_text
            
        except Exception as e:
            logger.error(f"❌ 格式化港股数据失败: {e}")
            return f"❌ 港股数据格式化失败: {symbol}"


# 全局提供器实例
_hk_provider = None

def get_hk_stock_provider() -> HKStockProvider:
    """获取全局港股提供器实例"""
    global _hk_provider
    if _hk_provider is None:
        _hk_provider = HKStockProvider()
    return _hk_provider


def get_hk_stock_data(symbol: str, start_date: str = None, end_date: str = None) -> str:
    """
    获取港股数据的便捷函数
    
    Args:
        symbol: 港股代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        str: 格式化的港股数据
    """
    provider = get_hk_stock_provider()
    data = provider.get_stock_data(symbol, start_date, end_date)
    return provider.format_stock_data(symbol, data, start_date, end_date)


def get_hk_stock_info(symbol: str) -> Dict:
    """
    获取港股信息的便捷函数
    
    Args:
        symbol: 港股代码
        
    Returns:
        Dict: 港股信息
    """
    provider = get_hk_stock_provider()
    return provider.get_stock_info(symbol)
