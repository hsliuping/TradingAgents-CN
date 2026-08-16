#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票工具模块单元测试
覆盖 tradingagents/utils/stock_utils.py 的市场识别、货币、数据源等核心逻辑
"""

from tradingagents.utils.stock_utils import (
    StockUtils,
    StockMarket,
    is_china_stock,
    is_hk_stock,
    is_us_stock,
    get_stock_market_info,
)


# ---------- StockMarket 枚举 ----------

def test_stock_market_enum_values():
    """枚举值定义应保持稳定"""
    assert StockMarket.CHINA_A.value == "china_a"
    assert StockMarket.HONG_KONG.value == "hong_kong"
    assert StockMarket.US.value == "us"
    assert StockMarket.UNKNOWN.value == "unknown"


# ---------- identify_stock_market：市场识别 ----------

def test_identify_china_a_plain_six_digits():
    """纯 6 位数字应识别为 A 股（沪深北交易所）"""
    for ticker in ["600000", "000001", "300750", "688001", "430047"]:
        assert StockUtils.identify_stock_market(ticker) == StockMarket.CHINA_A


def test_identify_china_a_with_exchange_suffix():
    """带交易所后缀（.SH/.SZ/.BJ，Tushare ts_code 格式）的 A 股代码也应被识别"""
    for ticker in ["600000.SH", "688001.SH", "000001.SZ", "300750.SZ", "430047.BJ"]:
        assert StockUtils.identify_stock_market(ticker) == StockMarket.CHINA_A


def test_identify_hk_stock():
    """港股：4-5 位数字加 .HK 后缀，或纯 4-5 位数字"""
    for ticker in ["0700.HK", "09988.HK", "00700", "9988", "1234"]:
        assert StockUtils.identify_stock_market(ticker) == StockMarket.HONG_KONG


def test_identify_us_stock():
    """美股：1-5 位字母"""
    for ticker in ["AAPL", "GOOGL", "TSLA", "MSFT", "F"]:
        assert StockUtils.identify_stock_market(ticker) == StockMarket.US


def test_identify_unknown_market():
    """空值、含分隔符的代码、超长代码等应识别为未知市场"""
    for ticker in ["", None, "BRK.A", "AAPL.O", "600000.SHX", "1234567", "abcdef"]:
        assert StockUtils.identify_stock_market(ticker) == StockMarket.UNKNOWN


def test_identify_stock_market_trims_and_uppercases():
    """输入应去除首尾空白并统一大写（小写后缀也支持）"""
    assert StockUtils.identify_stock_market("  aapl  ") == StockMarket.US
    assert StockUtils.identify_stock_market("600000.sh") == StockMarket.CHINA_A
    assert StockUtils.identify_stock_market("0700.hk") == StockMarket.HONG_KONG


# ---------- is_*_stock 便捷判断 ----------

def test_is_china_stock():
    assert is_china_stock("600000") is True
    assert is_china_stock("600000.SH") is True
    assert is_china_stock("0700.HK") is False
    assert is_china_stock("AAPL") is False


def test_is_hk_stock():
    assert is_hk_stock("0700.HK") is True
    assert is_hk_stock("9988") is True
    assert is_hk_stock("600000") is False


def test_is_us_stock():
    assert is_us_stock("AAPL") is True
    assert is_us_stock("600000") is False


# ---------- get_currency_info：货币信息 ----------

def test_get_currency_info():
    assert StockUtils.get_currency_info("600000") == ("人民币", "¥")
    assert StockUtils.get_currency_info("0700.HK") == ("港币", "HK$")
    assert StockUtils.get_currency_info("AAPL") == ("美元", "$")
    assert StockUtils.get_currency_info("????") == ("未知", "?")


# ---------- get_data_source：数据源推荐 ----------

def test_get_data_source():
    assert StockUtils.get_data_source("600000") == "china_unified"
    assert StockUtils.get_data_source("600000.SH") == "china_unified"
    assert StockUtils.get_data_source("0700.HK") == "yahoo_finance"
    assert StockUtils.get_data_source("AAPL") == "yahoo_finance"
    assert StockUtils.get_data_source("????") == "unknown"


# ---------- normalize_hk_ticker：港股代码标准化 ----------

def test_normalize_hk_ticker():
    assert StockUtils.normalize_hk_ticker("0700") == "0700.HK"
    assert StockUtils.normalize_hk_ticker("9988") == "9988.HK"
    assert StockUtils.normalize_hk_ticker("0700.HK") == "0700.HK"
    assert StockUtils.normalize_hk_ticker("AAPL") == "AAPL"
    assert StockUtils.normalize_hk_ticker("") == ""
    assert StockUtils.normalize_hk_ticker(None) is None


# ---------- get_market_info：完整市场信息 ----------

def test_get_market_info_china_a():
    info = StockUtils.get_market_info("600000")
    assert info == {
        "ticker": "600000",
        "market": "china_a",
        "market_name": "中国A股",
        "currency_name": "人民币",
        "currency_symbol": "¥",
        "data_source": "china_unified",
        "is_china": True,
        "is_hk": False,
        "is_us": False,
    }


def test_get_market_info_hk():
    info = StockUtils.get_market_info("0700.HK")
    assert info["market"] == "hong_kong"
    assert info["market_name"] == "港股"
    assert info["is_hk"] is True
    assert info["is_china"] is False
    assert info["currency_name"] == "港币"
    assert info["data_source"] == "yahoo_finance"


def test_get_market_info_us():
    info = StockUtils.get_market_info("AAPL")
    assert info["market"] == "us"
    assert info["market_name"] == "美股"
    assert info["is_us"] is True
    assert info["currency_symbol"] == "$"


def test_get_market_info_keeps_original_ticker_case():
    """返回的市场信息中 ticker 保留传入的原始值"""
    info = StockUtils.get_market_info("aapl")
    assert info["ticker"] == "aapl"
    assert info["market"] == "us"


def test_get_stock_market_info_convenience():
    """模块级便捷函数 get_stock_market_info 与类方法结果一致"""
    assert get_stock_market_info("600000") == StockUtils.get_market_info("600000")
