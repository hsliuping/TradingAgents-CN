#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/17 14:00
Desc: 股票指数成份股数据, 新浪有两个接口, 这里使用老接口:
新接口：https://vip.stock.finance.sina.com.cn/mkt/#zhishu_000001
老接口：https://vip.stock.finance.sina.com.cn/corp/view/vII_NewestComponent.php?page=1&indexid=399639
"""

import math
from io import BytesIO, StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

from akshare.utils import demjson


def index_stock_cons_sina(symbol: str = "000300") -> pd.DataFrame:
    """
    新浪新版股票指数成份页面, 目前该接口可获取指数数量较少
    https://vip.stock.finance.sina.com.cn/mkt/#zhishu_000040
    :param symbol: 指数代码
    :type symbol: str
    :return: 指数的成份股
    :rtype: pandas.DataFrame
    """
    if symbol == "000300":
        symbol = "hs300"
        url = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
            "/Market_Center.getHQNodeStockCountSimple"
        )
        params = {"node": f"{symbol}"}
        r = requests.get(url, params=params)
        page_num = math.ceil(int(r.json()) / 80) + 1
        temp_df = pd.DataFrame()
        for page in range(1, page_num):
            url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {
                "page": str(page),
                "num": "80",
                "sort": "symbol",
                "asc": "1",
                "node": "hs300",
                "symbol": "",
                "_s_r_a": "init",
            }
            r = requests.get(url, params=params)
            temp_df = pd.concat(
                objs=[temp_df, pd.DataFrame(demjson.decode(r.text))], ignore_index=True
            )
        return temp_df

    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple"
    params = {
        "page": 1,
        "num": "3000",
        "sort": "symbol",
        "asc": "1",
        "node": f"zhishu_{symbol}",
        "_s_r_a": "setlen",
    }
    r = requests.get(url, params=params)
    temp = pd.DataFrame(demjson.decode(r.text))
    return temp


def index_stock_info() -> pd.DataFrame:
    """
    聚宽-指数数据-指数列表
    https://www.joinquant.com/data/dict/indexData
    :return: 指数信息的数据框
    :rtype: pandas.DataFrame
    """
    url = "https://www.joinquant.com/data/dict/indexData"
    r = requests.get(url)
    r.encoding = "utf-8"
    index_df = pd.read_html(StringIO(r.text))[0]
    index_df["指数代码"] = index_df["指数代码"].str.split(".", expand=True)[0]
    index_df.columns = ["index_code", "display_name", "publish_date", "-", "-"]
    temp_df = index_df[["index_code", "display_name", "publish_date"]].copy()
    return temp_df


def index_stock_cons(symbol: str = "399639") -> pd.DataFrame:
    """
    最新股票指数的成份股目录
    https://vip.stock.finance.sina.com.cn/corp/view/vII_NewestComponent.php?page=1&indexid=399639
    :param symbol: 指数代码, 可以通过 ak.index_stock_info() 函数获取
    :type symbol: str
    :return: 最新股票指数的成份股目录
    :rtype: pandas.DataFrame
    """
    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vII_NewestComponent/indexid/{symbol}.phtml"
    r = requests.get(url)
    r.encoding = "gb2312"
    soup = BeautifulSoup(r.text, "lxml")
    page_num = (
        soup.find(attrs={"class": "table2"})
        .find("td")
        .find_all("a")[-1]["href"]
        .split("page=")[-1]
        .split("&")[0]
    )
    if page_num == "#":
        temp_df = pd.read_html(StringIO(r.text), header=0, skiprows=1)[3].iloc[:, :3]
        temp_df["品种代码"] = temp_df["品种代码"].astype(str).str.zfill(6)
        return temp_df

    temp_df = pd.DataFrame()
    for page in range(1, int(page_num) + 1):
        url = f"https://vip.stock.finance.sina.com.cn/corp/view/vII_NewestComponent.php?page={page}&indexid={symbol}"
        r = requests.get(url)
        r.encoding = "gb2312"
        temp_df = pd.concat(
            objs=[temp_df, pd.read_html(StringIO(r.text), header=1)[3]],
            ignore_index=True,
        )
    temp_df = temp_df.iloc[:, :3]
    temp_df["品种代码"] = temp_df["品种代码"].astype(str).str.zfill(6)
    return temp_df


def index_stock_cons_csindex(symbol: str = "000300") -> pd.DataFrame:
    """
    中证指数网站-成份股目录
    https://www.csindex.com.cn/zh-CN/indices/index-detail/000300
    :param symbol: 指数代码, 可以通过 ak.index_stock_info() 函数获取
    :type symbol: str
    :return: 最新指数的成份股
    :rtype: pandas.DataFrame
    """
    url = (
        f"https://oss-ch.csindex.com.cn/static/"
        f"html/csindex/public/uploads/file/autofile/cons/{symbol}cons.xls"
    )
    r = requests.get(url)
    temp_df = pd.read_excel(BytesIO(r.content))
    temp_df.columns = [
        "日期",
        "指数代码",
        "指数名称",
        "指数英文名称",
        "成分券代码",
        "成分券名称",
        "成分券英文名称",
        "交易所",
        "交易所英文名称",
    ]
    temp_df["日期"] = pd.to_datetime(
        temp_df["日期"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["指数代码"] = temp_df["指数代码"].astype(str).str.zfill(6)
    temp_df["成分券代码"] = temp_df["成分券代码"].astype(str).str.zfill(6)
    return temp_df


def index_stock_cons_weight_csindex(symbol: str = "000300") -> pd.DataFrame:
    """
    中证指数网站-样本权重
    https://www.csindex.com.cn/zh-CN/indices/index-detail/000300
    :param symbol: 指数代码, 可以通过 ak.index_stock_info() 接口获取
    :type symbol: str
    :return: 最新指数的成份股权重
    :rtype: pandas.DataFrame
    """
    url = (
        f"https://oss-ch.csindex.com.cn/static/html/csindex/"
        f"public/uploads/file/autofile/closeweight/{symbol}closeweight.xls"
    )
    r = requests.get(url)
    temp_df = pd.read_excel(BytesIO(r.content))
    temp_df.columns = [
        "日期",
        "指数代码",
        "指数名称",
        "指数英文名称",
        "成分券代码",
        "成分券名称",
        "成分券英文名称",
        "交易所",
        "交易所英文名称",
        "权重",
    ]
    temp_df["日期"] = pd.to_datetime(
        temp_df["日期"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["指数代码"] = temp_df["指数代码"].astype(str).str.zfill(6)
    temp_df["成分券代码"] = temp_df["成分券代码"].astype(str).str.zfill(6)
    temp_df["权重"] = pd.to_numeric(temp_df["权重"], errors="coerce")
    return temp_df


def stock_a_code_to_symbol(symbol: str = "000300") -> str:
    """
    输入股票代码判断股票市场
    :param symbol: 股票代码
    :type symbol: str
    :return: 股票市场
    :rtype: str
    """
    if symbol.startswith("6") or symbol.startswith("900"):
        return f"sh{symbol}"
    else:
        return f"sz{symbol}"


if __name__ == "__main__":
    index_stock_cons_csindex_df = index_stock_cons_csindex(symbol="000300")
    print(index_stock_cons_csindex_df)

    index_stock_cons_weight_csindex_df = index_stock_cons_weight_csindex(
        symbol="000300"
    )
    print(index_stock_cons_weight_csindex_df)

    index_stock_cons_sina_df = index_stock_cons_sina(symbol="000300")
    print(index_stock_cons_sina_df)

    index_stock_cons_df = index_stock_cons(symbol="000300")
    print(index_stock_cons_df)
