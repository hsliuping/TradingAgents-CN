#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/25 20:24
Desc: 市盈率, 市净率和股息率查询
https://www.legulegu.com/stocklist
https://www.legulegu.com/s/000001
"""

from datetime import datetime
from hashlib import md5

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils.cons import headers


def get_cookie_csrf(url: str = "") -> dict:
    """
    乐咕乐股-主板市盈率
    https://legulegu.com/stockdata/shanghaiPE
    :return: 指定市场的市盈率数据
    :rtype: pandas.DataFrame
    """
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    csrf_tag = soup.find(name="meta", attrs={"name": "_csrf"})
    csrf_token = csrf_tag.attrs["content"]
    headers.update({"X-CSRF-Token": csrf_token})
    return {"cookies": r.cookies, "headers": headers}


def get_token_lg() -> str:
    """
    生成乐咕的 token
    https://legulegu.com/s/002488
    :return: token
    :rtype: str
    """
    current_date_str = datetime.now().date().isoformat()
    obj = md5()
    obj.update(current_date_str.encode("utf-8"))
    token = obj.hexdigest()
    return token


def stock_a_indicator_lg(symbol: str = "000001") -> pd.DataFrame:
    """
    市盈率, 市净率, 股息率数据接口
    https://legulegu.com/stocklist
    :param symbol: 通过 ak.stock_a_indicator_lg(symbol="all") 来获取所有股票的代码
    :type symbol: str
    :return: 市盈率, 市净率, 股息率查询
    :rtype: pandas.DataFrame
    """
    if symbol == "all":
        url = "https://legulegu.com/stocklist"
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, features="lxml")
        node_list = soup.find_all(attrs={"class": "col-xs-6"})
        href_list = [item.find("a")["href"] for item in node_list]
        title_list = [item.find("a")["title"] for item in node_list]
        temp_df = pd.DataFrame([title_list, href_list]).T
        temp_df.columns = ["stock_name", "short_url"]
        temp_df["code"] = temp_df["short_url"].str.split("/", expand=True).iloc[:, -1]
        del temp_df["short_url"]
        temp_df = temp_df[["code", "stock_name"]]
        return temp_df
    else:
        url = "https://legulegu.com/api/s/base-info/"
        token = get_token_lg()
        params = {"token": token, "id": symbol}
        r = requests.post(
            url,
            params=params,
            **get_cookie_csrf(url="https://legulegu.com/"),
        )
        temp_json = r.json()
        temp_df = pd.DataFrame(
            temp_json["data"]["items"],
            columns=temp_json["data"]["fields"],
        )
        temp_df["trade_date"] = pd.to_datetime(temp_df["trade_date"]).dt.date
        temp_df[temp_df.columns[1:]] = temp_df[temp_df.columns[1:]].astype(float)
        temp_df.sort_values(by=["trade_date"], inplace=True, ignore_index=True)
        if len(set(temp_df["trade_date"])) <= 0:
            raise ValueError("数据获取失败, 请检查是否输入正确的股票代码")
        return temp_df


def stock_hk_indicator_eniu(
    symbol: str = "hk01093", indicator: str = "市盈率"
) -> pd.DataFrame:
    """
    亿牛网-港股指标
    https://eniu.com/gu/hk01093/roe
    :param symbol: 港股代码
    :type symbol: str
    :param indicator: 需要获取的指标, choice of {"港股", "市盈率", "市净率", "股息率", "ROE", "市值"}
    :type indicator: str
    :return: 指定 symbol 和 indicator 的数据
    :rtype: pandas.DataFrame
    """
    if indicator == "港股":
        url = "https://eniu.com/static/data/stock_list.json"
        r = requests.get(url, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json)
        temp_df = temp_df[temp_df["stock_id"].str.contains("hk")]
        temp_df.reset_index(inplace=True, drop=True)
        return temp_df
    if indicator == "市盈率":
        url = f"https://eniu.com/chart/peh/{symbol}"
    elif indicator == "市净率":
        url = f"https://eniu.com/chart/pbh/{symbol}"
    elif indicator == "股息率":
        url = f"https://eniu.com/chart/dvh/{symbol}"
    elif indicator == "ROE":
        url = f"https://eniu.com/chart/roeh/{symbol}"
    else:
        url = f"https://eniu.com/chart/marketvalueh/{symbol}"
    r = requests.get(url, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json)
    return temp_df


if __name__ == "__main__":
    stock_a_indicator_lg_all_df = stock_a_indicator_lg(symbol="all")
    print(stock_a_indicator_lg_all_df)

    stock_a_indicator_lg_df = stock_a_indicator_lg(symbol="000001")
    print(stock_a_indicator_lg_df)

    stock_hk_indicator_eniu_df = stock_hk_indicator_eniu(
        symbol="hk01093", indicator="市盈率"
    )
    print(stock_hk_indicator_eniu_df)
