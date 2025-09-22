#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/10 19:30
Desc: 东方财富-沪深板块-行业板块
https://quote.eastmoney.com/center/boardlist.html#industry_board
"""

import re
from functools import lru_cache

import pandas as pd
import requests

from akshare.utils.func import fetch_paginated_data


@lru_cache()
def __stock_board_industry_name_em() -> pd.DataFrame:
    """
    东方财富网-沪深板块-行业板块-名称
    https://quote.eastmoney.com/center/boardlist.html#industry_board
    :return: 行业板块-名称
    :rtype: pandas.DataFrame
    """
    url = "https://17.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:90 t:2 f:!50",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,"
        "f23,f24,f25,f26,f22,f33,f11,f62,f128,f136,f115,f152,f124,f107,f104,f105,"
        "f140,f141,f207,f208,f209,f222",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.columns = [
        "排名",
        "-",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "-",
        "_",
        "-",
        "换手率",
        "-",
        "-",
        "-",
        "板块代码",
        "-",
        "板块名称",
        "-",
        "-",
        "-",
        "-",
        "总市值",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "上涨家数",
        "下跌家数",
        "-",
        "-",
        "-",
        "领涨股票",
        "-",
        "-",
        "领涨股票-涨跌幅",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "排名",
            "板块名称",
            "板块代码",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "总市值",
            "换手率",
            "上涨家数",
            "下跌家数",
            "领涨股票",
            "领涨股票-涨跌幅",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
    temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
    temp_df["上涨家数"] = pd.to_numeric(temp_df["上涨家数"], errors="coerce")
    temp_df["下跌家数"] = pd.to_numeric(temp_df["下跌家数"], errors="coerce")
    temp_df["领涨股票-涨跌幅"] = pd.to_numeric(
        temp_df["领涨股票-涨跌幅"], errors="coerce"
    )
    return temp_df


def stock_board_industry_name_em() -> pd.DataFrame:
    """
    东方财富网-沪深板块-行业板块-名称
    https://quote.eastmoney.com/center/boardlist.html#industry_board
    :return: 行业板块-名称
    :rtype: pandas.DataFrame
    """
    url = "https://17.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:90 t:2 f:!50",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,"
        "f23,f24,f25,f26,f22,f33,f11,f62,f128,f136,f115,f152,f124,f107,f104,f105,"
        "f140,f141,f207,f208,f209,f222",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.columns = [
        "排名",
        "-",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "-",
        "_",
        "-",
        "换手率",
        "-",
        "-",
        "-",
        "板块代码",
        "-",
        "板块名称",
        "-",
        "-",
        "-",
        "-",
        "总市值",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "上涨家数",
        "下跌家数",
        "-",
        "-",
        "-",
        "领涨股票",
        "-",
        "-",
        "领涨股票-涨跌幅",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "排名",
            "板块名称",
            "板块代码",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "总市值",
            "换手率",
            "上涨家数",
            "下跌家数",
            "领涨股票",
            "领涨股票-涨跌幅",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
    temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
    temp_df["上涨家数"] = pd.to_numeric(temp_df["上涨家数"], errors="coerce")
    temp_df["下跌家数"] = pd.to_numeric(temp_df["下跌家数"], errors="coerce")
    temp_df["领涨股票-涨跌幅"] = pd.to_numeric(
        temp_df["领涨股票-涨跌幅"], errors="coerce"
    )
    return temp_df


def stock_board_industry_spot_em(symbol: str = "小金属") -> pd.DataFrame:
    """
    东方财富网-沪深板块-行业板块-实时行情
    https://quote.eastmoney.com/bk/90.BK1027.html
    :param symbol: 板块名称 or 东财板块代码
    :type symbol: str
    :return: 实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://91.push2.eastmoney.com/api/qt/stock/get"
    field_map = {
        "f43": "最新",
        "f44": "最高",
        "f45": "最低",
        "f46": "开盘",
        "f47": "成交量",
        "f48": "成交额",
        "f170": "涨跌幅",
        "f171": "振幅",
        "f168": "换手率",
        "f169": "涨跌额",
    }

    if re.match(pattern=r"^BK\d+", string=symbol):
        em_code = symbol
    else:
        industry_listing = __stock_board_industry_name_em()
        em_code = industry_listing.query("板块名称 == @symbol")["板块代码"].values[0]
    params = dict(
        fields=",".join(field_map.keys()),
        mpi="1000",
        invt="2",
        fltt="1",
        secid=f"90.{em_code}",
    )
    r = requests.get(url, params=params)
    data_dict = r.json()
    result = pd.DataFrame.from_dict(data_dict["data"], orient="index")
    result.rename(field_map, inplace=True)
    result.reset_index(inplace=True)
    result.columns = ["item", "value"]
    result["value"] = pd.to_numeric(result["value"], errors="coerce")

    # 各项转换成正常单位. 除了成交量与成交额, 原始数据中已是正常单位(元)
    result["value"] = result["value"] * 1e-2
    result.iloc[4, 1] = result.iloc[4, 1] * 1e2
    result.iloc[5, 1] = result.iloc[5, 1] * 1e2
    return result


