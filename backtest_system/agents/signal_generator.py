"""
信号生成器
Signal Generator

用于生成交易信号的辅助模块
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class SignalGenerator:
    """信号生成器"""

    def __init__(self, config: Dict = None):
        """
        初始化信号生成器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def generate_technical_signals(self, price_data: pd.DataFrame) -> Dict:
        """
        生成技术指标信号

        Args:
            price_data: 价格数据

        Returns:
            Dict: 技术信号
        """
        signals = {}

        try:
            if price_data.empty or 'close' not in price_data.columns:
                return signals

            prices = price_data['close']

            # 移动平均线信号
            if len(prices) >= 5:
                signals['ma5'] = prices.rolling(window=5).mean().iloc[-1]
            if len(prices) >= 10:
                signals['ma10'] = prices.rolling(window=10).mean().iloc[-1]
            if len(prices) >= 20:
                signals['ma20'] = prices.rolling(window=20).mean().iloc[-1]

            # RSI信号
            if len(prices) >= 14:
                signals['rsi'] = self._calculate_rsi(prices, 14)

            # MACD信号
            if len(prices) >= 26:
                macd_data = self._calculate_macd(prices)
                signals.update(macd_data)

            # 布林带信号
            if len(prices) >= 20:
                bb_data = self._calculate_bollinger_bands(prices, 20)
                signals.update(bb_data)

        except Exception as e:
            self.logger.error(f"生成技术信号失败: {e}")

        return signals

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """计算RSI指标"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not rsi.empty else 50.0
        except:
            return 50.0

    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """计算MACD指标"""
        try:
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal).mean()
            histogram = macd_line - signal_line

            return {
                'macd': macd_line.iloc[-1] if not macd_line.empty else 0,
                'macd_signal': signal_line.iloc[-1] if not signal_line.empty else 0,
                'macd_histogram': histogram.iloc[-1] if not histogram.empty else 0
            }
        except:
            return {'macd': 0, 'macd_signal': 0, 'macd_histogram': 0}

    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> Dict:
        """计算布林带"""
        try:
            sma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)

            return {
                'bb_upper': upper_band.iloc[-1] if not upper_band.empty else 0,
                'bb_middle': sma.iloc[-1] if not sma.empty else 0,
                'bb_lower': lower_band.iloc[-1] if not lower_band.empty else 0
            }
        except:
            return {'bb_upper': 0, 'bb_middle': 0, 'bb_lower': 0}