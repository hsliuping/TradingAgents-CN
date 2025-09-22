#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/3/17 18:20
Desc: 新浪财经-美股指数行情
https://stock.finance.sina.com.cn/usstock/quotes/.IXIC.html
"""

import pandas as pd
import requests
import py_mini_racer

from akshare.stock.cons import (
    zh_js_decode,
)


def index_us_stock_sina(symbol: str = ".INX") -> pd.DataFrame:
    """
    新浪财经-美股指数行情
    https://stock.finance.sina.com.cn/usstock/quotes/.IXIC.html
    :param symbol: choice of {".IXIC", ".DJI", ".INX", ".NDX"}
    :type symbol: str
    :return: 美股指数行情
    :rtype: pandas.DataFrame
    """
    url = f"https://finance.sina.com.cn/staticdata/us/{symbol}"
    r = requests.get(url)
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(zh_js_decode)
    dict_list = js_code.call("d", r.text.split("=")[1].split(";")[0].replace('"', ""))
    temp_df = pd.DataFrame(dict_list)
    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df["open"] = pd.to_numeric(temp_df["open"], errors="coerce")
    temp_df["high"] = pd.to_numeric(temp_df["high"], errors="coerce")
    temp_df["low"] = pd.to_numeric(temp_df["low"], errors="coerce")
    temp_df["close"] = pd.to_numeric(temp_df["close"], errors="coerce")
    temp_df["volume"] = pd.to_numeric(temp_df["volume"], errors="coerce")
    temp_df["amount"] = pd.to_numeric(temp_df["amount"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    index_us_stock_sina_df = index_us_stock_sina(symbol=".INX")
    print(index_us_stock_sina_df)
