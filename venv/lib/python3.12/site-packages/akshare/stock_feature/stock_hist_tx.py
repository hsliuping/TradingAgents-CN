#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/7/25 15:30
Desc: 腾讯证券-行情首页-沪深京A股
https://quote.eastmoney.com/
"""

import datetime

import pandas as pd
import requests

from akshare.index.index_stock_zh import get_tx_start_year
from akshare.utils import demjson
from akshare.utils.tqdm import get_tqdm


def stock_zh_a_hist_tx(
    symbol: str = "sz000001",
    start_date: str = "19000101",
    end_date: str = "20500101",
    adjust: str = "",
    timeout: float = None,
) -> pd.DataFrame:
    """
    腾讯证券-日频-股票历史数据
    https://gu.qq.com/sh000919/zs
    :param symbol: 带市场标识的股票或者指数代码
    :type symbol: str
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :param adjust: choice of {"qfq": "前复权", "hfq": "后复权", "": "不复权"}
    :type adjust: str
    :param timeout: choice of None or a positive float number
    :type timeout: float
    :return: 前复权的股票和指数数据
    :rtype: pandas.DataFrame
    """
    init_start_date = get_tx_start_year(symbol=symbol)
    if int(start_date.replace("-", "")) < int(init_start_date.replace("-", "")):
        start_date = init_start_date
    url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
    range_start = int(start_date[:4])
    if int(end_date.split("-")[0]) > datetime.date.today().year:
        range_end = datetime.date.today().year + 1
    else:
        range_end = int(end_date.split("-")[0]) + 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for year in tqdm(range(range_start, range_end), leave=False):
        params = {
            "_var": f"kline_day{adjust}{year}",
            "param": f"{symbol},day,{year}-01-01,{year + 1}-12-31,640,{adjust}",
            "r": "0.8205512681390605",
        }
        r = requests.get(url, params=params, timeout=timeout)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("={") + 1 :])["data"][
            symbol
        ]
        if "day" in data_json.keys():
            temp_df = pd.DataFrame(data_json["day"])
        elif "hfqday" in data_json.keys():
            temp_df = pd.DataFrame(data_json["hfqday"])
        else:
            temp_df = pd.DataFrame(data_json["qfqday"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df = big_df.iloc[:, :6]
    big_df.columns = ["date", "open", "close", "high", "low", "amount"]
    big_df["date"] = pd.to_datetime(big_df["date"], errors="coerce").dt.date
    big_df["open"] = pd.to_numeric(big_df["open"], errors="coerce")
    big_df["close"] = pd.to_numeric(big_df["close"], errors="coerce")
    big_df["high"] = pd.to_numeric(big_df["high"], errors="coerce")
    big_df["low"] = pd.to_numeric(big_df["low"], errors="coerce")
    big_df["amount"] = pd.to_numeric(big_df["amount"], errors="coerce")
    big_df.drop_duplicates(inplace=True, ignore_index=True)
    big_df.index = pd.to_datetime(big_df["date"])
    big_df = big_df[start_date:end_date]
    big_df.reset_index(inplace=True, drop=True)
    return big_df


if __name__ == "__main__":
    stock_zh_a_hist_tx_df = stock_zh_a_hist_tx(
        symbol="sz000001", start_date="20200101", end_date="20231027", adjust="hfq"
    )
    print(stock_zh_a_hist_tx_df)
