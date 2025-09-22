#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/9/26 18:00
Desc: Drewry 集装箱指数
https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry
https://infogram.com/world-container-index-1h17493095xl4zj
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils import demjson


def drewry_wci_index(symbol: str = "composite") -> pd.DataFrame:
    """
    Drewry 集装箱指数
    https://infogram.com/world-container-index-1h17493095xl4zj
    :param symbol: choice of {"composite", "shanghai-rotterdam", "rotterdam-shanghai", "shanghai-los angeles",
    "los angeles-shanghai", "shanghai-genoa", "new york-rotterdam", "rotterdam-new york"}
    :type symbol: str
    :return: Drewry 集装箱指数
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "composite": 0,
        "shanghai-rotterdam": 1,
        "rotterdam-shanghai": 2,
        "shanghai-los angeles": 3,
        "los angeles-shanghai": 4,
        "shanghai-genoa": 5,
        "new york-rotterdam": 6,
        "rotterdam-new york": 7,
    }
    url = "https://infogram.com/world-container-index-1h17493095xl4zj"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="lxml")
    data_text = soup.find_all("script")[-4].string.strip("window.infographicData=")[:-1]
    data_json = demjson.decode(data_text)
    data_json_need = data_json["elements"]["content"]["content"]["entities"][
        "7a55585f-3fb3-44e6-9b54-beea1cd20b4d"
    ]["data"][symbol_map[symbol]]
    date_list = [item[0]["value"] for item in data_json_need[1:]]
    try:
        value_list = [item[1]["value"] for item in data_json_need[1:]]
    except TypeError:
        value_list = [item[1]["value"] for item in data_json_need[1:-1]]
    temp_df = pd.DataFrame([date_list, value_list]).T
    temp_df.columns = ["date", "wci"]
    temp_df["date"] = pd.to_datetime(
        temp_df["date"], format="%d-%b-%y", errors="coerce"
    ).dt.date
    temp_df["wci"] = pd.to_numeric(temp_df["wci"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    drewry_wci_index_df = drewry_wci_index(symbol="composite")
    print(drewry_wci_index_df)

    drewry_wci_index_df = drewry_wci_index(symbol="shanghai-rotterdam")
    print(drewry_wci_index_df)

    drewry_wci_index_df = drewry_wci_index(symbol="rotterdam-shanghai")
    print(drewry_wci_index_df)

    drewry_wci_index_df = drewry_wci_index(symbol="shanghai-los angeles")
    print(drewry_wci_index_df)

    drewry_wci_index_df = drewry_wci_index(symbol="los angeles-shanghai")
    print(drewry_wci_index_df)

    drewry_wci_index_df = drewry_wci_index(symbol="shanghai-genoa")
    print(drewry_wci_index_df)

    drewry_wci_index_df = drewry_wci_index(symbol="new york-rotterdam")
    print(drewry_wci_index_df)

    drewry_wci_index_df = drewry_wci_index(symbol="rotterdam-new york")
    print(drewry_wci_index_df)
