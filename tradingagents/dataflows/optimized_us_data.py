#!/usr/bin/env python3
"""
优化的美股数据获取工具
集成缓存策略，减少API调用，提高响应速度
"""

import os
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import yfinance as yf
import pandas as pd
from .cache_manager import get_cache
from .config import get_config

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')


class OptimizedUSDataProvider:
    """优化的美股数据提供器 - 集成缓存和API限制处理"""
    
    def __init__(self):
        self.cache = get_cache()
        self.config = get_config()
        self.last_api_call = 0
        self.min_api_interval = 1.0  # 最小API调用间隔（秒）
        
        logger.info(f"📊 优化美股数据提供器初始化完成")
    
    def _wait_for_rate_limit(self):
        """等待API限制"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        
        if time_since_last_call < self.min_api_interval:
            wait_time = self.min_api_interval - time_since_last_call
            logger.info(f"⏳ API限制等待 {wait_time:.1f}s...")
            time.sleep(wait_time)
        
        self.last_api_call = time.time()
    
    def get_stock_data(self, symbol: str, start_date: str, end_date: str, 
                      force_refresh: bool = False) -> str:
        """
        获取美股数据 - 优先使用缓存
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            force_refresh: 是否强制刷新缓存
        
        Returns:
            格式化的股票数据字符串
        """
        logger.info(f"📈 获取美股数据: {symbol} ({start_date} 到 {end_date})")
        
        # 检查缓存（除非强制刷新）
        if not force_refresh:
            # 优先查找FINNHUB缓存
            cache_key = self.cache.find_cached_stock_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                data_source="finnhub"
            )

            # 如果没有FINNHUB缓存，查找Yahoo Finance缓存
            if not cache_key:
                cache_key = self.cache.find_cached_stock_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    data_source="yfinance"
                )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存加载美股数据: {symbol}")
                    return cached_data
        
        # 缓存未命中，从API获取 - 优先使用FINNHUB
        formatted_data = None
        data_source = None

        # 尝试FINNHUB API（优先）
        try:
            logger.info(f"🌐 从FINNHUB API获取数据: {symbol}")
            self._wait_for_rate_limit()

            formatted_data = self._get_data_from_finnhub(symbol, start_date, end_date)
            if formatted_data and "❌" not in formatted_data:
                data_source = "finnhub"
                logger.info(f"✅ FINNHUB数据获取成功: {symbol}")
            else:
                logger.error(f"⚠️ FINNHUB数据获取失败，尝试备用方案")
                formatted_data = None

        except Exception as e:
            logger.error(f"❌ FINNHUB API调用失败: {e}")
            formatted_data = None

        # 备用方案：根据股票类型选择合适的数据源
        if not formatted_data:
            try:
                # 检测股票类型
                from tradingagents.utils.stock_utils import StockUtils
                market_info = StockUtils.get_market_info(symbol)

                if market_info['is_hk']:
                    # 港股优先使用AKShare数据源
                    logger.info(f"🇭🇰 尝试使用AKShare获取港股数据: {symbol}")
                    try:
                        from tradingagents.dataflows.interface import get_hk_stock_data_unified
                        hk_data_text = get_hk_stock_data_unified(symbol, start_date, end_date)

                        if hk_data_text and "❌" not in hk_data_text:
                            formatted_data = hk_data_text
                            data_source = "akshare_hk"
                            logger.info(f"✅ AKShare港股数据获取成功: {symbol}")
                        else:
                            raise Exception("AKShare港股数据获取失败")

                    except Exception as e:
                        logger.error(f"⚠️ AKShare港股数据获取失败: {e}")
                        # 备用方案：Yahoo Finance
                        logger.info(f"🔄 使用Yahoo Finance备用方案获取港股数据: {symbol}")

                        self._wait_for_rate_limit()
                        ticker = yf.Ticker(symbol)  # 港股代码保持原格式
                        data = ticker.history(start=start_date, end=end_date)

                        if not data.empty:
                            formatted_data = self._format_stock_data(symbol, data, start_date, end_date)
                            data_source = "yfinance_hk"
                            logger.info(f"✅ Yahoo Finance港股数据获取成功: {symbol}")
                        else:
                            logger.error(f"❌ Yahoo Finance港股数据为空: {symbol}")
                else:
                    # 美股使用Yahoo Finance
                    logger.info(f"🇺🇸 从Yahoo Finance API获取美股数据: {symbol}")
                    self._wait_for_rate_limit()

                    # 获取数据
                    ticker = yf.Ticker(symbol.upper())
                    data = ticker.history(start=start_date, end=end_date)

                    if data.empty:
                        error_msg = f"未找到股票 '{symbol}' 在 {start_date} 到 {end_date} 期间的数据"
                        logger.error(f"❌ {error_msg}")
                    else:
                        # 格式化数据
                        formatted_data = self._format_stock_data(symbol, data, start_date, end_date)
                        data_source = "yfinance"
                        logger.info(f"✅ Yahoo Finance美股数据获取成功: {symbol}")

            except Exception as e:
                logger.error(f"❌ 数据获取失败: {e}")
                formatted_data = None

        # 如果所有API都失败，生成备用数据
        if not formatted_data:
            error_msg = "所有美股数据源都不可用"
            logger.error(f"❌ {error_msg}")
            return self._generate_fallback_data(symbol, start_date, end_date, error_msg)

        # 保存到缓存
        self.cache.save_stock_data(
            symbol=symbol,
            data=formatted_data,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source
        )

        return formatted_data
    
    def _format_stock_data(self, symbol: str, data: pd.DataFrame, 
                          start_date: str, end_date: str) -> str:
        """格式化股票数据为字符串"""
        
        # 移除时区信息
        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        
        # 四舍五入数值
        numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
        for col in numeric_columns:
            if col in data.columns:
                data[col] = data[col].round(2)
        
        # 获取最新价格和统计信息
        latest_price = data['Close'].iloc[-1]
        price_change = data['Close'].iloc[-1] - data['Close'].iloc[0]
        price_change_pct = (price_change / data['Close'].iloc[0]) * 100
        
        # 计算技术指标
        data['MA5'] = data['Close'].rolling(window=5).mean()
        data['MA10'] = data['Close'].rolling(window=10).mean()
        data['MA20'] = data['Close'].rolling(window=20).mean()
        
        # 计算RSI
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 格式化输出
        result = f"""# {symbol} 美股数据分析

