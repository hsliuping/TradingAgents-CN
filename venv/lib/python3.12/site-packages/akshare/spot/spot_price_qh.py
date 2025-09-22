# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/5/16 20:00
Desc: 99 期货-数据-期现-现货走势
https://www.99qh.com/data/spotTrend
"""

import json

import pandas as pd
import requests
from bs4 import BeautifulSoup


def __get_item_of_spot_price_qh() -> pd.DataFrame:
    """
    99 期货-数据-期现-品种和 ID 对应表
    https://www.99qh.com/data/spotTrend
    :return: 品种和 ID 对应表
    :rtype: str
    """
    url = "https://www.99qh.com/data/spotTrend"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="lxml")
    data_text = soup.find(name="script", attrs={"id": "__NEXT_DATA__"}).text
    data_json = json.loads(data_text)
    big_list = []
    for item in data_json["props"]["pageProps"]["data"]["varietyListData"]:
        big_list.extend(item["productList"])
    temp_df = pd.DataFrame(big_list)
    temp_df = temp_df[["qhExchangeName", "name", "productId"]]
    return temp_df


def __get_token_of_spot_price_qh() -> str:
    """
    99 期货-数据-期现-token
    https://www.99qh.com/data/spotTrend
    :return: token
    :rtype: str
    """
    url = "https://centerapi.fx168api.com/app/common/v.js"
    headers = {
        "Origin": "https://www.99qh.com",
        "Referer": "https://www.99qh.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    token = r.headers["_pcc"]
    return token


def spot_price_table_qh() -> pd.DataFrame:
    """
    99 期货-数据-期现-交易所与品种对照表
    https://www.99qh.com/data/spotTrend
    :return: 交易所与品种对照表
    :rtype: pandas.DataFrame
    """
    temp_df = __get_item_of_spot_price_qh()
    temp_df.rename(
        columns={
            "qhExchangeName": "交易所名称",
            "name": "品种名称",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "交易所名称",
            "品种名称",
        ]
    ]
    return temp_df


def spot_price_qh(symbol: str = "螺纹钢") -> pd.DataFrame:
    """
    99 期货-数据-期现-现货走势
    https://www.99qh.com/data/spotTrend
    :param symbol: 品种名称
    :type symbol: str
    :return: 现货走势
    :rtype: pandas.DataFrame
    """
    inner_df = __get_item_of_spot_price_qh()
    symbol_map = dict(zip(inner_df["name"], inner_df["productId"]))
    url = "https://centerapi.fx168api.com/app/qh/api/spot/trend"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36",
        "_pcc": __get_token_of_spot_price_qh(),
        "Origin": "https://www.99qh.com",
        "Referer": "https://www.99qh.com",
    }
    params = {
        "productId": symbol_map[symbol],
        "pageNo": "1",
        "pageSize": "50000",
        "startDate": "",
        "endDate": "2050-01-01",
        "appCategory": "web",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["list"])
    temp_df.rename(
        columns={"date": "日期", "fp": "期货收盘价", "sp": "现货价格"}, inplace=True
    )
    temp_df.sort_values(by=["日期"], inplace=True, ignore_index=True)
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["期货收盘价"] = pd.to_numeric(temp_df["期货收盘价"], errors="coerce")
    temp_df["现货价格"] = pd.to_numeric(temp_df["现货价格"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    spot_price_qh_df = spot_price_qh(symbol="螺纹钢")
    print(spot_price_qh_df)
