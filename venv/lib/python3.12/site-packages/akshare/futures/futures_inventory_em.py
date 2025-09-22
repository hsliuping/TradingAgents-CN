#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/5 17:30
Desc: 东方财富网-数据中心-期货库存数据
https://data.eastmoney.com/ifdata/kcsj.html
"""

import pandas as pd
import requests
from akshare.futures.cons import futures_inventory_em_symbol_dict


def futures_inventory_em(symbol: str = "a") -> pd.DataFrame:
    """
    东方财富网-数据中心-期货库存数据
    https://data.eastmoney.com/ifdata/kcsj.html
    :param symbol: 支持品种代码和中文名称，中文名称参见：https://data.eastmoney.com/ifdata/kcsj.html
    :type symbol: str
    :return: 指定品种的库存数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_FUTU_POSITIONCODE",
        "columns": "TRADE_MARKET_CODE,TRADE_CODE,TRADE_TYPE",
        "filter": '(IS_MAINCODE="1")',
        "pageNumber": "1",
        "pageSize": "500",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    symbol_dict = dict(zip(temp_df["TRADE_TYPE"], temp_df["TRADE_CODE"]))
    if symbol in symbol_dict.keys():
        product_id = symbol_dict[symbol]
    elif symbol in futures_inventory_em_symbol_dict.keys():  # 如果输入的是代码
        product_id = futures_inventory_em_symbol_dict[symbol]
    else:
        raise ValueError(f"请输入正确的 symbol, 可选项为: {symbol_dict}")
    params = {
        "reportName": "RPT_FUTU_STOCKDATA",
        "columns": "SECURITY_CODE,TRADE_DATE,ON_WARRANT_NUM,ADDCHANGE",
        "filter": f"""(SECURITY_CODE="{product_id}")(TRADE_DATE>='2020-10-28')""",
        "pageNumber": "1",
        "pageSize": "500",
        "sortTypes": "-1",
        "sortColumns": "TRADE_DATE",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = ["-", "日期", "库存", "增减"]
    temp_df = temp_df[["日期", "库存", "增减"]]
    temp_df.sort_values(["日期"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    temp_df["库存"] = pd.to_numeric(temp_df["库存"], errors="coerce")
    temp_df["增减"] = pd.to_numeric(temp_df["增减"], errors="coerce")
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    return temp_df


if __name__ == "__main__":
    futures_inventory_em_df = futures_inventory_em(symbol="a")
    print(futures_inventory_em_df)
