"""
股票工具函数
提供股票代码识别、分类和处理功能
"""

import re
from typing import Dict, Tuple, Optional
from enum import Enum

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


class StockMarket(Enum):
    """股票市场枚举"""
    CHINA_A = "china_a"      # 中国A股
    HONG_KONG = "hong_kong"  # 港股
    US = "us"                # 美股
    UNKNOWN = "unknown"      # 未知


class SecurityType(Enum):
    """证券类型枚举"""
    STOCK = "stock"          # 股票
    FUND = "fund"            # 基金/ETF
    BOND = "bond"            # 债券
    INDEX = "index"          # 指数
    UNKNOWN = "unknown"      # 未知


class StockUtils:
    """股票工具类"""
    
    @staticmethod
    def identify_stock_market(ticker: str) -> StockMarket:
        """
        识别股票代码所属市场

        Args:
            ticker: 股票代码

        Returns:
            StockMarket: 股票市场类型
        """
        if not ticker:
            return StockMarket.UNKNOWN

        ticker = str(ticker).strip().upper()

        # 中国A股：纯6位数字（前后端统一，不带后缀）
        if re.match(r'^\d{6}$', ticker):
            return StockMarket.CHINA_A

        # 港股：4-5位数字.HK 或 纯4-5位数字（支持0700.HK、09988.HK、00700、9988格式）
        if re.match(r'^\d{4,5}\.HK$', ticker) or re.match(r'^\d{4,5}$', ticker):
            return StockMarket.HONG_KONG

        # 美股：1-5位字母
        if re.match(r'^[A-Z]{1,5}$', ticker):
            return StockMarket.US

        return StockMarket.UNKNOWN

    @staticmethod
    def identify_security_type(ticker: str) -> SecurityType:
        """
        识别证券类型（股票/基金/债券/指数）

        A股代码规则：
        - 股票：
          - 上海主板：600xxx, 601xxx, 603xxx, 605xxx
          - 上海科创板：688xxx
          - 深圳主板：000xxx, 001xxx
          - 深圳中小板：002xxx
          - 深圳创业板：300xxx, 301xxx
          - 北交所：8xxxxx, 4xxxxx
        - 基金/ETF：
          - 上海交易所：5xxxxx (如 510050 上证50ETF)
          - 深圳交易所：1xxxxx (如 159919 沪深300ETF)
          - LOF基金：16xxxx
        - 债券：
          - 国债：01xxxx
          - 企业债：12xxxx, 11xxxx
          - 可转债：11xxxx, 12xxxx, 13xxxx
        - 指数：
          - 上证指数：000xxx (如 000001 上证综指)
          - 深证指数：399xxx

        Args:
            ticker: 证券代码

        Returns:
            SecurityType: 证券类型
        """
        if not ticker:
            return SecurityType.UNKNOWN

        # 去掉后缀，只保留数字部分
        ticker = str(ticker).strip().upper()
        code = re.sub(r'\.(SZ|SH|BJ)$', '', ticker)

        if not code.isdigit() or len(code) != 6:
            return SecurityType.UNKNOWN

        prefix = code[:2]
        prefix3 = code[:3]

        # 基金/ETF 识别（优先判断，因为基金代码范围更明确）
        # 上海交易所基金：5xxxxx
        if prefix == '51' or prefix == '50' or prefix == '52':
            return SecurityType.FUND
        # 深圳交易所基金：1xxxxx (15xxxx, 16xxxx)
        if prefix == '15' or prefix == '16':
            return SecurityType.FUND

        # 指数识别
        # 上证指数：000xxx 开头但在特定范围
        # 注意：000001-000999 在深圳是股票，在上海是指数
        # 简化处理：399xxx 是深证指数
        if prefix3 == '399':
            return SecurityType.INDEX

        # 债券识别（简化，主要识别可转债）
        # 可转债深圳：12xxxx, 13xxxx
        # 可转债上海：11xxxx
        if prefix == '11' or prefix == '12' or prefix == '13':
            # 进一步区分：110xxx, 113xxx, 127xxx, 128xxx 是可转债
            if prefix3 in ['110', '113', '127', '128', '123']:
                return SecurityType.BOND

        # 股票识别（剩余的6位数字代码）
        # 上海主板：600xxx, 601xxx, 603xxx, 605xxx
        if prefix in ['60']:
            return SecurityType.STOCK
        # 上海科创板：688xxx
        if prefix3 == '688':
            return SecurityType.STOCK
        # 深圳主板：000xxx, 001xxx
        if prefix in ['00']:
            return SecurityType.STOCK
        # 深圳中小板：002xxx
        if prefix3 == '002':
            return SecurityType.STOCK
        # 深圳创业板：300xxx, 301xxx
        if prefix in ['30']:
            return SecurityType.STOCK
        # 北交所：8xxxxx, 4xxxxx
        if prefix[0] in ['8', '4']:
            return SecurityType.STOCK

        return SecurityType.UNKNOWN

    @staticmethod
    def is_stock(ticker: str) -> bool:
        """
        判断是否为股票（排除基金、债券、指数）

        Args:
            ticker: 证券代码

        Returns:
            bool: 是否为股票
        """
        return StockUtils.identify_security_type(ticker) == SecurityType.STOCK

    @staticmethod
    def is_fund(ticker: str) -> bool:
        """
        判断是否为基金/ETF

        Args:
            ticker: 证券代码

        Returns:
            bool: 是否为基金/ETF
        """
        return StockUtils.identify_security_type(ticker) == SecurityType.FUND

    @staticmethod
    def is_china_stock(ticker: str) -> bool:
        """
        判断是否为中国A股
        
        Args:
            ticker: 股票代码
            
        Returns:
            bool: 是否为中国A股
        """
        return StockUtils.identify_stock_market(ticker) == StockMarket.CHINA_A
    
    @staticmethod
    def is_hk_stock(ticker: str) -> bool:
        """
        判断是否为港股
        
        Args:
            ticker: 股票代码
            
        Returns:
            bool: 是否为港股
        """
        return StockUtils.identify_stock_market(ticker) == StockMarket.HONG_KONG
    
    @staticmethod
    def is_us_stock(ticker: str) -> bool:
        """
        判断是否为美股
        
        Args:
            ticker: 股票代码
            
        Returns:
            bool: 是否为美股
        """
        return StockUtils.identify_stock_market(ticker) == StockMarket.US
    
    @staticmethod
    def get_currency_info(ticker: str) -> Tuple[str, str]:
        """
        根据股票代码获取货币信息
        
        Args:
            ticker: 股票代码
            
        Returns:
            Tuple[str, str]: (货币名称, 货币符号)
        """
        market = StockUtils.identify_stock_market(ticker)
        
        if market == StockMarket.CHINA_A:
            return "人民币", "¥"
        elif market == StockMarket.HONG_KONG:
            return "港币", "HK$"
        elif market == StockMarket.US:
            return "美元", "$"
        else:
            return "未知", "?"
    
    @staticmethod
    def get_data_source(ticker: str) -> str:
        """
        根据股票代码获取推荐的数据源
        
        Args:
            ticker: 股票代码
            
        Returns:
            str: 数据源名称
        """
        market = StockUtils.identify_stock_market(ticker)
        
        if market == StockMarket.CHINA_A:
            return "china_unified"  # 使用统一的中国股票数据源
        elif market == StockMarket.HONG_KONG:
            return "yahoo_finance"  # 港股使用Yahoo Finance
        elif market == StockMarket.US:
            return "yahoo_finance"  # 美股使用Yahoo Finance
        else:
            return "unknown"
    
    @staticmethod
    def normalize_hk_ticker(ticker: str) -> str:
        """
        标准化港股代码格式
        
        Args:
            ticker: 原始港股代码
            
        Returns:
            str: 标准化后的港股代码
        """
        if not ticker:
            return ticker
            
        ticker = str(ticker).strip().upper()
        
        # 如果是纯4-5位数字，添加.HK后缀
        if re.match(r'^\d{4,5}$', ticker):
            return f"{ticker}.HK"

        # 如果已经是正确格式，直接返回
        if re.match(r'^\d{4,5}\.HK$', ticker):
            return ticker
            
        return ticker
    
    @staticmethod
    def get_market_info(ticker: str) -> Dict:
        """
        获取股票市场的详细信息
        
        Args:
            ticker: 股票代码
            
        Returns:
            Dict: 市场信息字典
        """
        market = StockUtils.identify_stock_market(ticker)
        currency_name, currency_symbol = StockUtils.get_currency_info(ticker)
        data_source = StockUtils.get_data_source(ticker)
        
        market_names = {
            StockMarket.CHINA_A: "中国A股",
            StockMarket.HONG_KONG: "港股",
            StockMarket.US: "美股",
            StockMarket.UNKNOWN: "未知市场"
        }
        
        return {
            "ticker": ticker,
            "market": market.value,
            "market_name": market_names[market],
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            "data_source": data_source,
            "is_china": market == StockMarket.CHINA_A,
            "is_hk": market == StockMarket.HONG_KONG,
            "is_us": market == StockMarket.US
        }


# 便捷函数，保持向后兼容
def is_china_stock(ticker: str) -> bool:
    """判断是否为中国A股（向后兼容）"""
    return StockUtils.is_china_stock(ticker)


def is_hk_stock(ticker: str) -> bool:
    """判断是否为港股"""
    return StockUtils.is_hk_stock(ticker)


def is_us_stock(ticker: str) -> bool:
    """判断是否为美股"""
    return StockUtils.is_us_stock(ticker)


def get_stock_market_info(ticker: str) -> Dict:
    """获取股票市场信息"""
    return StockUtils.get_market_info(ticker)
