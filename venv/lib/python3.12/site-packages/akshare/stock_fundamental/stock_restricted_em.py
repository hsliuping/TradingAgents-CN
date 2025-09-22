#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/7 19:30
Desc: 限售股解禁
https://data.eastmoney.com/dxf/detail.html
"""

import pandas as pd
import requests
from tqdm import tqdm


def stock_restricted_release_summary_em(
    symbol: str = "全部股票", start_date: str = "20221101", end_date: str = "20221209"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-限售股解禁
    https://data.eastmoney.com/dxf/marketStatistics.html?type=day&startdate=2022-11-08&enddate=2022-12-19
    :param symbol: 标的市场; choice of {"全部股票", "沪市A股", "科创板", "深市A股", "创业板", "京市A股"}
    :type symbol: str
    :param start_date: 开始时间
    :type start_date: str
    :param end_date: 结束时间
    :type end_date: str
    :return: 限售股解禁
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "全部股票": "000300",
        "沪市A股": "000001",
        "科创板": "000688",
        "深市A股": "399001",
        "创业板": "399001",
        "京市A股": "999999",
    }
    start_date_str = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date_str = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "FREE_DATE",
        "sortTypes": "1",
        "pageSize": "500",
        "pageNumber": "1",
        "columns": "ALL",
        "quoteColumns": "f2~03~INDEX_CODE,f3~03~INDEX_CODE,f124~03~INDEX_CODE",
        "quoteType": "0",
        "source": "WEB",
        "client": "WEB",
        "filter": f"""(INDEX_CODE="{symbol_map[symbol]}")(FREE_DATE>=
        '{start_date_str}')(FREE_DATE<='{end_date_str}')""",
        "reportName": "RPT_LIFTDAY_STA",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"] + 1
    temp_df.columns = [
        "序号",
        "解禁时间",
        "当日解禁股票家数",
        "实际解禁数量",
        "实际解禁市值",
        "沪深300指数",
        "沪深300指数涨跌幅",
        "解禁数量",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "序号",
            "解禁时间",
            "当日解禁股票家数",
            "解禁数量",
            "实际解禁数量",
            "实际解禁市值",
            "沪深300指数",
            "沪深300指数涨跌幅",
        ]
    ]
    temp_df["解禁时间"] = pd.to_datetime(temp_df["解禁时间"], errors="coerce").dt.date
    temp_df["当日解禁股票家数"] = pd.to_numeric(
        temp_df["当日解禁股票家数"], errors="coerce"
    )
    temp_df["解禁数量"] = pd.to_numeric(temp_df["解禁数量"], errors="coerce") * 10000
    temp_df["实际解禁数量"] = (
        pd.to_numeric(temp_df["实际解禁数量"], errors="coerce") * 10000
    )
    temp_df["实际解禁市值"] = (
        pd.to_numeric(temp_df["实际解禁市值"], errors="coerce") * 10000
    )
    temp_df["沪深300指数"] = pd.to_numeric(temp_df["沪深300指数"], errors="coerce")
    temp_df["沪深300指数涨跌幅"] = pd.to_numeric(
        temp_df["沪深300指数涨跌幅"], errors="coerce"
    )
    return temp_df


def stock_restricted_release_detail_em(
    start_date: str = "20221202", end_date: str = "20241202"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-限售股解禁-解禁详情一览
    https://data.eastmoney.com/dxf/detail.html
    :param start_date: 开始时间
    :type start_date: str
    :param end_date: 结束时间
    :type end_date: str
    :return: 解禁详情一览
    :rtype: pandas.DataFrame
    """
    start_date_str = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date_str = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "FREE_DATE,CURRENT_FREE_SHARES",
        "sortTypes": "1,1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_LIFT_STAGE",
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,FREE_DATE,CURRENT_FREE_SHARES,ABLE_FREE_SHARES,"
        "LIFT_MARKET_CAP,FREE_RATIO,NEW,B20_ADJCHRATE,A20_ADJCHRATE,FREE_SHARES_TYPE,TOTAL_RATIO,"
        "NON_FREE_SHARES,BATCH_HOLDER_NUM",
        "source": "WEB",
        "client": "WEB",
        "filter": f"""(FREE_DATE>='{start_date_str}')(FREE_DATE<='{end_date_str}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.columns = [
        "序号",
        "股票代码",
        "股票简称",
        "解禁时间",
        "实际解禁数量",
        "解禁数量",
        "实际解禁市值",
        "占解禁前流通市值比例",
        "解禁前一交易日收盘价",
        "解禁前20日涨跌幅",
        "解禁后20日涨跌幅",
        "限售股类型",
        "-",
        "-",
        "-",
    ]
    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "解禁时间",
            "限售股类型",
            "解禁数量",
            "实际解禁数量",
            "实际解禁市值",
            "占解禁前流通市值比例",
            "解禁前一交易日收盘价",
            "解禁前20日涨跌幅",
            "解禁后20日涨跌幅",
        ]
    ]
    big_df["解禁时间"] = pd.to_datetime(big_df["解禁时间"], errors="coerce").dt.date

    big_df["解禁数量"] = pd.to_numeric(big_df["解禁数量"], errors="coerce") * 10000
    big_df["实际解禁数量"] = (
        pd.to_numeric(big_df["实际解禁数量"], errors="coerce") * 10000
    )
    big_df["实际解禁市值"] = (
        pd.to_numeric(big_df["实际解禁市值"], errors="coerce") * 10000
    )
    big_df["占解禁前流通市值比例"] = pd.to_numeric(
        big_df["占解禁前流通市值比例"], errors="coerce"
    )
    big_df["解禁前一交易日收盘价"] = pd.to_numeric(
        big_df["解禁前一交易日收盘价"], errors="coerce"
    )
    big_df["解禁前20日涨跌幅"] = pd.to_numeric(
        big_df["解禁前20日涨跌幅"], errors="coerce"
    )
    big_df["解禁后20日涨跌幅"] = pd.to_numeric(
        big_df["解禁后20日涨跌幅"], errors="coerce"
    )
    return big_df


def stock_restricted_release_queue_em(symbol: str = "600000") -> pd.DataFrame:
    """
    东方财富网-数据中心-个股限售解禁-解禁批次
    https://data.eastmoney.com/dxf/q/600000.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 个股限售解禁
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "FREE_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_LIFT_STAGE",
        "filter": f'(SECURITY_CODE="{symbol}")',
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,FREE_DATE,CURRENT_FREE_SHARES,ABLE_FREE_SHARES,"
        "LIFT_MARKET_CAP,FREE_RATIO,NEW,B20_ADJCHRATE,A20_ADJCHRATE,FREE_SHARES_TYPE,TOTAL_RATIO,"
        "NON_FREE_SHARES,BATCH_HOLDER_NUM",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    if not data_json["result"]:
        return pd.DataFrame()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"] + 1
    temp_df.columns = [
        "序号",
        "-",
        "-",
        "解禁时间",
        "实际解禁数量",
        "解禁数量",
        "实际解禁数量市值",
        "占流通市值比例",
        "解禁前一交易日收盘价",
        "解禁前20日涨跌幅",
        "解禁后20日涨跌幅",
        "限售股类型",
        "占总市值比例",
        "未解禁数量",
        "解禁股东数",
    ]
    temp_df = temp_df[
        [
            "序号",
            "解禁时间",
            "解禁股东数",
            "解禁数量",
            "实际解禁数量",
            "未解禁数量",
            "实际解禁数量市值",
            "占总市值比例",
            "占流通市值比例",
            "解禁前一交易日收盘价",
            "限售股类型",
            "解禁前20日涨跌幅",
            "解禁后20日涨跌幅",
        ]
    ]
    temp_df["解禁时间"] = pd.to_datetime(temp_df["解禁时间"], errors="coerce").dt.date
    temp_df["解禁股东数"] = pd.to_numeric(temp_df["解禁股东数"], errors="coerce")
    temp_df["解禁数量"] = pd.to_numeric(temp_df["解禁数量"], errors="coerce") * 10000
    temp_df["实际解禁数量"] = (
        pd.to_numeric(temp_df["实际解禁数量"], errors="coerce") * 10000
    )
    temp_df["未解禁数量"] = (
        pd.to_numeric(temp_df["未解禁数量"], errors="coerce") * 10000
    )
    temp_df["实际解禁数量市值"] = (
        pd.to_numeric(temp_df["实际解禁数量市值"], errors="coerce") * 10000
    )
    temp_df["占总市值比例"] = pd.to_numeric(temp_df["占总市值比例"], errors="coerce")
    temp_df["占流通市值比例"] = pd.to_numeric(
        temp_df["占流通市值比例"], errors="coerce"
    )
    temp_df["解禁前一交易日收盘价"] = pd.to_numeric(
        temp_df["解禁前一交易日收盘价"], errors="coerce"
    )
    temp_df["解禁前20日涨跌幅"] = pd.to_numeric(
        temp_df["解禁前20日涨跌幅"], errors="coerce"
    )
    temp_df["解禁后20日涨跌幅"] = pd.to_numeric(
        temp_df["解禁后20日涨跌幅"], errors="coerce"
    )
    return temp_df


