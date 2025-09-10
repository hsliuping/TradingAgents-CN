#!/usr/bin/env python3
"""
加密货币数据工具
集成CoinGecko API提供加密货币市场数据
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')

# 导入缓存管理器
try:
    from .cache_manager import get_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    logger.warning("⚠️ 缓存管理器不可用")


class CryptoDataProvider:
    """加密货币数据提供器"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.cache = get_cache() if CACHE_AVAILABLE else None
        self.last_api_call = 0
        self.min_api_interval = 1.0  # API限制间隔
        
    def _wait_for_rate_limit(self):
        """等待API限制"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        
        if time_since_last_call < self.min_api_interval:
            wait_time = self.min_api_interval - time_since_last_call
            time.sleep(wait_time)
        
        self.last_api_call = time.time()
    
    def get_crypto_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """获取加密货币历史数据"""
        try:
            # 检查缓存
            if self.cache:
                cache_key = self.cache.find_cached_stock_data(
                    symbol=symbol.lower(),
                    start_date=start_date,
                    end_date=end_date,
                    data_source="coingecko"
                )
                if cache_key:
                    cached_data = self.cache.load_stock_data(cache_key)
                    if cached_data:
                        logger.info(f"⚡ 从缓存加载加密货币数据: {symbol}")
                        return cached_data
            
            # 获取币种ID
            coin_id = self._get_coin_id(symbol)
            if not coin_id:
                return f"❌ 未找到加密货币: {symbol}"
            
            # 获取历史数据
            self._wait_for_rate_limit()
            
            # 计算日期范围
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end_dt - start_dt).days + 1
            
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': min(days, 365),  # CoinGecko限制
                'interval': 'daily'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 格式化数据
            formatted_data = self._format_crypto_data(symbol, coin_id, data, start_date, end_date)
            
            # 保存到缓存
            if self.cache:
                self.cache.save_stock_data(
                    symbol=symbol.lower(),
                    data=formatted_data,
                    start_date=start_date,
                    end_date=end_date,
                    data_source="coingecko"
                )
            
            return formatted_data
            
        except Exception as e:
            logger.error(f"❌ 获取加密货币数据失败: {e}")
            return f"❌ 获取{symbol}数据失败: {e}"
    
    def get_crypto_info(self, symbol: str) -> Dict:
        """获取加密货币基本信息"""
        try:
            coin_id = self._get_coin_id(symbol)
            if not coin_id:
                return {'symbol': symbol, 'name': f'加密货币{symbol}', 'source': 'coingecko'}
            
            self._wait_for_rate_limit()
            
            url = f"{self.base_url}/coins/{coin_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                'symbol': symbol.upper(),
                'name': data.get('name', symbol),
                'market_cap_rank': data.get('market_cap_rank', 'N/A'),
                'current_price': data.get('market_data', {}).get('current_price', {}).get('usd', 'N/A'),
                'market_cap': data.get('market_data', {}).get('market_cap', {}).get('usd', 'N/A'),
                'total_volume': data.get('market_data', {}).get('total_volume', {}).get('usd', 'N/A'),
                'source': 'coingecko'
            }
            
        except Exception as e:
            logger.error(f"❌ 获取加密货币信息失败: {e}")
            return {'symbol': symbol, 'name': f'加密货币{symbol}', 'source': 'coingecko', 'error': str(e)}
    
    def _get_coin_id(self, symbol: str) -> Optional[str]:
        """获取CoinGecko币种ID"""
        # 常见币种映射
        common_coins = {
            'btc': 'bitcoin',
            'eth': 'ethereum',
            'bnb': 'binancecoin',
            'ada': 'cardano',
            'sol': 'solana',
            'xrp': 'ripple',
            'dot': 'polkadot',
            'doge': 'dogecoin',
            'avax': 'avalanche-2',
            'matic': 'matic-network',
            'link': 'chainlink',
            'uni': 'uniswap',
            'ltc': 'litecoin',
            'atom': 'cosmos',
            'etc': 'ethereum-classic',
            'xlm': 'stellar',
            'vet': 'vechain',
            'icp': 'internet-computer',
            'fil': 'filecoin',
            'trx': 'tron'
        }
        
        symbol_lower = symbol.lower()
        if symbol_lower in common_coins:
            return common_coins[symbol_lower]
        
        # 如果不在常见列表中，尝试API查询
        try:
            self._wait_for_rate_limit()
            url = f"{self.base_url}/coins/list"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            coins = response.json()
            
            for coin in coins:
                if coin['symbol'].lower() == symbol_lower:
                    return coin['id']
                    
        except Exception as e:
            logger.error(f"❌ 查询币种ID失败: {e}")
        
        return None
    
    def _format_crypto_data(self, symbol: str, coin_id: str, data: Dict, start_date: str, end_date: str) -> str:
        """格式化加密货币数据"""
        try:
            prices = data.get('prices', [])
            volumes = data.get('total_volumes', [])
            market_caps = data.get('market_caps', [])
            
            if not prices:
                return f"❌ {symbol}数据为空"
            
            # 转换为DataFrame
            df = pd.DataFrame(prices, columns=['timestamp', 'price'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
            df['volume'] = [v[1] for v in volumes] if volumes else [0] * len(df)
            df['market_cap'] = [m[1] for m in market_caps] if market_caps else [0] * len(df)
            
            # 计算统计数据
            latest_price = df['price'].iloc[-1]
            first_price = df['price'].iloc[0]
            price_change = latest_price - first_price
            price_change_pct = (price_change / first_price) * 100
            
            # 计算技术指标
            df['ma7'] = df['price'].rolling(window=7).mean()
            df['ma30'] = df['price'].rolling(window=30).mean()
            
            # 计算波动率
            df['returns'] = df['price'].pct_change()
            volatility = df['returns'].std() * (365 ** 0.5) * 100  # 年化波动率
            
            result = f"""# {symbol.upper()} 加密货币数据分析

## 📊 基本信息
- 币种代码: {symbol.upper()}
- 币种名称: {coin_id.replace('-', ' ').title()}
- 数据期间: {start_date} 至 {end_date}
- 数据条数: {len(df)}条
- 当前价格: ${latest_price:,.4f}
- 期间涨跌: ${price_change:+,.4f} ({price_change_pct:+.2f}%)

## 📈 价格统计
- 期间最高: ${df['price'].max():,.4f}
- 期间最低: ${df['price'].min():,.4f}
- 平均价格: ${df['price'].mean():,.4f}
- 年化波动率: {volatility:.2f}%
- 平均日成交量: ${df['volume'].mean():,.0f}

## 🔍 技术指标
- MA7: ${df['ma7'].iloc[-1]:,.4f}
- MA30: ${df['ma30'].iloc[-1]:,.4f}
- 最新市值: ${df['market_cap'].iloc[-1]:,.0f}

## 📋 最近5日数据
{df[['date', 'price', 'volume']].tail().to_string(index=False)}

数据来源: CoinGecko API
更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 格式化加密货币数据失败: {e}")
            return f"❌ 格式化{symbol}数据失败: {e}"


# 全局实例
_crypto_provider = None

def get_crypto_provider() -> CryptoDataProvider:
    """获取全局加密货币数据提供器实例"""
    global _crypto_provider
    if _crypto_provider is None:
        _crypto_provider = CryptoDataProvider()
    return _crypto_provider