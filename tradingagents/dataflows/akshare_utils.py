#!/usr/bin/env python3
"""
AKShare数据源工具
提供AKShare数据获取的统一接口
"""

import pandas as pd
from typing import Optional, Dict, Any
import warnings

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')
warnings.filterwarnings('ignore')

class AKShareProvider:
    """AKShare数据提供器"""

    def __init__(self):
        """初始化AKShare提供器"""
        try:
            import akshare as ak
            self.ak = ak
            self.connected = True

            # 设置更长的超时时间
            self._configure_timeout()

            logger.info(f"✅ AKShare初始化成功")
        except ImportError:
            self.ak = None
            self.connected = False
            logger.error(f"❌ AKShare未安装")

    def _configure_timeout(self):
        """配置AKShare的超时设置"""
        try:
            import requests
            import socket

            # 设置更长的超时时间
            socket.setdefaulttimeout(60)  # 60秒超时

            # 如果AKShare使用requests，设置默认超时
            if hasattr(requests, 'adapters'):
                from requests.adapters import HTTPAdapter
                from urllib3.util.retry import Retry

                # 创建重试策略
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                )

                # 设置适配器
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session = requests.Session()
                session.mount("http://", adapter)
                session.mount("https://", adapter)

                logger.info(f"🔧 AKShare超时配置完成: 60秒超时，3次重试")

        except Exception as e:
            logger.error(f"⚠️ AKShare超时配置失败: {e}")
            logger.info(f"🔧 使用默认超时设置")
    
    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """获取股票历史数据"""
        if not self.connected:
            return None
        
        try:
            # 转换股票代码格式
            if len(symbol) == 6:
                symbol = symbol
            else:
                symbol = symbol.replace('.SZ', '').replace('.SS', '')
            
            # 获取数据
            data = self.ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date.replace('-', '') if start_date else "20240101",
                end_date=end_date.replace('-', '') if end_date else "20241231",
                adjust=""
            )
            
            return data
            
        except Exception as e:
            logger.error(f"❌ AKShare获取股票数据失败: {e}")
            return None
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本信息"""
        if not self.connected:
            return {}
        
        try:
            # 获取股票基本信息
            stock_list = self.ak.stock_info_a_code_name()
            stock_info = stock_list[stock_list['code'] == symbol]
            
            if not stock_info.empty:
                return {
                    'symbol': symbol,
                    'name': stock_info.iloc[0]['name'],
                    'source': 'akshare'
                }
            else:
                return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'akshare'}
                
        except Exception as e:
            logger.error(f"❌ AKShare获取股票信息失败: {e}")
            return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'akshare'}

    def get_hk_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """
        获取港股历史数据

        Args:
            symbol: 港股代码 (如: 00700 或 0700.HK)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            DataFrame: 港股历史数据
        """
        if not self.connected:
            logger.error(f"❌ AKShare未连接")
            return None

        try:
            # 标准化港股代码 - AKShare使用5位数字格式
            hk_symbol = self._normalize_hk_symbol_for_akshare(symbol)

            logger.info(f"🇭🇰 AKShare获取港股数据: {hk_symbol} ({start_date} 到 {end_date})")

            # 格式化日期为AKShare需要的格式
            start_date_formatted = start_date.replace('-', '') if start_date else "20240101"
            end_date_formatted = end_date.replace('-', '') if end_date else "20241231"

            # 使用AKShare获取港股历史数据（带超时保护）
            import threading

            result = [None]
            exception = [None]

            def fetch_hist_data():
                try:
                    result[0] = self.ak.stock_hk_hist(
                        symbol=hk_symbol,
                        period="daily",
                        start_date=start_date_formatted,
                        end_date=end_date_formatted,
                        adjust=""
                    )
                except Exception as e:
                    exception[0] = e

            # 启动线程
            thread = threading.Thread(target=fetch_hist_data)
            thread.daemon = True
            thread.start()

            # 等待60秒
            thread.join(timeout=60)

            if thread.is_alive():
                # 超时了
                logger.warning(f"⚠️ AKShare港股历史数据获取超时（60秒）: {symbol}")
                raise Exception(f"AKShare港股历史数据获取超时（60秒）: {symbol}")
            elif exception[0]:
                # 有异常
                raise exception[0]
            else:
                # 成功
                data = result[0]

            if not data.empty:
                # 数据预处理
                data = data.reset_index()
                data['Symbol'] = symbol  # 保持原始格式

                # 重命名列以保持一致性
                column_mapping = {
                    '日期': 'Date',
                    '开盘': 'Open',
                    '收盘': 'Close',
                    '最高': 'High',
                    '最低': 'Low',
                    '成交量': 'Volume',
                    '成交额': 'Amount'
                }

                for old_col, new_col in column_mapping.items():
                    if old_col in data.columns:
                        data = data.rename(columns={old_col: new_col})

                logger.info(f"✅ AKShare港股数据获取成功: {symbol}, {len(data)}条记录")
                return data
            else:
                logger.warning(f"⚠️ AKShare港股数据为空: {symbol}")
                return None

        except Exception as e:
            logger.error(f"❌ AKShare获取港股数据失败: {e}")
            return None

    def get_hk_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取港股基本信息

        Args:
            symbol: 港股代码

        Returns:
            Dict: 港股基本信息
        """
        if not self.connected:
            return {
                'symbol': symbol,
                'name': f'港股{symbol}',
                'currency': 'HKD',
                'exchange': 'HKG',
                'source': 'akshare_unavailable'
            }

        try:
            hk_symbol = self._normalize_hk_symbol_for_akshare(symbol)

            logger.info(f"🇭🇰 AKShare获取港股信息: {hk_symbol}")

            # 尝试获取港股实时行情数据来获取基本信息
            # 使用线程超时包装（兼容Windows）
            import threading
            import time


            result = [None]
            exception = [None]

            def fetch_data():
                try:
                    result[0] = self.ak.stock_hk_spot_em()
                except Exception as e:
                    exception[0] = e

            # 启动线程
            thread = threading.Thread(target=fetch_data)
            thread.daemon = True
            thread.start()

            # 等待60秒
            thread.join(timeout=60)

            if thread.is_alive():
                # 超时了
                logger.warning(f"⚠️ AKShare港股信息获取超时（60秒），使用备用方案")
                raise Exception("AKShare港股信息获取超时（60秒）")
            elif exception[0]:
                # 有异常
                raise exception[0]
            else:
                # 成功
                spot_data = result[0]

            # 查找对应的股票信息
            if not spot_data.empty:
                # 查找匹配的股票
                matching_stocks = spot_data[spot_data['代码'].str.contains(hk_symbol[:5], na=False)]

                if not matching_stocks.empty:
                    stock_info = matching_stocks.iloc[0]
                    return {
                        'symbol': symbol,
                        'name': stock_info.get('名称', f'港股{symbol}'),
                        'currency': 'HKD',
                        'exchange': 'HKG',
                        'latest_price': stock_info.get('最新价', None),
                        'source': 'akshare'
                    }

            # 如果没有找到，返回基本信息
            return {
                'symbol': symbol,
                'name': f'港股{symbol}',
                'currency': 'HKD',
                'exchange': 'HKG',
                'source': 'akshare'
            }

        except Exception as e:
            logger.error(f"❌ AKShare获取港股信息失败: {e}")
            return {
                'symbol': symbol,
                'name': f'港股{symbol}',
                'currency': 'HKD',
                'exchange': 'HKG',
                'source': 'akshare_error',
                'error': str(e)
            }

    def _normalize_hk_symbol_for_akshare(self, symbol: str) -> str:
        """
        标准化港股代码为AKShare格式

        Args:
            symbol: 原始港股代码 (如: 0700.HK 或 700)

        Returns:
            str: AKShare格式的港股代码 (如: 00700)
        """
        if not symbol:
            return symbol

        # 移除.HK后缀
        clean_symbol = symbol.replace('.HK', '').replace('.hk', '')

        # 确保是5位数字格式
        if clean_symbol.isdigit():
            return clean_symbol.zfill(5)

        return clean_symbol

