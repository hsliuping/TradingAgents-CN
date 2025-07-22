"""
Stock utility functions
Provide stock code identification, classification, and processing functions
"""

import re
from typing import Dict, Tuple, Optional
from enum import Enum

# Import unified logging system
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


class StockMarket(Enum):
    """Stock market enumeration"""
    CHINA_A = "china_a"      # China A-shares
    HONG_KONG = "hong_kong"  # Hong Kong stocks
    US = "us"                # US stocks
    UNKNOWN = "unknown"      # Unknown


class StockUtils:
    """Stock utility class"""
    
    @staticmethod
    def identify_stock_market(ticker: str) -> StockMarket:
        """
        Identify the market to which the stock code belongs
        
        Args:
            ticker: Stock code
            
        Returns:
            StockMarket: Stock market type
        """
        if not ticker:
            return StockMarket.UNKNOWN
            
        ticker = str(ticker).strip().upper()
        
        # China A-shares: 6 digits
        if re.match(r'^\d{6}$', ticker):
            return StockMarket.CHINA_A

        # Hong Kong stocks: 4-5 digits.HK (supports 0700.HK and 09988.HK formats)
        if re.match(r'^\d{4,5}\.HK$', ticker):
            return StockMarket.HONG_KONG

        # US stocks: 1-5 letters
        if re.match(r'^[A-Z]{1,5}$', ticker):
            return StockMarket.US
            
        return StockMarket.UNKNOWN
    
    @staticmethod
    def is_china_stock(ticker: str) -> bool:
        """
        Determine if it is a China A-share
        
        Args:
            ticker: Stock code
            
        Returns:
            bool: Whether it is a China A-share
        """
        return StockUtils.identify_stock_market(ticker) == StockMarket.CHINA_A
    
    @staticmethod
    def is_hk_stock(ticker: str) -> bool:
        """
        Determine if it is a Hong Kong stock
        
        Args:
            ticker: Stock code
            
        Returns:
            bool: Whether it is a Hong Kong stock
        """
        return StockUtils.identify_stock_market(ticker) == StockMarket.HONG_KONG
    
    @staticmethod
    def is_us_stock(ticker: str) -> bool:
        """
        Determine if it is a US stock
        
        Args:
            ticker: Stock code
            
        Returns:
            bool: Whether it is a US stock
        """
        return StockUtils.identify_stock_market(ticker) == StockMarket.US
    
    @staticmethod
    def get_currency_info(ticker: str) -> Tuple[str, str]:
        """
        Get currency information based on stock code
        
        Args:
            ticker: Stock code
            
        Returns:
            Tuple[str, str]: (Currency name, Currency symbol)
        """
        market = StockUtils.identify_stock_market(ticker)
        
        if market == StockMarket.CHINA_A:
            return "Chinese Yuan", "¥"
        elif market == StockMarket.HONG_KONG:
            return "Hong Kong Dollar", "HK$"
        elif market == StockMarket.US:
            return "US Dollar", "$"
        else:
            return "Unknown", "?"
    
    @staticmethod
    def get_data_source(ticker: str) -> str:
        """
        Get recommended data sources based on stock code
        
        Args:
            ticker: Stock code
            
        Returns:
            str: Data source name
        """
        market = StockUtils.identify_stock_market(ticker)
        
        if market == StockMarket.CHINA_A:
            return "china_unified"  # Use unified Chinese stock data source
        elif market == StockMarket.HONG_KONG:
            return "yahoo_finance"  # Hong Kong stocks use Yahoo Finance
        elif market == StockMarket.US:
            return "yahoo_finance"  # US stocks use Yahoo Finance
        else:
            return "unknown"
    
    @staticmethod
    def normalize_hk_ticker(ticker: str) -> str:
        """
        Standardize Hong Kong stock code format
        
        Args:
            ticker: Original Hong Kong stock code
            
        Returns:
            str: Standardized Hong Kong stock code
        """
        if not ticker:
            return ticker
            
        ticker = str(ticker).strip().upper()
        
        # If it is pure 4-5 digits, add .HK suffix
        if re.match(r'^\d{4,5}$', ticker):
            return f"{ticker}.HK"

        # If it is already in the correct format, return directly
        if re.match(r'^\d{4,5}\.HK$', ticker):
            return ticker
            
        return ticker
    
    @staticmethod
    def get_market_info(ticker: str) -> Dict:
        """
        Get detailed market information
        
        Args:
            ticker: Stock code
            
        Returns:
            Dict: Market information dictionary
        """
        market = StockUtils.identify_stock_market(ticker)
        currency_name, currency_symbol = StockUtils.get_currency_info(ticker)
        data_source = StockUtils.get_data_source(ticker)
        
        market_names = {
            StockMarket.CHINA_A: "China A-shares",
            StockMarket.HONG_KONG: "Hong Kong stocks",
            StockMarket.US: "US stocks",
            StockMarket.UNKNOWN: "Unknown market"
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


# Convenient functions, for backward compatibility
def is_china_stock(ticker: str) -> bool:
    """Determine if it is a China A-share (backward compatibility)"""
    return StockUtils.is_china_stock(ticker)


def is_hk_stock(ticker: str) -> bool:
    """Determine if it is a Hong Kong stock"""
    return StockUtils.is_hk_stock(ticker)


def is_us_stock(ticker: str) -> bool:
    """Determine if it is a US stock"""
    return StockUtils.is_us_stock(ticker)


def get_stock_market_info(ticker: str) -> Dict:
    """Get stock market information"""
    return StockUtils.get_market_info(ticker)
