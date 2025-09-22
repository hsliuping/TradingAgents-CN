#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/18 16:25
Desc: 新加坡交易所-衍生品-历史数据-历史结算价格
https://www.sgx.com/zh-hans/research-education/derivatives
https://links.sgx.com/1.0.0/derivatives-daily/5888/FUTURE.zip
"""

import zipfile
from io import BytesIO
from io import StringIO

import pandas as pd
import requests


def __fetch_ftse_index_futu(date: str = "20231108") -> int:
    """
    新加坡交易所-日历计算
    https://wap.eastmoney.com/quote/stock/100.STI.html
    :param date: 交易日
    :type date: str
    :return: 日期计算结果
    :rtype: int
    """
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": "100.STI",
        "klt": "101",
        "fqt": "0",
        "lmt": "10000",
        "end": date,
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df.columns = [
        "date",
        "-",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "_",
        "-",
        "open",
        "close",
        "high",
        "low",
    ]
    num = temp_df["date"].index[-1] + 791
    return num


def futures_settlement_price_sgx(date: str = "20231107") -> pd.DataFrame:
    """
    新加坡交易所-衍生品-历史数据-历史结算价格
    https://www.sgx.com/zh-hans/research-education/derivatives
    :param date: 交易日
    :type date: str
    :return: 所有期货品种的在指定交易日的历史结算价格
    :rtype: pandas.DataFrame
    """
    num = __fetch_ftse_index_futu(date)
    url = f"https://links.sgx.com/1.0.0/derivatives-daily/{num}/FUTURE.zip"
    r = requests.get(url)
    with zipfile.ZipFile(BytesIO(r.content)) as file:
        with file.open(file.namelist()[0]) as my_file:
            data = my_file.read().decode()
            if file.namelist()[0].endswith("txt"):
                data_df = pd.read_table(StringIO(data))
            else:
                data_df = pd.read_csv(StringIO(data))
    return data_df


if __name__ == "__main__":
    futures_settlement_price_sgx_df = futures_settlement_price_sgx(date="20240110")
    print(futures_settlement_price_sgx_df)
