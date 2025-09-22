#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/4 18:20
Desc: 东方财富网-数据中心-特色数据-千股千评
https://data.eastmoney.com/stockcomment/
"""

import time

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_comment_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-千股千评
    https://data.eastmoney.com/stockcomment/
    :return: 千股千评数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "SECURITY_CODE",
        "sortTypes": "1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_DMSK_TS_STOCKNEW",
        "quoteColumns": "f2~01~SECURITY_CODE~CLOSE_PRICE,f8~01~SECURITY_CODE~TURNOVERRATE,"
        "f3~01~SECURITY_CODE~CHANGE_RATE,f9~01~SECURITY_CODE~PE_DYNAMIC",
        "columns": "ALL",
        "filter": "",
        "token": "894050c76af8597a853f5b408b759f5d",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "-",
        "代码",
        "-",
        "交易日",
        "名称",
        "-",
        "-",
        "-",
        "最新价",
        "涨跌幅",
        "-",
        "换手率",
        "主力成本",
        "市盈率",
        "-",
        "-",
        "机构参与度",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "综合得分",
        "上升",
        "目前排名",
        "关注指数",
        "-",
    ]
    big_df = big_df[
        [
            "序号",
            "代码",
            "名称",
            "最新价",
            "涨跌幅",
            "换手率",
            "市盈率",
            "主力成本",
            "机构参与度",
            "综合得分",
            "上升",
            "目前排名",
            "关注指数",
            "交易日",
        ]
    ]

    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["市盈率"] = pd.to_numeric(big_df["市盈率"], errors="coerce")
    big_df["主力成本"] = pd.to_numeric(big_df["主力成本"], errors="coerce")
    big_df["机构参与度"] = pd.to_numeric(big_df["机构参与度"], errors="coerce")
    big_df["综合得分"] = pd.to_numeric(big_df["综合得分"], errors="coerce")
    big_df["上升"] = pd.to_numeric(big_df["上升"], errors="coerce")
    big_df["目前排名"] = pd.to_numeric(big_df["目前排名"], errors="coerce")
    big_df["关注指数"] = pd.to_numeric(big_df["关注指数"], errors="coerce")
    big_df["交易日"] = pd.to_datetime(big_df["交易日"], errors="coerce").dt.date
    return big_df


def stock_comment_detail_zlkp_jgcyd_em(symbol: str = "600000") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-千股千评-主力控盘-机构参与度
    https://data.eastmoney.com/stockcomment/stock/600000.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 主力控盘-机构参与度
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_DMSK_TS_STOCKEVALUATE",
        "filter": f'(SECURITY_CODE="{symbol}")',
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df = temp_df[["TRADE_DATE", "ORG_PARTICIPATE"]]
    temp_df.columns = ["交易日", "机构参与度"]
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"], errors="coerce").dt.date
    temp_df.sort_values(["交易日"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    temp_df["机构参与度"] = pd.to_numeric(temp_df["机构参与度"], errors="coerce") * 100
    return temp_df


def stock_comment_detail_zhpj_lspf_em(symbol: str = "600000") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-千股千评-综合评价-历史评分
    https://data.eastmoney.com/stockcomment/stock/600000.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 综合评价-历史评分
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "filter": f'(SECURITY_CODE="{symbol}")',
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_STOCK_HISTORYMARK",
        "sortColumns": "DIAGNOSE_DATE",
        "sortTypes": "1",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.rename(
        columns={
            "TOTAL_SCORE": "评分",
            "DIAGNOSE_DATE": "交易日",
        },
        inplace=True,
    )
    temp_df = temp_df[["交易日", "评分"]]
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"], errors="coerce").dt.date
    temp_df.sort_values(by=["交易日"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    temp_df["评分"] = pd.to_numeric(temp_df["评分"], errors="coerce")
    return temp_df


def stock_comment_detail_scrd_focus_em(symbol: str = "600000") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-千股千评-市场热度-用户关注指数
    https://data.eastmoney.com/stockcomment/stock/600000.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 市场热度-用户关注指数
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "filter": f'(SECURITY_CODE="{symbol}")',
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_STOCK_MARKETFOCUS",
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageSize": "30",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.rename(
        columns={
            "MARKET_FOCUS": "用户关注指数",
            "TRADE_DATE": "交易日",
        },
        inplace=True,
    )
    temp_df = temp_df[["交易日", "用户关注指数"]]
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"], errors="coerce").dt.date
    temp_df.sort_values(by=["交易日"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    temp_df["用户关注指数"] = pd.to_numeric(temp_df["用户关注指数"], errors="coerce")
    return temp_df


def stock_comment_detail_scrd_desire_em(
    symbol: str = "600000",
) -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-千股千评-市场热度-市场参与意愿
    https://data.eastmoney.com/stockcomment/stock/600000.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 市场热度-市场参与意愿
    :rtype: pandas.DataFrame
    """
    url = f"https://data.eastmoney.com/stockcomment/api/{symbol}.json"
    try_count = 10
    data_json = None
    while try_count:
        try:
            r = requests.get(url)
            data_json = r.json()
            break
        except requests.exceptions.JSONDecodeError:
            try_count -= 1
            time.sleep(1)
            continue

    date_str = (
        data_json["ApiResults"]["scrd"]["desire"][0][0]["UpdateTime"]
        .split(" ")[0]
        .replace("/", "-")
    )

    temp_df = pd.DataFrame(
        [
            data_json["ApiResults"]["scrd"]["desire"][1]["XData"],
            data_json["ApiResults"]["scrd"]["desire"][1]["Ydata"]["MajorPeopleNumChg"],
            data_json["ApiResults"]["scrd"]["desire"][1]["Ydata"]["PeopleNumChange"],
            data_json["ApiResults"]["scrd"]["desire"][1]["Ydata"]["RetailPeopleNumChg"],
        ]
    ).T
    temp_df.columns = ["日期时间", "大户", "全部", "散户"]
    temp_df["日期时间"] = date_str + " " + temp_df["日期时间"]
    temp_df["日期时间"] = pd.to_datetime(temp_df["日期时间"], errors="coerce")
    temp_df.sort_values(by=["日期时间"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    temp_df["大户"] = pd.to_numeric(temp_df["大户"], errors="coerce")
    temp_df["全部"] = pd.to_numeric(temp_df["全部"], errors="coerce")
    temp_df["散户"] = pd.to_numeric(temp_df["散户"], errors="coerce")
    return temp_df


def stock_comment_detail_scrd_desire_daily_em(
    symbol: str = "600000",
) -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-千股千评-市场热度-日度市场参与意愿
    https://data.eastmoney.com/stockcomment/stock/600000.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 市场热度-日度市场参与意愿
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "filter": f'(SECURITY_CODE="{symbol}")',
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_STOCK_PARTICIPATION",
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageSize": "30",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.rename(
        columns={
            "PARTICIPATION_WISH_5DAYSCHANGE": "5日平均参与意愿变化",
            "PARTICIPATION_WISH_CHANGE": "当日意愿上升",
            "TRADE_DATE": "交易日",
        },
        inplace=True,
    )
    temp_df = temp_df[["交易日", "当日意愿上升", "5日平均参与意愿变化"]]
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"], errors="coerce").dt.date
    temp_df.sort_values(by=["交易日"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    temp_df["当日意愿上升"] = pd.to_numeric(temp_df["当日意愿上升"], errors="coerce")
    temp_df["5日平均参与意愿变化"] = pd.to_numeric(
        temp_df["5日平均参与意愿变化"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_comment_em_df = stock_comment_em()
    print(stock_comment_em_df)

    stock_comment_detail_zlkp_jgcyd_em_df = stock_comment_detail_zlkp_jgcyd_em(
        symbol="600000"
    )
    print(stock_comment_detail_zlkp_jgcyd_em_df)

    stock_comment_detail_zhpj_lspf_em_df = stock_comment_detail_zhpj_lspf_em(
        symbol="600000"
    )
    print(stock_comment_detail_zhpj_lspf_em_df)

    stock_comment_detail_scrd_focus_em_df = stock_comment_detail_scrd_focus_em(
        symbol="600000"
    )
    print(stock_comment_detail_scrd_focus_em_df)

    stock_comment_detail_scrd_desire_em_df = stock_comment_detail_scrd_desire_em(
        symbol="600000"
    )
    print(stock_comment_detail_scrd_desire_em_df)

    stock_comment_detail_scrd_desire_daily_em_df = (
        stock_comment_detail_scrd_desire_daily_em(symbol="600000")
    )
    print(stock_comment_detail_scrd_desire_daily_em_df)
