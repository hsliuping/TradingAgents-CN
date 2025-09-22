#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/7/17 18:00
Desc: 99 期货网-大宗商品库存数据
https://www.99qh.com/
"""

import json
from datetime import datetime
from functools import lru_cache

import pandas as pd
import requests
from bs4 import BeautifulSoup


@lru_cache(maxsize=32)
def __get_99_symbol_map() -> pd.DataFrame:
    """
    99 期货网-品种代码对照表
    https://www.99qh.com/data/stockIn?productId=12
    :return: 品种代码对照表
    :rtype: pandas.DataFrame
    """
    url = "https://www.99qh.com/data/stockIn"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="lxml")
    raw_data = soup.find(attrs={"id": "__NEXT_DATA__"}).text
    data_json = json.loads(raw_data)
    df_list = []
    for i, item in enumerate(
        data_json["props"]["pageProps"]["data"]["varietyListData"]
    ):
        temp_df = pd.DataFrame(
            data_json["props"]["pageProps"]["data"]["varietyListData"][i]["productList"]
        )
        df_list.append(temp_df)

    big_df = pd.concat(df_list, ignore_index=True)
    return big_df


def futures_inventory_99(symbol: str = "豆一") -> pd.DataFrame:
    """
    99 期货网-大宗商品库存数据
    https://www.99qh.com/data/stockIn?productId=12
    :param symbol: 交易所对应的具体品种; 如：大连商品交易所的 豆一
    :type symbol: str
    :return: 大宗商品库存数据
    :rtype: pandas.DataFrame
    """
    temp_df = __get_99_symbol_map()
    symbol_name_map = dict(zip(temp_df["name"], temp_df["productId"]))
    symbol_code_map = dict(zip(temp_df["code"], temp_df["productId"]))
    if symbol in symbol_name_map:  # 如果输入的是中文名称
        product_id = symbol_name_map[symbol]
    elif symbol in symbol_code_map:  # 如果输入的是代码
        product_id = symbol_code_map[symbol]
    else:
        raise ValueError(f"未找到品种 {symbol} 对应的编号")

    url = "https://centerapi.fx168api.com/app/qh/api/stock/trend"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "_pcc": "LXbAQMr0TYT8dDsJKEEQE4yFSLKOVQ1LguCImNzNBQXu2vyAq7MN34kKtBhtp7VsCjm1x5oobzlyd4kC9PDaOJnbk"
                "GQeS0PLhhvjbUlysSk3LOnuqhxMzlls9eEspnnu3iRJbtD4dAcGSoUAUf/AiRWZvysT/aVbkRzQj9lv5ck=",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/58.0.3029.110 Safari/537.3",
        "referer": "https://www.99qh.com",
        "origin": "https://www.99qh.com",
    }
    params = {
        "productId": product_id,
        "type": "1",
        "pageNo": "1",
        "pageSize": "5000",
        "startDate": "",
        "endDate": f"{datetime.now().date().isoformat()}",
        "appCategory": "web",
    }
    r = requests.get(url, params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["list"])
    temp_df.columns = ["日期", "收盘价", "库存"]
    temp_df.sort_values(by=["日期"], ignore_index=True, inplace=True)
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["收盘价"] = pd.to_numeric(temp_df["收盘价"], errors="coerce")
    temp_df["库存"] = pd.to_numeric(temp_df["库存"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    futures_inventory_99_df = futures_inventory_99(symbol="豆一")
    print(futures_inventory_99_df)
