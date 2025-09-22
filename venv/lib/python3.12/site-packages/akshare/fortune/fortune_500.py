#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/8/4 17:22
Desc: 历年世界 500 强榜单数据
https://www.fortunechina.com/fortune500/index.htm
特殊情况说明：
2010年由于网页端没有公布公司所属的国家, 故 2010 年数据没有国家这列
"""

from functools import lru_cache
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


@lru_cache()
def _fortune_rank_year_url_map() -> dict:
    """
    年份和网址映射
    https://www.fortunechina.com/fortune500/index.htm
    :return: 年份和网址映射
    :rtype: dict
    """
    url = "https://www.fortunechina.com/fortune500/index.htm"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="lxml")
    url_2023 = "https://www.fortunechina.com/fortune500/c/2023-08/02/content_436874.htm"
    node_list = soup.find_all(name="div", attrs={"class": "swiper-slide"})
    url_list = [item.find("a")["href"] for item in node_list]
    year_list = [item.find("a").text for item in node_list]
    year_url_map = dict(zip(year_list, url_list))
    year_url_map["2023"] = url_2023
    return year_url_map


def fortune_rank(year: str = "2015") -> pd.DataFrame:
    """
    财富 500 强公司从 1996 年开始的排行榜
    https://www.fortunechina.com/fortune500/index.htm
    :param year: str 年份
    :return: pandas.DataFrame
    """
    year_url_map = _fortune_rank_year_url_map()
    url = year_url_map[year]
    r = requests.get(url)
    r.encoding = "utf-8"
    if int(year) < 2007:
        df = pd.read_html(StringIO(r.text))[0].iloc[1:-1,]
        df.columns = pd.read_html(StringIO(r.text))[0].iloc[0, :].tolist()
        return df
    elif 2006 < int(year) < 2010:
        df = pd.read_html(StringIO(r.text))[0].iloc[1:,]
        df.columns = pd.read_html(StringIO(r.text))[0].iloc[0, :].tolist()
        for page in tqdm(range(2, 11), leave=False):
            # page =2
            r = requests.get(url.rsplit(".", maxsplit=1)[0] + "_" + str(page) + ".htm")
            r.encoding = "utf-8"
            temp_df = pd.read_html(StringIO(r.text))[0].iloc[1:,]
            temp_df.columns = pd.read_html(StringIO(r.text))[0].iloc[0, :].tolist()
            df = pd.concat(objs=[df, temp_df], ignore_index=True)
        return df
    else:
        df = pd.read_html(StringIO(r.text))[0]
        return df


if __name__ == "__main__":
    fortune_rank_df = fortune_rank(year="2023")  # 2010 不一样
    print(fortune_rank_df)

    fortune_rank_df = fortune_rank(year="2022")  # 2010 不一样
    print(fortune_rank_df)

    fortune_rank_df = fortune_rank(year="2008")  # 2010 不一样
    print(fortune_rank_df)

    fortune_rank_df = fortune_rank(year="2008")  # 2010 不一样
    print(fortune_rank_df)

    fortune_rank_df = fortune_rank(year="2009")  # 2010 不一样
    print(fortune_rank_df)

    for item in range(1996, 2008):
        print(item)
        fortune_rank_df = fortune_rank(year=str(item))  # 2010 不一样
        print(fortune_rank_df)

    for item in range(2010, 2023):
        print(item)
        fortune_rank_df = fortune_rank(year=str(item))  # 2010 不一样
        print(fortune_rank_df)
