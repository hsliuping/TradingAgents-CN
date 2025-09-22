#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/1/7 13:40
Desc: 新浪财经-机构推荐池
http://stock.finance.sina.com.cn/stock/go.php/vIR_RatingNewest/index.phtml
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup


def stock_institute_recommend(symbol: str = "投资评级选股") -> pd.DataFrame:
    """
    新浪财经-机构推荐池-最新投资评级
    http://stock.finance.sina.com.cn/stock/go.php/vIR_RatingNewest/index.phtml
    :param symbol: choice of {'最新投资评级', '上调评级股票', '下调评级股票', '股票综合评级', '首次评级股票', '目标涨幅排名', '机构关注度', '行业关注度', '投资评级选股'}
    :type symbol: str
    :return: 最新投资评级数据
    :rtype: pandas.DataFrame
    """
    url = "http://stock.finance.sina.com.cn/stock/go.php/vIR_RatingNewest/index.phtml"
    params = {
        "num": "40",
        "p": "1",
    }
    r = requests.get(url, params=params)
    soup = BeautifulSoup(r.text, "lxml")
    indicator_map = {
        item.find("a").text: item.find("a")["href"]
        for item in soup.find(attrs={"id": "leftMenu"}).find_all("dd")[1].find_all("li")
    }
    url = indicator_map[symbol]
    params = {
        "num": "10000",
        "p": "1",
    }
    r = requests.get(url, params=params)
    if symbol == "股票综合评级":
        temp_df = pd.read_html(r.text, header=0)[0].iloc[:, :9]
        temp_df["股票代码"] = temp_df["股票代码"].astype(str).str.zfill(6)
        temp_df = temp_df.rename(columns={"综合评级↓": "综合评级"})
        return temp_df
    if symbol == "首次评级股票":
        temp_df = pd.read_html(r.text, header=0)[0].iloc[:, :8]
        temp_df["股票代码"] = temp_df["股票代码"].astype(str).str.zfill(6)
        temp_df = temp_df.rename(columns={"评级日期↓": "评级日期"})
        return temp_df
    if symbol == "目标涨幅排名":
        temp_df = pd.read_html(r.text, header=0)[0].iloc[:, :7]
        temp_df["股票代码"] = temp_df["股票代码"].astype(str).str.zfill(6)
        temp_df = temp_df.rename(columns={"平均目标涨幅↓": "平均目标涨幅"})
        return temp_df
    if symbol == "机构关注度":
        temp_df = pd.read_html(r.text, header=0)[0].iloc[:, :11]
        temp_df["股票代码"] = temp_df["股票代码"].astype(str).str.zfill(6)
        temp_df = temp_df.rename(columns={"关注度↓": "关注度"})
        return temp_df
    if symbol == "行业关注度":
        temp_df = pd.read_html(r.text, header=0)[0].iloc[:, :11]
        temp_df = temp_df.rename(columns={"关注度↓": "关注度"})
        return temp_df
    if symbol == "投资评级选股":
        temp_df = pd.read_html(r.text, header=0)[0].iloc[:, :9]
        temp_df["股票代码"] = temp_df["股票代码"].astype(str).str.zfill(6)
        del temp_df["评级明细"]
        temp_df = temp_df.rename(columns={"评级日期↓": "评级日期"})
        return temp_df
    temp_df = pd.read_html(r.text, header=0)[0].iloc[:, :8]
    temp_df["股票代码"] = temp_df["股票代码"].astype(str).str.zfill(6)
    temp_df = temp_df.rename(columns={"评级日期↓": "评级日期"})
    return temp_df


def stock_institute_recommend_detail(symbol: str = "000001") -> pd.DataFrame:
    """
    新浪财经-机构推荐池-股票评级记录
    http://stock.finance.sina.com.cn/stock/go.php/vIR_StockSearch/key/sz000001.phtml
    :param symbol: 股票代码
    :type symbol: str
    :return: 具体股票的股票评级记录
    :rtype: pandas.DataFrame
    """
    url = f"http://stock.finance.sina.com.cn/stock/go.php/vIR_StockSearch/key/{symbol}.phtml"
    params = {
        "num": "5000",
        "p": "1",
    }
    r = requests.get(url, params=params)
    temp_df = pd.read_html(r.text, header=0)[0].iloc[:, :8]
    temp_df["股票代码"] = temp_df["股票代码"].astype(str).str.zfill(6)
    temp_df = temp_df.rename(columns={"评级日期↓": "评级日期"})
    return temp_df


if __name__ == "__main__":
    for item in [
        "最新投资评级",
        "上调评级股票",
        "下调评级股票",
        "股票综合评级",
        "首次评级股票",
        "目标涨幅排名",
        "机构关注度",
        "行业关注度",
        "投资评级选股",
    ]:
        stock_institute_recommend_df = stock_institute_recommend(symbol=item)
        print(stock_institute_recommend_df)

    stock_institute_recommend_detail_df = stock_institute_recommend_detail(
        symbol="002709"
    )
    print(stock_institute_recommend_detail_df)