def stock_board_industry_hist_em(
    symbol: str = "小金属",
    start_date: str = "20211201",
    end_date: str = "20220401",
    period: str = "日k",
    adjust: str = "",
) -> pd.DataFrame:
    """
    东方财富网-沪深板块-行业板块-历史行情
    https://quote.eastmoney.com/bk/90.BK1027.html
    :param symbol: 板块名称
    :type symbol: str
    :param start_date: 开始时间
    :type start_date: str
    :param end_date: 结束时间
    :type end_date: str
    :param period: 周期; choice of {"日k", "周k", "月k"}
    :type period: str
    :param adjust: choice of {'': 不复权, "qfq": 前复权, "hfq": 后复权}
    :type adjust: str
    :return: 历史行情
    :rtype: pandas.DataFrame
    """
    if re.match(pattern=r"^BK\d+", string=symbol):
        em_code = symbol
    else:
        industry_listing = __stock_board_industry_name_em()
        em_code = industry_listing.query("板块名称 == @symbol")["板块代码"].values[0]
    period_map = {
        "日k": "101",
        "周k": "102",
        "月k": "103",
    }
    adjust_map = {"": "0", "qfq": "1", "hfq": "2"}
    url = "http://7.push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": f"90.{em_code}",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": period_map[period],
        "fqt": adjust_map[adjust],
        "beg": start_date,
        "end": end_date,
        "smplmt": "10000",
        "lmt": "1000000",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df.columns = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率",
    ]
    temp_df = temp_df[
        [
            "日期",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "涨跌幅",
            "涨跌额",
            "成交量",
            "成交额",
            "振幅",
            "换手率",
        ]
    ]
    temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
    temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
    return temp_df


def stock_board_industry_hist_min_em(
    symbol: str = "小金属", period: str = "5"
) -> pd.DataFrame:
    """
    东方财富网-沪深板块-行业板块-分时历史行情
    https://quote.eastmoney.com/bk/90.BK1027.html
    :param symbol: 板块名称
    :type symbol: str
    :param period: choice of {"1", "5", "15", "30", "60"}
    :type period: str
    :return: 分时历史行情
    :rtype: pandas.DataFrame
    """
    if re.match(pattern=r"^BK\d+", string=symbol):
        em_code = symbol
    else:
        industry_listing = __stock_board_industry_name_em()
        em_code = industry_listing.query("板块名称 == @symbol")["板块代码"].values[0]
    if period == "1":
        url = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "iscr": "0",
            "ndays": "1",
            "secid": f"90.{em_code}",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            [item.split(",") for item in data_json["data"]["trends"]]
        )
        temp_df.columns = [
            "日期时间",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "最新价",
        ]

        temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
        temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
        temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
        temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
        temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        return temp_df
    else:
        url = "https://7.push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": f"90.{em_code}",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": period,
            "fqt": "1",
            "beg": "0",
            "end": "20500101",
            "smplmt": "10000",
            "lmt": "1000000",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            [item.split(",") for item in data_json["data"]["klines"]]
        )
        temp_df.columns = [
            "日期时间",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "振幅",
            "涨跌幅",
            "涨跌额",
            "换手率",
        ]
        temp_df = temp_df[
            [
                "日期时间",
                "开盘",
                "收盘",
                "最高",
                "最低",
                "涨跌幅",
                "涨跌额",
                "成交量",
                "成交额",
                "振幅",
                "换手率",
            ]
        ]
        temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
        temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
        temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
        temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
        temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        return temp_df


def stock_board_industry_cons_em(symbol: str = "小金属") -> pd.DataFrame:
    """
    东方财富网-沪深板块-行业板块-板块成份
    https://data.eastmoney.com/bkzj/BK1027.html
    :param symbol: 板块名称或者板块代码
    :type symbol: str
    :return: 板块成份
    :rtype: pandas.DataFrame
    """
    if re.match(pattern=r"^BK\d+", string=symbol):
        stock_board_code = symbol
    else:
        stock_board_concept_em_map = __stock_board_industry_name_em()
        stock_board_code = stock_board_concept_em_map[
            stock_board_concept_em_map["板块名称"] == symbol
        ]["板块代码"].values[0]
    url = "https://29.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": f"b:{stock_board_code} f:!50",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,"
        "f23,f24,f25,f22,f11,f62,f128,f136,f115,f152,f45",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.columns = [
        "序号",
        "_",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "成交量",
        "成交额",
        "振幅",
        "换手率",
        "市盈率-动态",
        "_",
        "_",
        "代码",
        "_",
        "名称",
        "最高",
        "最低",
        "今开",
        "昨收",
        "_",
        "_",
        "_",
        "市净率",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "序号",
            "代码",
            "名称",
            "最新价",
            "涨跌幅",
            "涨跌额",
            "成交量",
            "成交额",
            "振幅",
            "最高",
            "最低",
            "今开",
            "昨收",
            "换手率",
            "市盈率-动态",
            "市净率",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
    temp_df["市盈率-动态"] = pd.to_numeric(temp_df["市盈率-动态"], errors="coerce")
    temp_df["市净率"] = pd.to_numeric(temp_df["市净率"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_board_industry_name_em_df = stock_board_industry_name_em()
    print(stock_board_industry_name_em_df)

    stock_board_industry_spot_em_df = stock_board_industry_spot_em(symbol="小金属")
    print(stock_board_industry_spot_em_df)

    stock_board_industry_hist_em_df = stock_board_industry_hist_em(
        symbol="小金属",
        start_date="20211201",
        end_date="20240222",
        period="日k",
        adjust="",
    )
    print(stock_board_industry_hist_em_df)

    stock_board_industry_hist_min_em_df = stock_board_industry_hist_min_em(
        symbol="小金属", period="1"
    )
    print(stock_board_industry_hist_min_em_df)

    stock_board_industry_cons_em_df = stock_board_industry_cons_em(symbol="互联网服务")
    print(stock_board_industry_cons_em_df)
