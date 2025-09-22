#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/1/26 15:10
Desc: 福布斯中国-榜单
https://www.forbeschina.com/lists
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup


def forbes_rank(symbol: str = "2021福布斯中国创投人100") -> pd.DataFrame:
    """
    福布斯中国-榜单
    https://www.forbeschina.com/lists
    https://www.forbeschina.com/lists/1750
    :param symbol: choice of {"2020福布斯美国富豪榜", "2020福布斯新加坡富豪榜", "2020福布斯中国名人榜", *}
    :type symbol: str
    :return: 具体指标的榜单
    :rtype: pandas.DataFrame
    """
    url = "https://www.forbeschina.com/lists"
    r = requests.get(url, verify=False)
    soup = BeautifulSoup(r.text, "lxml")
    need_list = [
        item.find_all("a") for item in soup.find_all("div", attrs={"class": "col-sm-4"})
    ]
    all_list = []
    for item in need_list:
        all_list.extend(item)
    name_url_dict = dict(
        zip(
            [item.text.strip() for item in all_list],
            ["https://www.forbeschina.com" + item["href"] for item in all_list],
        )
    )
    r = requests.get(name_url_dict[symbol], verify=False)
    temp_df = pd.read_html(r.text)[0]
    return temp_df


if __name__ == "__main__":
    forbes_rank_df = forbes_rank(symbol="2021福布斯中国香港富豪榜")
    print(forbes_rank_df)
