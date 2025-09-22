#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/1/5 19:00
Desc: 新浪财经-基金行情
https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf
"""

import pandas as pd
import py_mini_racer
import requests

from akshare.stock.cons import hk_js_decode
from akshare.utils import demjson


def fund_etf_category_sina(symbol: str = "LOF基金") -> pd.DataFrame:
    """
    新浪财经-基金列表
    https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf
    :param symbol: choice of {"封闭式基金", "ETF基金", "LOF基金"}
    :type symbol: str
    :return: 指定 symbol 的基金列表
    :rtype: pandas.DataFrame
    """
    fund_map = {
        "封闭式基金": "close_fund",
        "ETF基金": "etf_hq_fund",
        "LOF基金": "lof_hq_fund",
    }
    url = (
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/jsonp.php/"
        "IO.XSRV2.CallbackList['da_yPT46_Ll7K6WD']/Market_Center.getHQNodeDataSimple"
    )
    params = {
        "page": "1",
        "num": "5000",
        "sort": "symbol",
        "asc": "0",
        "node": fund_map[symbol],
        "[object HTMLDivElement]": "qvvne",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("([") + 1 : -2])
    temp_df = pd.DataFrame(data_json)
    if symbol == "封闭式基金":
        temp_df.columns = [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "买入",
            "卖出",
            "昨收",
            "今开",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "_",
            "_",
        ]
    else:
        temp_df.columns = [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "买入",
            "卖出",
            "昨收",
            "今开",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "_",
            "_",
            "_",
            "_",
        ]
    temp_df = temp_df[
        [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "买入",
            "卖出",
            "昨收",
            "今开",
            "最高",
            "最低",
            "成交量",
            "成交额",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["买入"] = pd.to_numeric(temp_df["买入"], errors="coerce")
    temp_df["卖出"] = pd.to_numeric(temp_df["卖出"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


def fund_etf_hist_sina(symbol: str = "sh510050") -> pd.DataFrame:
    """
    新浪财经-基金-ETF 基金-日行情数据
    https://finance.sina.com.cn/fund/quotes/159996/bc.shtml
    :param symbol: 基金名称, 可以通过 ak.fund_etf_category_sina() 函数获取
    :type symbol: str
    :return: 日行情数据
    :rtype: pandas.DataFrame
    """
    url = f"https://finance.sina.com.cn/realstock/company/{symbol}/hisdata/klc_kl.js"
    r = requests.get(url)
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call(
        "d", r.text.split("=")[1].split(";")[0].replace('"', "")
    )  # 执行js解密代码
    temp_df = pd.DataFrame(dict_list)
    if temp_df.empty:  # 处理获取数据为空的问题
        return pd.DataFrame()
    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.tz_localize(
        None
    )
    temp_df["open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["volume"] = pd.to_numeric(temp_df["volume"], errors="coerce")

    # 转换日期列为日期类型
    temp_df["date"] = temp_df["date"].dt.date
    temp_df = temp_df.sort_values(by="date", ascending=True)
    return temp_df


def fund_etf_dividend_sina(symbol: str = "sh510050") -> pd.DataFrame:
    """
    新浪财经-基金-ETF 基金-累计分红
    https://finance.sina.com.cn/fund/quotes/510050/bc.shtml
    :param symbol: 基金名称, 可以通过 ak.fund_etf_category_sina() 函数获取
    :type symbol: str
    :return: 累计分红
    :rtype: pandas.DataFrame
    """
    # 构建复权数据URL
    factor_url = f"https://finance.sina.com.cn/realstock/company/{symbol}/hfq.js"
    r = requests.get(factor_url)
    text = r.text
    if text.startswith("var"):
        json_str = text.split("=")[1].strip().rsplit("}", maxsplit=1)[0].strip()
        data = eval(json_str + "}")  # 这里使用eval而不是json.loads因为数据格式特殊

        if isinstance(data, dict) and "data" in data:
            df = pd.DataFrame(data["data"])
            # 重命名列
            df.columns = ["date", "f", "s", "u"] if len(df.columns) == 4 else df.columns
            # 移除1900-01-01的数据
            df = df[df["date"] != "1900-01-01"]
            # 转换日期
            df["date"] = pd.to_datetime(df["date"])
            # 转换数值类型
            df[["f", "s", "u"]] = df[["f", "s", "u"]].astype(float)
            # 按日期排序
            df = df.sort_values("date", ascending=True, ignore_index=True)
            temp_df = df[["date", "u"]].copy()
            temp_df.columns = ["日期", "累计分红"]
            temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
            return temp_df


if __name__ == "__main__":
    fund_etf_category_sina_df = fund_etf_category_sina(symbol="封闭式基金")
    print(fund_etf_category_sina_df)

    fund_etf_category_sina_df = fund_etf_category_sina(symbol="ETF基金")
    print(fund_etf_category_sina_df)

    fund_etf_category_sina_df = fund_etf_category_sina(symbol="LOF基金")
    print(fund_etf_category_sina_df)

    fund_etf_hist_sina_df = fund_etf_hist_sina(symbol="sh510050")
    print(fund_etf_hist_sina_df)

    fund_etf_hist_sina_df = fund_etf_hist_sina(symbol="sh510300")
    print(fund_etf_hist_sina_df)

    fund_etf_dividend_sina_df = fund_etf_dividend_sina(symbol="sh510050")
    print(fund_etf_dividend_sina_df)