def stock_restricted_release_stockholder_em(
    symbol: str = "600000", date: str = "20200904"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-个股限售解禁-解禁股东
    https://data.eastmoney.com/dxf/q/600000.html
    :param symbol: 股票代码
    :type symbol: str
    :param date: 日期; 通过 ak.stock_restricted_release_queue_em(symbol="600000") 获取
    :type date: str
    :return: 个股限售解禁
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    date_str = "-".join([date[:4], date[4:6], date[6:]])
    params = {
        "sortColumns": "ADD_LISTING_SHARES",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_LIFT_GD",
        "filter": f"""(SECURITY_CODE="{symbol}")(FREE_DATE='{date_str}')""",
        "columns": "LIMITED_HOLDER_NAME,ADD_LISTING_SHARES,ACTUAL_LISTED_SHARES,ADD_LISTING_CAP,LOCK_MONTH,"
        "RESIDUAL_LIMITED_SHARES,FREE_SHARES_TYPE,PLAN_FEATURE",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"] + 1
    temp_df.columns = [
        "序号",
        "股东名称",
        "解禁数量",
        "实际解禁数量",
        "解禁市值",
        "锁定期",
        "剩余未解禁数量",
        "限售股类型",
        "进度",
    ]
    temp_df["解禁数量"] = pd.to_numeric(temp_df["解禁数量"], errors="coerce")
    temp_df["实际解禁数量"] = pd.to_numeric(temp_df["实际解禁数量"], errors="coerce")
    temp_df["解禁市值"] = pd.to_numeric(temp_df["解禁市值"], errors="coerce")
    temp_df["锁定期"] = pd.to_numeric(temp_df["锁定期"], errors="coerce")
    temp_df["剩余未解禁数量"] = pd.to_numeric(
        temp_df["剩余未解禁数量"], errors="coerce"
    )
    temp_df["剩余未解禁数量"] = pd.to_numeric(
        temp_df["剩余未解禁数量"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_restricted_release_summary_em_df = stock_restricted_release_summary_em(
        symbol="全部股票", start_date="20221108", end_date="20221209"
    )
    print(stock_restricted_release_summary_em_df)

    stock_restricted_release_detail_em_df = stock_restricted_release_detail_em(
        start_date="20221202", end_date="20221204"
    )
    print(stock_restricted_release_detail_em_df)

    stock_restricted_release_queue_em_df = stock_restricted_release_queue_em(
        symbol="600000"
    )
    print(stock_restricted_release_queue_em_df)

    stock_restricted_release_stockholder_em_df = (
        stock_restricted_release_stockholder_em(symbol="600000", date="20200904")
    )
    print(stock_restricted_release_stockholder_em_df)
