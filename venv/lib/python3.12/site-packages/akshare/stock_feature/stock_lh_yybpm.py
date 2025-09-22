#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/6 20:30
Desc: 同花顺-数据中心-营业部排名
https://data.10jqka.com.cn/market/longhu/
"""

from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils.tqdm import get_tqdm
from akshare.utils.cons import headers


def stock_lh_yyb_most() -> pd.DataFrame:
    """
    同花顺-数据中心-营业部排名-上榜次数最多
    https://data.10jqka.com.cn/market/longhu/
    :return: 上榜次数最多
    :rtype: pandas.DataFrame
    """
    url = "https://data.10jqka.com.cn/ifmarket/lhbyyb/type/1/tab/sbcs/field/sbcs/sort/desc/page/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    page_str = soup.find(name="span", attrs={"class": "page_info"}).text
    total_page = int(page_str.split("/")[1]) + 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page), leave=False):
        url = f"https://data.10jqka.com.cn/ifmarket/lhbyyb/type/1/tab/sbcs/field/sbcs/sort/desc/page/{page}/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def stock_lh_yyb_capital() -> pd.DataFrame:
    """
    同花顺-数据中心-营业部排名-资金实力最强
    https://data.10jqka.com.cn/market/longhu/
    :return: 资金实力最强
    :rtype: pandas.DataFrame
    """
    url = "https://data.10jqka.com.cn/ifmarket/lhbyyb/type/1/tab/zjsl/field/zgczje/sort/desc/page/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    page_str = soup.find(name="span", attrs={"class": "page_info"}).text
    total_page = int(page_str.split("/")[1]) + 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page), leave=False):
        url = f"https://data.10jqka.com.cn/ifmarket/lhbyyb/type/1/tab/zjsl/field/zgczje/sort/desc/page/{page}/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def stock_lh_yyb_control() -> pd.DataFrame:
    """
    同花顺-数据中心-营业部排名-抱团操作实力
    https://data.10jqka.com.cn/market/longhu/
    :return: 抱团操作实力
    :rtype: pandas.DataFrame
    """
    url = "https://data.10jqka.com.cn/ifmarket/lhbyyb/type/1/tab/btcz/field/xsjs/sort/desc/page/1/"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    page_str = soup.find(name="span", attrs={"class": "page_info"}).text
    total_page = int(page_str.split("/")[1]) + 1
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page), leave=False):
        url = f"https://data.10jqka.com.cn/ifmarket/lhbyyb/type/1/tab/btcz/field/xsjs/sort/desc/page/{page}/"
        r = requests.get(url, headers=headers)
        temp_df = pd.read_html(StringIO(r.text))[0]
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


if __name__ == "__main__":
    stock_lh_yyb_most_df = stock_lh_yyb_most()
    print(stock_lh_yyb_most_df)

    stock_lh_yyb_capital_df = stock_lh_yyb_capital()
    print(stock_lh_yyb_capital_df)

    stock_lh_yyb_control_df = stock_lh_yyb_control()
    print(stock_lh_yyb_control_df)