def get_akshare_provider() -> AKShareProvider:
    """获取AKShare提供器实例"""
    return AKShareProvider()


# 便捷函数
def get_hk_stock_data_akshare(symbol: str, start_date: str = None, end_date: str = None) -> str:
    """
    使用AKShare获取港股数据的便捷函数

    Args:
        symbol: 港股代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        str: 格式化的港股数据
    """
    try:
        provider = get_akshare_provider()
        data = provider.get_hk_stock_data(symbol, start_date, end_date)

        if data is not None and not data.empty:
            return format_hk_stock_data_akshare(symbol, data, start_date, end_date)
        else:
            return f"❌ 无法获取港股 {symbol} 的AKShare数据"

    except Exception as e:
        return f"❌ AKShare港股数据获取失败: {e}"


def get_hk_stock_info_akshare(symbol: str) -> Dict[str, Any]:
    """
    使用AKShare获取港股信息的便捷函数

    Args:
        symbol: 港股代码

    Returns:
        Dict: 港股信息
    """
    try:
        provider = get_akshare_provider()
        return provider.get_hk_stock_info(symbol)
    except Exception as e:
        return {
            'symbol': symbol,
            'name': f'港股{symbol}',
            'currency': 'HKD',
            'exchange': 'HKG',
            'source': 'akshare_error',
            'error': str(e)
        }


def format_hk_stock_data_akshare(symbol: str, data: pd.DataFrame, start_date: str, end_date: str) -> str:
    """
    格式化AKShare港股数据为文本格式

    Args:
        symbol: 股票代码
        data: 股票数据DataFrame
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        str: 格式化的股票数据文本
    """
    if data is None or data.empty:
        return f"❌ 无法获取港股 {symbol} 的AKShare数据"

    try:
        # 获取股票基本信息（允许失败）
        stock_name = f'港股{symbol}'  # 默认名称
        try:
            provider = get_akshare_provider()
            stock_info = provider.get_hk_stock_info(symbol)
            stock_name = stock_info.get('name', f'港股{symbol}')
            logger.info(f"✅ 港股信息获取成功: {stock_name}")
        except Exception as info_error:
            logger.error(f"⚠️ 港股信息获取失败，使用默认信息: {info_error}")
            # 继续处理，使用默认信息

        # 计算统计信息
        latest_price = data['Close'].iloc[-1]
        price_change = data['Close'].iloc[-1] - data['Close'].iloc[0]
        price_change_pct = (price_change / data['Close'].iloc[0]) * 100

        avg_volume = data['Volume'].mean() if 'Volume' in data.columns else 0
        max_price = data['High'].max()
        min_price = data['Low'].min()

        # 格式化输出
        formatted_text = f"""
🇭🇰 港股数据报告 (AKShare)
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
            volume = row.get('Volume', 0)
            formatted_text += f"- {date}: 开盘HK${row['Open']:.2f}, 收盘HK${row['Close']:.2f}, 成交量{volume:,.0f}\n"

        formatted_text += f"\n数据来源: AKShare (港股)\n"

        return formatted_text

    except Exception as e:
        logger.error(f"❌ 格式化AKShare港股数据失败: {e}")
        return f"❌ AKShare港股数据格式化失败: {symbol}"
