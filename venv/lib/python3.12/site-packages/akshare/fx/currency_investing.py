#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/26 15:33
Desc: 英为财情-外汇-货币对历史数据
https://cn.investing.com/currencies/
https://cn.investing.com/currencies/eur-usd-historical-data
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
from akshare.utils.tqdm import get_tqdm


def currency_pair_map(symbol: str = "美元") -> pd.DataFrame:
    """
    指定货币的所有可获取货币对的数据
    https://cn.investing.com/currencies/cny-jmd
    :param symbol: 指定货币
    :type symbol: str
    :return: 指定货币的所有可获取货币对的数据
    :rtype: pandas.DataFrame
    """
    region_code = []
    region_name = []
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        # "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "cn.investing.com",
        "Pragma": "no-cache",
        "Referer": "https://cn.investing.com/currencies/single-currency-crosses",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/79.0.3945.130 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }

    def has_data_sml_id_but_no_id(tag):
        return tag.has_attr("data-sml-id") and not tag.has_attr("title")

    tqdm = get_tqdm()
    for region_id in tqdm(["4", "1", "8", "7", "6"], leave=False):
        url = "https://cn.investing.com/currencies/Service/region"
        params = {"region_ID": region_id, "currency_ID": "false"}

        r = requests.get(url, params=params, headers=headers)
        soup = BeautifulSoup(r.text, features="lxml")
        region_code.extend(
            [
                item["continentid"] + "-" + region_id
                for item in soup.find_all(has_data_sml_id_but_no_id)
            ]
        )
        region_name.extend(
            [item.find("i").text for item in soup.find_all(has_data_sml_id_but_no_id)]
        )

    name_id_map = dict(zip(region_name, region_code))
    url = "https://cn.investing.com/currencies/Service/currency"
    params = {
        "region_ID": name_id_map[symbol].split("-")[1],
        "currency_ID": name_id_map[symbol].split("-")[0],
    }
    r = requests.get(url, params=params, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")

    temp_code = [item["href"].split("/")[-1] for item in soup.find_all("a")]  # need
    temp_name = [item["title"].replace(" ", "-") for item in soup.find_all("a")]
    temp_df = pd.DataFrame(data=[temp_name, temp_code], index=["name", "code"]).T
    return temp_df


if __name__ == "__main__":
    currency_pair_map_df = currency_pair_map(symbol="人民币")
    print(currency_pair_map_df)
