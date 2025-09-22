# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/3/29 10:30
Desc: 同花顺-主营介绍
https://basic.10jqka.com.cn/new/000066/operate.html
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup


def stock_zyjs_ths(symbol: str = "000066") -> pd.DataFrame:
    """
    同花顺-主营介绍
    https://basic.10jqka.com.cn/new/000066/operate.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 主营介绍
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/new/{symbol}/operate.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/109.0.0.0 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
    r.encoding = "gb2312"
    soup = BeautifulSoup(r.text, "lxml")
    content_list = [
        item.text.strip()
        for item in soup.find("ul", attrs={"class": "main_intro_list"}).find_all("li")
    ]
    columns_list = []
    value_list = []
    for item in content_list:
        columns_list.append(item.split("：")[0])
        value_list.append(
            item.split("：", maxsplit=1)[1]
            .replace("\t", "")
            .replace("\n", "")
            .replace(" ", "")
            .strip()
        )

    temp_df = pd.DataFrame(value_list, index=columns_list).T
    temp_df.insert(0, "股票代码", symbol)
    return temp_df


if __name__ == "__main__":
    stock_zyjs_ths_df = stock_zyjs_ths(symbol="000066")
    print(stock_zyjs_ths_df)
