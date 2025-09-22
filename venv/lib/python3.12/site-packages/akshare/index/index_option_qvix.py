# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2023/10/19 16:00
Desc: 50 ETF 期权波动率指数 QVIX
300 ETF 期权波动率指数 QVIX
http://1.optbbs.com/s/vix.shtml?50ETF
http://1.optbbs.com/s/vix.shtml?300ETF
"""

import pandas as pd
from functools import lru_cache


@lru_cache
def __get_optbbs_daily() -> pd.DataFrame:
    """
    读取原始数据
    http://1.optbbs.com/d/csv/d/k.csv
    :return: 原始数据
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/k.csv"
    temp_df = pd.read_csv(url, encoding="gbk")
    return temp_df


def index_option_50etf_qvix() -> pd.DataFrame:
    """
    50ETF 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?50ETF
    :return: 50ETF 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, :5]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_50etf_min_qvix() -> pd.DataFrame:
    """
    50 ETF 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?50ETF
    :return: 50 ETF 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vix50.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


def index_option_300etf_qvix() -> pd.DataFrame:
    """
    300 ETF 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?300ETF
    :return: 300 ETF 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, [0, 9, 10, 11, 12]]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_300etf_min_qvix() -> pd.DataFrame:
    """
    300 ETF 期权波动率指数 QVIX-分时
    http://1.optbbs.com/s/vix.shtml?300ETF
    :return: 300 ETF 期权波动率指数 QVIX-分时
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vix300.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


def index_option_500etf_qvix() -> pd.DataFrame:
    """
    500 ETF 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?500ETF
    :return: 500 ETF 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, [0, 67, 68, 69, 70]]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_500etf_min_qvix() -> pd.DataFrame:
    """
    500 ETF 期权波动率指数 QVIX-分时
    http://1.optbbs.com/s/vix.shtml?500ETF
    :return: 500 ETF 期权波动率指数 QVIX-分时
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vix500.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


def index_option_cyb_qvix() -> pd.DataFrame:
    """
    创业板 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?CYB
    :return: 创业板 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, [0, 71, 72, 73, 74]]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_cyb_min_qvix() -> pd.DataFrame:
    """
    创业板 期权波动率指数 QVIX-分时
    http://1.optbbs.com/s/vix.shtml?CYB
    :return: 创业板 期权波动率指数 QVIX-分时
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vixcyb.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


def index_option_kcb_qvix() -> pd.DataFrame:
    """
    科创板 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?KCB
    :return: 科创板 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, [0, 83, 84, 85, 86]]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_kcb_min_qvix() -> pd.DataFrame:
    """
    科创板 期权波动率指数 QVIX-分时
    http://1.optbbs.com/s/vix.shtml?KCB
    :return: 科创板 期权波动率指数 QVIX-分时
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vixkcb.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


def index_option_100etf_qvix() -> pd.DataFrame:
    """
    深证100ETF 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?100ETF
    :return: 深证100ETF 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, [0, 75, 76, 77, 78]]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_100etf_min_qvix() -> pd.DataFrame:
    """
    深证100ETF 期权波动率指数 QVIX-分时
    http://1.optbbs.com/s/vix.shtml?100ETF
    :return: 深证100ETF 期权波动率指数 QVIX-分时
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vix100.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


def index_option_300index_qvix() -> pd.DataFrame:
    """
    中证300股指 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?Index
    :return: 中证300股指 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, [0, 17, 18, 19, 20]]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_300index_min_qvix() -> pd.DataFrame:
    """
    中证300股指 期权波动率指数 QVIX-分时
    http://1.optbbs.com/s/vix.shtml?Index
    :return: 中证300股指 期权波动率指数 QVIX-分时
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vixindex.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


def index_option_1000index_qvix() -> pd.DataFrame:
    """
    中证1000股指 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?Index1000
    :return: 中证1000股指 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, [0, 25, 26, 27, 28]]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_1000index_min_qvix() -> pd.DataFrame:
    """
    中证1000股指 期权波动率指数 QVIX-分时
    http://1.optbbs.com/s/vix.shtml?Index1000
    :return: 中证1000股指 期权波动率指数 QVIX-分时
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vixindex1000.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


def index_option_50index_qvix() -> pd.DataFrame:
    """
    上证50股指 期权波动率指数 QVIX
    http://1.optbbs.com/s/vix.shtml?50index
    :return: 上证50股指 期权波动率指数 QVIX
    :rtype: pandas.DataFrame
    """
    temp_df = __get_optbbs_daily().iloc[:, [0, 79, 80, 81, 82]]
    temp_df.columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
    ]
    temp_df.loc[:, "date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df.loc[:, "open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df.loc[:, "high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df.loc[:, "low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df.loc[:, "close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    return temp_df


def index_option_50index_min_qvix() -> pd.DataFrame:
    """
    上证50股指 期权波动率指数 QVIX-分时
    http://1.optbbs.com/s/vix.shtml?50index
    :return: 上证50股指 期权波动率指数 QVIX-分时
    :rtype: pandas.DataFrame
    """
    url = "http://1.optbbs.com/d/csv/d/vix50index.csv"
    temp_df = pd.read_csv(url).iloc[:, :2]
    temp_df.columns = [
        "time",
        "qvix",
    ]
    temp_df.loc[:, "qvix"] = pd.to_numeric(temp_df["qvix"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    index_option_50etf_qvix_df = index_option_50etf_qvix()
    print(index_option_50etf_qvix_df)

    index_option_50etf_min_qvix_df = index_option_50etf_min_qvix()
    print(index_option_50etf_min_qvix_df)

    index_option_300etf_qvix_df = index_option_300etf_qvix()
    print(index_option_300etf_qvix_df)

    index_option_300etf_min_qvix_df = index_option_300etf_min_qvix()
    print(index_option_300etf_min_qvix_df)

    index_option_500etf_qvix_df = index_option_500etf_qvix()
    print(index_option_500etf_qvix_df)

    index_option_500etf_min_qvix_df = index_option_500etf_min_qvix()
    print(index_option_500etf_min_qvix_df)

    index_option_cyb_qvix_df = index_option_cyb_qvix()
    print(index_option_cyb_qvix_df)

    index_option_cyb_min_qvix_df = index_option_cyb_min_qvix()
    print(index_option_cyb_min_qvix_df)

    index_option_kcb_qvix_df = index_option_kcb_qvix()
    print(index_option_kcb_qvix_df)

    index_option_kcb_min_qvix_df = index_option_kcb_min_qvix()
    print(index_option_kcb_min_qvix_df)

    index_option_100etf_qvix_df = index_option_100etf_qvix()
    print(index_option_100etf_qvix_df)

    index_option_100etf_min_qvix_df = index_option_100etf_min_qvix()
    print(index_option_100etf_min_qvix_df)

    index_option_300index_qvix_df = index_option_300index_qvix()
    print(index_option_300index_qvix_df)

    index_option_300index_min_qvix_df = index_option_300index_min_qvix()
    print(index_option_300index_min_qvix_df)

    index_option_1000index_qvix_df = index_option_1000index_qvix()
    print(index_option_1000index_qvix_df)

    index_option_1000index_min_qvix_df = index_option_1000index_min_qvix()
    print(index_option_1000index_min_qvix_df)

    index_option_50index_qvix_df = index_option_50index_qvix()
    print(index_option_50index_qvix_df)

    index_option_50index_min_qvix_df = index_option_50index_min_qvix()
    print(index_option_50index_min_qvix_df)
