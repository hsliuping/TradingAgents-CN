# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/4/22 14:00
Desc: 东方财富网-数据中心-龙虎榜单
https://data.eastmoney.com/stock/tradedetail.html
"""

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm


def stock_lhb_detail_em(
    start_date: str = "20230403", end_date: str = "20230417"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-龙虎榜详情
    https://data.eastmoney.com/stock/tradedetail.html
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :return: 龙虎榜详情
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "SECURITY_CODE,TRADE_DATE",
        "sortTypes": "1,-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
        "columns": "SECURITY_CODE,SECUCODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLAIN,CLOSE_PRICE,CHANGE_RATE,"
        "BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,BILLBOARD_DEAL_AMT,ACCUM_AMOUNT,"
        "DEAL_NET_RATIO,DEAL_AMOUNT_RATIO,TURNOVERRATE,FREE_MARKET_CAP,EXPLANATION,D1_CLOSE_ADJCHRATE,"
        "D2_CLOSE_ADJCHRATE,D5_CLOSE_ADJCHRATE,D10_CLOSE_ADJCHRATE,SECURITY_TYPE_CODE",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(TRADE_DATE<='{end_date}')(TRADE_DATE>='{start_date}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page_num = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page_num + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.rename(
        columns={
            "index": "序号",
            "SECURITY_CODE": "代码",
            "SECUCODE": "-",
            "SECURITY_NAME_ABBR": "名称",
            "TRADE_DATE": "上榜日",
            "EXPLAIN": "解读",
            "CLOSE_PRICE": "收盘价",
            "CHANGE_RATE": "涨跌幅",
            "BILLBOARD_NET_AMT": "龙虎榜净买额",
            "BILLBOARD_BUY_AMT": "龙虎榜买入额",
            "BILLBOARD_SELL_AMT": "龙虎榜卖出额",
            "BILLBOARD_DEAL_AMT": "龙虎榜成交额",
            "ACCUM_AMOUNT": "市场总成交额",
            "DEAL_NET_RATIO": "净买额占总成交比",
            "DEAL_AMOUNT_RATIO": "成交额占总成交比",
            "TURNOVERRATE": "换手率",
            "FREE_MARKET_CAP": "流通市值",
            "EXPLANATION": "上榜原因",
            "D1_CLOSE_ADJCHRATE": "上榜后1日",
            "D2_CLOSE_ADJCHRATE": "上榜后2日",
            "D5_CLOSE_ADJCHRATE": "上榜后5日",
            "D10_CLOSE_ADJCHRATE": "上榜后10日",
        },
        inplace=True,
    )

    big_df = big_df[
        [
            "序号",
            "代码",
            "名称",
            "上榜日",
            "解读",
            "收盘价",
            "涨跌幅",
            "龙虎榜净买额",
            "龙虎榜买入额",
            "龙虎榜卖出额",
            "龙虎榜成交额",
            "市场总成交额",
            "净买额占总成交比",
            "成交额占总成交比",
            "换手率",
            "流通市值",
            "上榜原因",
            "上榜后1日",
            "上榜后2日",
            "上榜后5日",
            "上榜后10日",
        ]
    ]
    big_df["上榜日"] = pd.to_datetime(big_df["上榜日"], errors="coerce").dt.date
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["龙虎榜净买额"] = pd.to_numeric(big_df["龙虎榜净买额"], errors="coerce")
    big_df["龙虎榜买入额"] = pd.to_numeric(big_df["龙虎榜买入额"], errors="coerce")
    big_df["龙虎榜卖出额"] = pd.to_numeric(big_df["龙虎榜卖出额"], errors="coerce")
    big_df["龙虎榜成交额"] = pd.to_numeric(big_df["龙虎榜成交额"], errors="coerce")
    big_df["市场总成交额"] = pd.to_numeric(big_df["市场总成交额"], errors="coerce")
    big_df["净买额占总成交比"] = pd.to_numeric(
        big_df["净买额占总成交比"], errors="coerce"
    )
    big_df["成交额占总成交比"] = pd.to_numeric(
        big_df["成交额占总成交比"], errors="coerce"
    )
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["流通市值"] = pd.to_numeric(big_df["流通市值"], errors="coerce")
    big_df["上榜后1日"] = pd.to_numeric(big_df["上榜后1日"], errors="coerce")
    big_df["上榜后2日"] = pd.to_numeric(big_df["上榜后2日"], errors="coerce")
    big_df["上榜后5日"] = pd.to_numeric(big_df["上榜后5日"], errors="coerce")
    big_df["上榜后10日"] = pd.to_numeric(big_df["上榜后10日"], errors="coerce")
    return big_df


def stock_lhb_stock_statistic_em(symbol: str = "近一月") -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-个股上榜统计
    https://data.eastmoney.com/stock/tradedetail.html
    :param symbol: choice of {"近一月", "近三月", "近六月", "近一年"}
    :type symbol: str
    :return: 个股上榜统计
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "近一月": "01",
        "近三月": "02",
        "近六月": "03",
        "近一年": "04",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "BILLBOARD_TIMES,LATEST_TDATE,SECURITY_CODE",
        "sortTypes": "-1,-1,1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_BILLBOARD_TRADEALL",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(STATISTICS_CYCLE="{symbol_map[symbol]}")',
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = [
        "序号",
        "-",
        "代码",
        "最近上榜日",
        "名称",
        "近1个月涨跌幅",
        "近3个月涨跌幅",
        "近6个月涨跌幅",
        "近1年涨跌幅",
        "涨跌幅",
        "收盘价",
        "-",
        "龙虎榜总成交额",
        "龙虎榜净买额",
        "-",
        "-",
        "机构买入净额",
        "上榜次数",
        "龙虎榜买入额",
        "龙虎榜卖出额",
        "机构买入总额",
        "机构卖出总额",
        "买方机构次数",
        "卖方机构次数",
        "-",
    ]
    temp_df = temp_df[
        [
            "序号",
            "代码",
            "名称",
            "最近上榜日",
            "收盘价",
            "涨跌幅",
            "上榜次数",
            "龙虎榜净买额",
            "龙虎榜买入额",
            "龙虎榜卖出额",
            "龙虎榜总成交额",
            "买方机构次数",
            "卖方机构次数",
            "机构买入净额",
            "机构买入总额",
            "机构卖出总额",
            "近1个月涨跌幅",
            "近3个月涨跌幅",
            "近6个月涨跌幅",
            "近1年涨跌幅",
        ]
    ]
    temp_df["最近上榜日"] = pd.to_datetime(
        temp_df["最近上榜日"], errors="coerce"
    ).dt.date
    return temp_df


def stock_lhb_jgmmtj_em(
    start_date: str = "20240417", end_date: str = "20240430"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-机构买卖每日统计
    https://data.eastmoney.com/stock/jgmmtj.html
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :return: 机构买卖每日统计
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NET_BUY_AMT,TRADE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1,1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_ORGANIZATION_TRADE_DETAILS",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(TRADE_DATE>='{start_date}')(TRADE_DATE<='{end_date}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
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
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "-",
        "名称",
        "代码",
        "上榜日期",
        "收盘价",
        "涨跌幅",
        "买方机构数",
        "卖方机构数",
        "机构买入总额",
        "机构卖出总额",
        "机构买入净额",
        "市场总成交额",
        "机构净买额占总成交额比",
        "换手率",
        "流通市值",
        "上榜原因",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    big_df = big_df[
        [
            "序号",
            "代码",
            "名称",
            "收盘价",
            "涨跌幅",
            "买方机构数",
            "卖方机构数",
            "机构买入总额",
            "机构卖出总额",
            "机构买入净额",
            "市场总成交额",
            "机构净买额占总成交额比",
            "换手率",
            "流通市值",
            "上榜原因",
            "上榜日期",
        ]
    ]
    big_df["上榜日期"] = pd.to_datetime(big_df["上榜日期"], errors="coerce").dt.date
    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["买方机构数"] = pd.to_numeric(big_df["买方机构数"], errors="coerce")
    big_df["卖方机构数"] = pd.to_numeric(big_df["卖方机构数"], errors="coerce")
    big_df["机构买入总额"] = pd.to_numeric(big_df["机构买入总额"], errors="coerce")
    big_df["机构卖出总额"] = pd.to_numeric(big_df["机构卖出总额"], errors="coerce")
    big_df["机构买入净额"] = pd.to_numeric(big_df["机构买入净额"], errors="coerce")
    big_df["市场总成交额"] = pd.to_numeric(big_df["市场总成交额"], errors="coerce")
    big_df["机构净买额占总成交额比"] = pd.to_numeric(
        big_df["机构净买额占总成交额比"], errors="coerce"
    )
    big_df["换手率"] = pd.to_numeric(big_df["换手率"], errors="coerce")
    big_df["流通市值"] = pd.to_numeric(big_df["流通市值"], errors="coerce")
    return big_df


def stock_lhb_jgstatistic_em(symbol: str = "近一月") -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-机构席位追踪
    https://data.eastmoney.com/stock/jgstatistic.html
    :param symbol: choice of {"近一月", "近三月", "近六月", "近一年"}
    :type symbol: str
    :return: 机构席位追踪
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "近一月": "01",
        "近三月": "02",
        "近六月": "03",
        "近一年": "04",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "ONLIST_TIMES,SECURITY_CODE",
        "sortTypes": "-1,1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_ORGANIZATION_SEATNEW",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(STATISTICSCYCLE="{symbol_map[symbol]}")',
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
    big_df.rename(
        columns={
            "index": "序号",
            "SECURITY_CODE": "代码",
            "SECURITY_NAME_ABBR": "名称",
            "CLOSE_PRICE": "收盘价",
            "CHANGE_RATE": "涨跌幅",
            "AMOUNT": "龙虎榜成交金额",
            "ONLIST_TIMES": "上榜次数",
            "BUY_AMT": "机构买入额",
            "BUY_TIMES": "机构买入次数",
            "SELL_AMT": "机构卖出额",
            "SELL_TIMES": "机构卖出次数",
            "NET_BUY_AMT": "机构净买额",
            "M1_CLOSE_ADJCHRATE": "近1个月涨跌幅",
            "M3_CLOSE_ADJCHRATE": "近3个月涨跌幅",
            "M6_CLOSE_ADJCHRATE": "近6个月涨跌幅",
            "Y1_CLOSE_ADJCHRATE": "近1年涨跌幅",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "代码",
            "名称",
            "收盘价",
            "涨跌幅",
            "龙虎榜成交金额",
            "上榜次数",
            "机构买入额",
            "机构买入次数",
            "机构卖出额",
            "机构卖出次数",
            "机构净买额",
            "近1个月涨跌幅",
            "近3个月涨跌幅",
            "近6个月涨跌幅",
            "近1年涨跌幅",
        ]
    ]

    big_df["收盘价"] = pd.to_numeric(big_df["收盘价"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["龙虎榜成交金额"] = pd.to_numeric(big_df["龙虎榜成交金额"], errors="coerce")
    big_df["上榜次数"] = pd.to_numeric(big_df["上榜次数"], errors="coerce")
    big_df["机构买入额"] = pd.to_numeric(big_df["机构买入额"], errors="coerce")
    big_df["机构买入次数"] = pd.to_numeric(big_df["机构买入次数"], errors="coerce")
    big_df["机构卖出额"] = pd.to_numeric(big_df["机构卖出额"], errors="coerce")
    big_df["机构卖出次数"] = pd.to_numeric(big_df["机构卖出次数"], errors="coerce")
    big_df["机构净买额"] = pd.to_numeric(big_df["机构净买额"], errors="coerce")
    big_df["近1个月涨跌幅"] = pd.to_numeric(big_df["近1个月涨跌幅"], errors="coerce")
    big_df["近3个月涨跌幅"] = pd.to_numeric(big_df["近3个月涨跌幅"], errors="coerce")
    big_df["近6个月涨跌幅"] = pd.to_numeric(big_df["近6个月涨跌幅"], errors="coerce")
    big_df["近1年涨跌幅"] = pd.to_numeric(big_df["近1年涨跌幅"], errors="coerce")
    return big_df


def stock_lhb_hyyyb_em(
    start_date: str = "20220324", end_date: str = "20220324"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-每日活跃营业部
    https://data.eastmoney.com/stock/hyyyb.html
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :return: 每日活跃营业部
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "TOTAL_NETAMT,ONLIST_DATE,OPERATEDEPT_CODE",
        "sortTypes": "-1,-1,1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_OPERATEDEPT_ACTIVE",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(ONLIST_DATE>='{start_date}')(ONLIST_DATE<='{end_date}')",
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
        "营业部名称",
        "上榜日",
        "买入个股数",
        "卖出个股数",
        "买入总金额",
        "卖出总金额",
        "总买卖净额",
        "-",
        "营业部代码",
        "买入股票",
        "-",
        "-",
    ]
    big_df = big_df[
        [
            "序号",
            "营业部名称",
            "上榜日",
            "买入个股数",
            "卖出个股数",
            "买入总金额",
            "卖出总金额",
            "总买卖净额",
            "买入股票",
            "营业部代码",
        ]
    ]

    big_df["上榜日"] = pd.to_datetime(big_df["上榜日"], errors="coerce").dt.date
    big_df["买入个股数"] = pd.to_numeric(big_df["买入个股数"], errors="coerce")
    big_df["卖出个股数"] = pd.to_numeric(big_df["卖出个股数"], errors="coerce")
    big_df["买入总金额"] = pd.to_numeric(big_df["买入总金额"], errors="coerce")
    big_df["卖出总金额"] = pd.to_numeric(big_df["卖出总金额"], errors="coerce")
    big_df["总买卖净额"] = pd.to_numeric(big_df["总买卖净额"], errors="coerce")
    return big_df


def stock_lhb_yybph_em(symbol: str = "近一月") -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-营业部排行
    https://data.eastmoney.com/stock/yybph.html
    :param symbol: choice of {"近一月", "近三月", "近六月", "近一年"}
    :type symbol: str
    :return: 营业部排行
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "近一月": "01",
        "近三月": "02",
        "近六月": "03",
        "近一年": "04",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "TOTAL_BUYER_SALESTIMES_1DAY,OPERATEDEPT_CODE",
        "sortTypes": "-1,1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_RATEDEPT_RETURNT_RANKING",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(STATISTICSCYCLE="{symbol_map[symbol]}")',
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
    big_df.rename(
        columns={
            "index": "序号",
            "OPERATEDEPT_NAME": "营业部名称",
            "TOTAL_BUYER_SALESTIMES_1DAY": "上榜后1天-买入次数",
            "AVERAGE_INCREASE_1DAY": "上榜后1天-平均涨幅",
            "RISE_PROBABILITY_1DAY": "上榜后1天-上涨概率",
            "TOTAL_BUYER_SALESTIMES_2DAY": "上榜后2天-买入次数",
            "AVERAGE_INCREASE_2DAY": "上榜后2天-平均涨幅",
            "RISE_PROBABILITY_2DAY": "上榜后2天-上涨概率",
            "TOTAL_BUYER_SALESTIMES_3DAY": "上榜后3天-买入次数",
            "AVERAGE_INCREASE_3DAY": "上榜后3天-平均涨幅",
            "RISE_PROBABILITY_3DAY": "上榜后3天-上涨概率",
            "TOTAL_BUYER_SALESTIMES_5DAY": "上榜后5天-买入次数",
            "AVERAGE_INCREASE_5DAY": "上榜后5天-平均涨幅",
            "RISE_PROBABILITY_5DAY": "上榜后5天-上涨概率",
            "TOTAL_BUYER_SALESTIMES_10DAY": "上榜后10天-买入次数",
            "AVERAGE_INCREASE_10DAY": "上榜后10天-平均涨幅",
            "RISE_PROBABILITY_10DAY": "上榜后10天-上涨概率",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "营业部名称",
            "上榜后1天-买入次数",
            "上榜后1天-平均涨幅",
            "上榜后1天-上涨概率",
            "上榜后2天-买入次数",
            "上榜后2天-平均涨幅",
            "上榜后2天-上涨概率",
            "上榜后3天-买入次数",
            "上榜后3天-平均涨幅",
            "上榜后3天-上涨概率",
            "上榜后5天-买入次数",
            "上榜后5天-平均涨幅",
            "上榜后5天-上涨概率",
            "上榜后10天-买入次数",
            "上榜后10天-平均涨幅",
            "上榜后10天-上涨概率",
        ]
    ]

    big_df["上榜后1天-买入次数"] = pd.to_numeric(
        big_df["上榜后1天-买入次数"], errors="coerce"
    )
    big_df["上榜后1天-平均涨幅"] = pd.to_numeric(
        big_df["上榜后1天-平均涨幅"], errors="coerce"
    )
    big_df["上榜后1天-上涨概率"] = pd.to_numeric(
        big_df["上榜后1天-上涨概率"], errors="coerce"
    )

    big_df["上榜后2天-买入次数"] = pd.to_numeric(
        big_df["上榜后2天-买入次数"], errors="coerce"
    )
    big_df["上榜后2天-平均涨幅"] = pd.to_numeric(
        big_df["上榜后2天-平均涨幅"], errors="coerce"
    )
    big_df["上榜后2天-上涨概率"] = pd.to_numeric(
        big_df["上榜后2天-上涨概率"], errors="coerce"
    )

    big_df["上榜后3天-买入次数"] = pd.to_numeric(
        big_df["上榜后3天-买入次数"], errors="coerce"
    )
    big_df["上榜后3天-平均涨幅"] = pd.to_numeric(
        big_df["上榜后3天-平均涨幅"], errors="coerce"
    )
    big_df["上榜后3天-上涨概率"] = pd.to_numeric(
        big_df["上榜后3天-上涨概率"], errors="coerce"
    )

    big_df["上榜后5天-买入次数"] = pd.to_numeric(
        big_df["上榜后5天-买入次数"], errors="coerce"
    )
    big_df["上榜后5天-平均涨幅"] = pd.to_numeric(
        big_df["上榜后5天-平均涨幅"], errors="coerce"
    )
    big_df["上榜后5天-上涨概率"] = pd.to_numeric(
        big_df["上榜后5天-上涨概率"], errors="coerce"
    )

    big_df["上榜后10天-买入次数"] = pd.to_numeric(
        big_df["上榜后10天-买入次数"], errors="coerce"
    )
    big_df["上榜后10天-平均涨幅"] = pd.to_numeric(
        big_df["上榜后10天-平均涨幅"], errors="coerce"
    )
    big_df["上榜后10天-上涨概率"] = pd.to_numeric(
        big_df["上榜后10天-上涨概率"], errors="coerce"
    )
    return big_df


def stock_lhb_traderstatistic_em(symbol: str = "近一月") -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-营业部统计
    https://data.eastmoney.com/stock/traderstatistic.html
    :param symbol: choice of {"近一月", "近三月", "近六月", "近一年"}
    :type symbol: str
    :return: 营业部统计
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "近一月": "01",
        "近三月": "02",
        "近六月": "03",
        "近一年": "04",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "AMOUNT,OPERATEDEPT_CODE",
        "sortTypes": "-1,1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_OPERATEDEPT_LIST_STATISTICS",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(STATISTICSCYCLE="{symbol_map[symbol]}")',
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
    big_df.rename(
        columns={
            "index": "序号",
            "OPERATEDEPT_NAME": "营业部名称",
            "AMOUNT": "龙虎榜成交金额",
            "SALES_ONLIST_TIMES": "上榜次数",
            "ACT_BUY": "买入额",
            "TOTAL_BUYER_SALESTIMES": "买入次数",
            "ACT_SELL": "卖出额",
            "TOTAL_SELLER_SALESTIMES": "卖出次数",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "序号",
            "营业部名称",
            "龙虎榜成交金额",
            "上榜次数",
            "买入额",
            "买入次数",
            "卖出额",
            "卖出次数",
        ]
    ]

    big_df["龙虎榜成交金额"] = pd.to_numeric(big_df["龙虎榜成交金额"], errors="coerce")
    big_df["上榜次数"] = pd.to_numeric(big_df["上榜次数"], errors="coerce")
    big_df["买入额"] = pd.to_numeric(big_df["买入额"], errors="coerce")
    big_df["买入次数"] = pd.to_numeric(big_df["买入次数"], errors="coerce")
    big_df["卖出额"] = pd.to_numeric(big_df["卖出额"], errors="coerce")
    big_df["卖出次数"] = pd.to_numeric(big_df["卖出次数"], errors="coerce")
    return big_df


def stock_lhb_stock_detail_date_em(symbol: str = "600077") -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-个股龙虎榜详情-日期
    https://data.eastmoney.com/stock/tradedetail.html
    :param symbol: 股票代码
    :type symbol: str
    :return: 个股龙虎榜详情-日期
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_LHB_BOARDDATE",
        "columns": "SECURITY_CODE,TRADE_DATE,TR_DATE",
        "filter": f'(SECURITY_CODE="{symbol}")',
        "pageNumber": "1",
        "pageSize": "1000",
        "sortTypes": "-1",
        "sortColumns": "TRADE_DATE",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = [
        "序号",
        "股票代码",
        "交易日",
        "-",
    ]
    temp_df = temp_df[
        [
            "序号",
            "股票代码",
            "交易日",
        ]
    ]
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"]).dt.date
    return temp_df


def stock_lhb_stock_detail_em(
    symbol: str = "000788", date: str = "20220315", flag: str = "卖出"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-个股龙虎榜详情
    https://data.eastmoney.com/stock/lhb/600077.html
    :param symbol: 股票代码
    :type symbol: str
    :param date: 查询日期; 需要通过 ak.stock_lhb_stock_detail_date_em(symbol="600077") 接口获取相应股票的有龙虎榜详情数据的日期
    :type date: str
    :param flag: choice of {"买入", "卖出"}
    :type flag: str
    :return: 个股龙虎榜详情
    :rtype: pandas.DataFrame
    """
    flag_map = {
        "买入": "BUY",
        "卖出": "SELL",
    }
    report_map = {
        "买入": "RPT_BILLBOARD_DAILYDETAILSBUY",
        "卖出": "RPT_BILLBOARD_DAILYDETAILSSELL",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": report_map[flag],
        "columns": "ALL",
        "filter": f"""(TRADE_DATE='{'-'.join([date[:4], date[4:6], date[6:]])}')(SECURITY_CODE="{symbol}")""",
        "pageNumber": "1",
        "pageSize": "500",
        "sortTypes": "-1",
        "sortColumns": flag_map[flag],
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1

    if flag == "买入":
        temp_df.columns = [
            "序号",
            "-",
            "-",
            "-",
            "-",
            "交易营业部名称",
            "类型",
            "-",
            "-",
            "-",
            "-",
            "买入金额",
            "卖出金额",
            "净额",
            "-",
            "-",
            "-",
            "-",
            "买入金额-占总成交比例",
            "卖出金额-占总成交比例",
            "-",
        ]
        temp_df = temp_df[
            [
                "序号",
                "交易营业部名称",
                "买入金额",
                "买入金额-占总成交比例",
                "卖出金额",
                "卖出金额-占总成交比例",
                "净额",
                "类型",
            ]
        ]
        temp_df["买入金额"] = pd.to_numeric(temp_df["买入金额"], errors="coerce")
        temp_df["买入金额-占总成交比例"] = pd.to_numeric(
            temp_df["买入金额-占总成交比例"], errors="coerce"
        )
        temp_df["卖出金额"] = pd.to_numeric(temp_df["卖出金额"], errors="coerce")
        temp_df["卖出金额-占总成交比例"] = pd.to_numeric(
            temp_df["卖出金额-占总成交比例"], errors="coerce"
        )
        temp_df.sort_values("类型", inplace=True, ignore_index=True)
        temp_df.reset_index(inplace=True, drop=True)
        temp_df["序号"] = range(1, len(temp_df["序号"]) + 1)
    else:
        temp_df.columns = [
            "序号",
            "-",
            "-",
            "-",
            "-",
            "交易营业部名称",
            "类型",
            "-",
            "-",
            "-",
            "-",
            "买入金额",
            "卖出金额",
            "净额",
            "-",
            "-",
            "-",
            "-",
            "买入金额-占总成交比例",
            "卖出金额-占总成交比例",
            "-",
        ]
        temp_df = temp_df[
            [
                "序号",
                "交易营业部名称",
                "买入金额",
                "买入金额-占总成交比例",
                "卖出金额",
                "卖出金额-占总成交比例",
                "净额",
                "类型",
            ]
        ]
        temp_df["买入金额"] = pd.to_numeric(temp_df["买入金额"], errors="coerce")
        temp_df["买入金额-占总成交比例"] = pd.to_numeric(
            temp_df["买入金额-占总成交比例"], errors="coerce"
        )
        temp_df["卖出金额"] = pd.to_numeric(temp_df["卖出金额"], errors="coerce")
        temp_df["卖出金额-占总成交比例"] = pd.to_numeric(
            temp_df["卖出金额-占总成交比例"], errors="coerce"
        )
        temp_df.sort_values("类型", inplace=True, ignore_index=True)
        temp_df.reset_index(inplace=True, drop=True)
        temp_df["序号"] = range(1, len(temp_df["序号"]) + 1)
    return temp_df


def stock_lhb_yyb_detail_em(symbol: str = "10188715") -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-营业部历史交易明细-营业部交易明细
    https://data.eastmoney.com/stock/lhb/yyb/10188715.html
    :param symbol: 营业部代码, 如 "10188715", 通过 ak.stock_lhb_hyyyb_em() 接口获取
    :type symbol: str
    :return: 营业部交易明细数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "TRADE_DATE,SECURITY_CODE",
        "sortTypes": "-1,1",
        "pageSize": '100',
        "pageNumber": "1",
        "reportName": "RPT_OPERATEDEPT_TRADE_DETAILSNEW",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(OPERATEDEPT_CODE="{symbol}")',
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

    # 检查DataFrame是否为空
    if big_df.empty:
        return pd.DataFrame()

    # 确保列名与实际返回的JSON数据结构一致
    column_map = {
        "OPERATEDEPT_CODE": "营业部代码",
        "OPERATEDEPT_NAME": "营业部名称",
        "TRADE_DATE": "交易日期",
        "D1_CLOSE_ADJCHRATE": "1日后涨跌幅",
        "D2_CLOSE_ADJCHRATE": "2日后涨跌幅",
        "D3_CLOSE_ADJCHRATE": "3日后涨跌幅",
        "D5_CLOSE_ADJCHRATE": "5日后涨跌幅",
        "D10_CLOSE_ADJCHRATE": "10日后涨跌幅",
        "SECURITY_CODE": "股票代码",
        "SECURITY_NAME_ABBR": "股票名称",
        "ACT_BUY": "买入金额",
        "ACT_SELL": "卖出金额",
        "NET_AMT": "净额",
        "EXPLANATION": "上榜原因",
        "D20_CLOSE_ADJCHRATE": "20日后涨跌幅",
        "D30_CLOSE_ADJCHRATE": "30日后涨跌幅",
        "SECUCODE": "证券代码",
        "OPERATEDEPT_CODE_OLD": "营业部旧代码",
        "ORG_NAME_ABBR": "营业部简称",
        "CHANGE_RATE": "涨跌幅"
    }

    # 重命名列
    big_df.rename(columns=column_map, inplace=True)

    # 添加序号列
    big_df.reset_index(inplace=True)
    big_df["序号"] = big_df.index + 1

    # 选择需要的列并排序
    result_columns = [
        "序号",
        "营业部代码",
        "营业部名称",
        "营业部简称",
        "交易日期",
        "股票代码",
        "股票名称",
        "涨跌幅",
        "买入金额",
        "卖出金额",
        "净额",
        "上榜原因",
        "1日后涨跌幅",
        "2日后涨跌幅",
        "3日后涨跌幅",
        "5日后涨跌幅",
        "10日后涨跌幅",
        "20日后涨跌幅",
        "30日后涨跌幅",
    ]

    # 确保所有列都存在
    for col in result_columns:
        if col not in big_df.columns and col != "序号":
            big_df[col] = None

    big_df = big_df[result_columns]

    # 处理日期格式
    big_df["交易日期"] = pd.to_datetime(big_df["交易日期"], errors="coerce").dt.date

    # 处理数值列
    numeric_cols = [
        "涨跌幅", "买入金额", "卖出金额", "净额",
        "1日后涨跌幅", "2日后涨跌幅", "3日后涨跌幅",
        "5日后涨跌幅", "10日后涨跌幅", "20日后涨跌幅", "30日后涨跌幅"
    ]
    for col in numeric_cols:
        big_df[col] = pd.to_numeric(big_df[col], errors="coerce")

    return big_df


if __name__ == "__main__":
    stock_lhb_detail_em_df = stock_lhb_detail_em(
        start_date="20250201", end_date="20250228"
    )
    print(stock_lhb_detail_em_df)

    stock_lhb_stock_statistic_em_df = stock_lhb_stock_statistic_em(symbol="近一月")
    print(stock_lhb_stock_statistic_em_df)

    stock_lhb_stock_statistic_em_df = stock_lhb_stock_statistic_em(symbol="近三月")
    print(stock_lhb_stock_statistic_em_df)

    stock_lhb_stock_statistic_em_df = stock_lhb_stock_statistic_em(symbol="近六月")
    print(stock_lhb_stock_statistic_em_df)

    stock_lhb_stock_statistic_em_df = stock_lhb_stock_statistic_em(symbol="近一年")
    print(stock_lhb_stock_statistic_em_df)

    stock_lhb_jgmmtj_em_df = stock_lhb_jgmmtj_em(
        start_date="20240417", end_date="20240430"
    )
    print(stock_lhb_jgmmtj_em_df)

    stock_lhb_jgstatistic_em_df = stock_lhb_jgstatistic_em(symbol="近一月")
    print(stock_lhb_jgstatistic_em_df)

    stock_lhb_hyyyb_em_df = stock_lhb_hyyyb_em(
        start_date="20240401", end_date="20240430"
    )
    print(stock_lhb_hyyyb_em_df)

    stock_lhb_yybph_em_df = stock_lhb_yybph_em(symbol="近一月")
    print(stock_lhb_yybph_em_df)

    stock_lhb_traderstatistic_em_df = stock_lhb_traderstatistic_em(symbol="近一月")
    print(stock_lhb_traderstatistic_em_df)

    stock_lhb_stock_detail_date_em_df = stock_lhb_stock_detail_date_em(symbol="002901")
    print(stock_lhb_stock_detail_date_em_df)

    stock_lhb_stock_detail_em_df = stock_lhb_stock_detail_em(
        symbol="002901", date="20221012", flag="买入"
    )
    print(stock_lhb_stock_detail_em_df)

    stock_lhb_stock_detail_em_df = stock_lhb_stock_detail_em(
        symbol="600077", date="20070416", flag="买入"
    )
    print(stock_lhb_stock_detail_em_df)

    stock_lhb_yyb_detail_em_df = stock_lhb_yyb_detail_em(symbol="10188715")
    print(stock_lhb_yyb_detail_em_df)