## 📊 基本信息
- 股票代码: {symbol}
- 数据期间: {start_date} 至 {end_date}
- 数据条数: {len(data)}条
- 最新价格: ${latest_price:.2f}
- 期间涨跌: ${price_change:+.2f} ({price_change_pct:+.2f}%)

## 📈 价格统计
- 期间最高: ${data['High'].max():.2f}
- 期间最低: ${data['Low'].min():.2f}
- 平均成交量: {data['Volume'].mean():,.0f}

## 🔍 技术指标
- MA5: ${data['MA5'].iloc[-1]:.2f}
- MA10: ${data['MA10'].iloc[-1]:.2f}
- MA20: ${data['MA20'].iloc[-1]:.2f}
- RSI: {rsi.iloc[-1]:.2f}

## 📋 最近5日数据
{data.tail().to_string()}

数据来源: Yahoo Finance API
更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return result
    
    def _try_get_old_cache(self, symbol: str, start_date: str, end_date: str) -> Optional[str]:
        """尝试获取过期的缓存数据作为备用"""
        try:
            # 查找任何相关的缓存，不考虑TTL
            for metadata_file in self.cache.metadata_dir.glob(f"*_meta.json"):
                try:
                    import json
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    if (metadata.get('symbol') == symbol and 
                        metadata.get('data_type') == 'stock_data' and
                        metadata.get('market_type') == 'us'):
                        
                        cache_key = metadata_file.stem.replace('_meta', '')
                        cached_data = self.cache.load_stock_data(cache_key)
                        if cached_data:
                            return cached_data + "\n\n⚠️ 注意: 使用的是过期缓存数据"
                except Exception:
                    continue
        except Exception:
            pass
        
        return None

    def _get_data_from_finnhub(self, symbol: str, start_date: str, end_date: str) -> str:
        """从FINNHUB API获取股票数据"""
        try:
            import finnhub
            import os
            from datetime import datetime, timedelta


            # 获取API密钥
            api_key = os.getenv('FINNHUB_API_KEY')
            if not api_key:
                return None

            client = finnhub.Client(api_key=api_key)

            # 获取实时报价
            quote = client.quote(symbol.upper())
            if not quote or 'c' not in quote:
                return None

            # 获取公司信息
            profile = client.company_profile2(symbol=symbol.upper())
            company_name = profile.get('name', symbol.upper()) if profile else symbol.upper()

            # 格式化数据
            current_price = quote.get('c', 0)
            change = quote.get('d', 0)
            change_percent = quote.get('dp', 0)

            formatted_data = f"""# {symbol.upper()} 美股数据分析

## 📊 实时行情
- 股票名称: {company_name}
- 当前价格: ${current_price:.2f}
- 涨跌额: ${change:+.2f}
- 涨跌幅: {change_percent:+.2f}%
- 开盘价: ${quote.get('o', 0):.2f}
- 最高价: ${quote.get('h', 0):.2f}
- 最低价: ${quote.get('l', 0):.2f}
- 前收盘: ${quote.get('pc', 0):.2f}
- 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📈 数据概览
- 数据期间: {start_date} 至 {end_date}
- 数据来源: FINNHUB API (实时数据)
- 当前价位相对位置: {((current_price - quote.get('l', current_price)) / max(quote.get('h', current_price) - quote.get('l', current_price), 0.01) * 100):.1f}%
- 日内振幅: {((quote.get('h', 0) - quote.get('l', 0)) / max(quote.get('pc', 1), 0.01) * 100):.2f}%

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            return formatted_data

        except Exception as e:
            logger.error(f"❌ FINNHUB数据获取失败: {e}")
            return None

    def _generate_fallback_data(self, symbol: str, start_date: str, end_date: str, error_msg: str) -> str:
        """生成备用数据"""
        return f"""# {symbol} 美股数据获取失败

## ❌ 错误信息
{error_msg}

## 📊 模拟数据（仅供演示）
- 股票代码: {symbol}
- 数据期间: {start_date} 至 {end_date}
- 最新价格: ${random.uniform(100, 300):.2f}
- 模拟涨跌: {random.uniform(-5, 5):+.2f}%

## ⚠️ 重要提示
由于API限制或网络问题，无法获取实时数据。
建议稍后重试或检查网络连接。

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""


# 全局实例
_us_data_provider = None

def get_optimized_us_data_provider() -> OptimizedUSDataProvider:
    """获取全局美股数据提供器实例"""
    global _us_data_provider
    if _us_data_provider is None:
        _us_data_provider = OptimizedUSDataProvider()
    return _us_data_provider


def get_us_stock_data_cached(symbol: str, start_date: str, end_date: str, 
                           force_refresh: bool = False) -> str:
    """
    获取美股数据的便捷函数
    
    Args:
        symbol: 股票代码
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        force_refresh: 是否强制刷新缓存
    
    Returns:
        格式化的股票数据字符串
    """
    provider = get_optimized_us_data_provider()
    return provider.get_stock_data(symbol, start_date, end_date, force_refresh)
