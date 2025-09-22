#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/1/13 22:30
Desc: 东方财富网-数据中心-大宗交易-市场统计
https://data.eastmoney.com/dzjy/
"""

import pandas as pd
import requests


def stock_dzjy_sctj() -> pd.DataFrame:
    """
    东方财富网-数据中心-大宗交易-市场统计
    https://data.eastmoney.com/dzjy/dzjy_sctj.html
    :return: 市场统计表
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "PRT_BLOCKTRADE_MARKET_STA",
        "columns": "TRADE_DATE,SZ_INDEX,SZ_CHANGE_RATE,BLOCKTRADE_DEAL_AMT,PREMIUM_DEAL_AMT,"
        "PREMIUM_RATIO,DISCOUNT_DEAL_AMT,DISCOUNT_RATIO",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = int(data_json["result"]["pages"])
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.columns = [
        "序号",
        "交易日期",
        "上证指数",
        "上证指数涨跌幅",
        "大宗交易成交总额",
        "溢价成交总额",
        "溢价成交总额占比",
        "折价成交总额",
        "折价成交总额占比",
    ]
    big_df["交易日期"] = pd.to_datetime(big_df["交易日期"], errors="coerce").dt.date
    big_df["上证指数"] = pd.to_numeric(big_df["上证指数"], errors="coerce")
    big_df["上证指数涨跌幅"] = pd.to_numeric(big_df["上证指数涨跌幅"], errors="coerce")
    big_df["大宗交易成交总额"] = pd.to_numeric(
        big_df["大宗交易成交总额"], errors="coerce"
    )
    big_df["溢价成交总额"] = pd.to_numeric(big_df["溢价成交总额"], errors="coerce")
    big_df["溢价成交总额占比"] = pd.to_numeric(
        big_df["溢价成交总额占比"], errors="coerce"
    )
    big_df["折价成交总额"] = pd.to_numeric(big_df["折价成交总额"], errors="coerce")
    big_df["折价成交总额占比"] = pd.to_numeric(
        big_df["折价成交总额占比"], errors="coerce"
    )
    return big_df


def stock_dzjy_mrmx(
    symbol: str = "基金", start_date: str = "20220104", end_date: str = "20220104"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-大宗交易-每日明细
    https://data.eastmoney.com/dzjy/dzjy_mrmx.html
    :param symbol: choice of {'A股', 'B股', '基金', '债券'}
    :type symbol: str
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :return: 每日明细
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "A股": "1",
        "B股": "2",
        "基金": "3",
        "债券": "4",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "SECURITY_CODE",
        "sortTypes": "1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_DATA_BLOCKTRADE",
        "columns": "TRADE_DATE,SECURITY_CODE,SECUCODE,SECURITY_NAME_ABBR,CHANGE_RATE,CLOSE_PRICE,"
        "DEAL_PRICE,PREMIUM_RATIO,DEAL_VOLUME,DEAL_AMT,TURNOVER_RATE,BUYER_NAME,SELLER_NAME,"
        "CHANGE_RATE_1DAYS,CHANGE_RATE_5DAYS,CHANGE_RATE_10DAYS,CHANGE_RATE_20DAYS,BUYER_CODE,SELLER_CODE",
        "source": "WEB",
        "client": "WEB",
        "filter": f"""(SECURITY_TYPE_WEB={symbol_map[symbol]})(TRADE_DATE>=
        '{'-'.join([start_date[:4], start_date[4:6], start_date[6:]])}')(TRADE_DATE<=
        '{'-'.join([end_date[:4], end_date[4:6], end_date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    if not data_json["result"]["data"]:
        return pd.DataFrame()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    if symbol in {"A股"}:
        temp_df.columns = [
            "序号",
            "交易日期",
            "证券代码",
            "-",
            "证券简称",
            "涨跌幅",
            "收盘价",
            "成交价",
            "折溢率",
            "成交量",
            "成交额",
            "成交额/流通市值",
            "买方营业部",
            "卖方营业部",
            "_",
            "_",
            "_",
            "_",
            "_",
            "_",
        ]
        temp_df["交易日期"] = pd.to_datetime(
            temp_df["交易日期"], errors="coerce"
        ).dt.date
        temp_df = temp_df[
            [
                "序号",
                "交易日期",
                "证券代码",
                "证券简称",
                "涨跌幅",
                "收盘价",
                "成交价",
                "折溢率",
                "成交量",
                "成交额",
                "成交额/流通市值",
                "买方营业部",
                "卖方营业部",
            ]
        ]
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["收盘价"] = pd.to_numeric(temp_df["收盘价"], errors="coerce")
        temp_df["成交价"] = pd.to_numeric(temp_df["成交价"], errors="coerce")
        temp_df["折溢率"] = pd.to_numeric(temp_df["折溢率"], errors="coerce")
        temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["成交额/流通市值"] = pd.to_numeric(
            temp_df["成交额/流通市值"], errors="coerce"
        )
    if symbol in {"B股", "基金", "债券"}:
        temp_df.columns = [
            "序号",
            "交易日期",
            "证券代码",
            "-",
            "证券简称",
            "-",
            "-",
            "成交价",
            "-",
            "成交量",
            "成交额",
            "-",
            "买方营业部",
            "卖方营业部",
            "_",
            "_",
            "_",
            "_",
            "_",
            "_",
        ]
        temp_df["交易日期"] = pd.to_datetime(
            temp_df["交易日期"], errors="coerce"
        ).dt.date
        temp_df = temp_df[
            [
                "序号",
                "交易日期",
                "证券代码",
                "证券简称",
                "成交价",
                "成交量",
                "成交额",
                "买方营业部",
                "卖方营业部",
            ]
        ]
        temp_df["成交价"] = pd.to_numeric(temp_df["成交价"], errors="coerce")
        temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    return temp_df


def stock_dzjy_mrtj(
    start_date: str = "20220105", end_date: str = "20220105"
) -> pd.DataFrame:
    """
    东方财富网-数据中心-大宗交易-每日统计
    https://data.eastmoney.com/dzjy/dzjy_mrtj.html
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :return: 每日统计
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "TURNOVERRATE",
        "sortTypes": "-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_BLOCKTRADE_STA",
        "columns": "TRADE_DATE,SECURITY_CODE,SECUCODE,SECURITY_NAME_ABBR,CHANGE_RATE,"
        "CLOSE_PRICE,AVERAGE_PRICE,PREMIUM_RATIO,DEAL_NUM,VOLUME,DEAL_AMT,"
        "TURNOVERRATE,D1_CLOSE_ADJCHRATE,D5_CLOSE_ADJCHRATE,D10_CLOSE_ADJCHRATE,D20_CLOSE_ADJCHRATE",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(TRADE_DATE>='{'-'.join([start_date[:4], start_date[4:6], start_date[6:]])}')(TRADE_DATE<="
        f"'{'-'.join([end_date[:4], end_date[4:6], end_date[6:]])}')",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df.index + 1
    temp_df.columns = [
        "序号",
        "交易日期",
        "证券代码",
        "-",
        "证券简称",
        "涨跌幅",
        "收盘价",
        "成交价",
        "折溢率",
        "成交笔数",
        "成交总量",
        "成交总额",
        "成交总额/流通市值",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df["交易日期"] = pd.to_datetime(temp_df["交易日期"], errors="coerce").dt.date
    temp_df = temp_df[
        [
            "序号",
            "交易日期",
            "证券代码",
            "证券简称",
            "涨跌幅",
            "收盘价",
            "成交价",
            "折溢率",
            "成交笔数",
            "成交总量",
            "成交总额",
            "成交总额/流通市值",
        ]
    ]
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["收盘价"] = pd.to_numeric(temp_df["收盘价"], errors="coerce")
    temp_df["成交价"] = pd.to_numeric(temp_df["成交价"], errors="coerce")
    temp_df["折溢率"] = pd.to_numeric(temp_df["折溢率"], errors="coerce")
    temp_df["成交笔数"] = pd.to_numeric(temp_df["成交笔数"], errors="coerce")
    temp_df["成交总量"] = pd.to_numeric(temp_df["成交总量"], errors="coerce")
    temp_df["成交总额"] = pd.to_numeric(temp_df["成交总额"], errors="coerce")
    temp_df["成交总额/流通市值"] = pd.to_numeric(
        temp_df["成交总额/流通市值"], errors="coerce"
    )
    return temp_df


def stock_dzjy_hygtj(symbol: str = "近三月") -> pd.DataFrame:
    """
    东方财富网-数据中心-大宗交易-活跃 A 股统计
    https://data.eastmoney.com/dzjy/dzjy_hygtj.html
    :param symbol: choice of {'近一月', '近三月', '近六月', '近一年'}
    :type symbol: str
    :return: 活跃 A 股统计
    :rtype: pandas.DataFrame
    """
    period_map = {
        "近一月": "1",
        "近三月": "3",
        "近六月": "6",
        "近一年": "12",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "DEAL_NUM,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_BLOCKTRADE_ACSTA",
        "columns": "SECURITY_CODE,SECUCODE,SECURITY_NAME_ABBR,CLOSE_PRICE,CHANGE_RATE,TRADE_DATE,"
        "DEAL_AMT,PREMIUM_RATIO,SUM_TURNOVERRATE,DEAL_NUM,PREMIUM_TIMES,DISCOUNT_TIMES,"
        "D1_AVG_ADJCHRATE,D5_AVG_ADJCHRATE,D10_AVG_ADJCHRATE,D20_AVG_ADJCHRATE,DATE_TYPE_CODE",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(DATE_TYPE_CODE={period_map[symbol]})",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    for page in range(1, int(total_page) + 1):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "证券代码",
        "_",
        "证券简称",
        "最新价",
        "涨跌幅",
        "最近上榜日",
        "总成交额",
        "折溢率",
        "成交总额/流通市值",
        "上榜次数-总计",
        "上榜次数-溢价",
        "上榜次数-折价",
        "上榜日后平均涨跌幅-1日",
        "上榜日后平均涨跌幅-5日",
        "上榜日后平均涨跌幅-10日",
        "上榜日后平均涨跌幅-20日",
        "_",
    ]
    big_df = big_df[
        [
            "序号",
            "证券代码",
            "证券简称",
            "最新价",
            "涨跌幅",
            "最近上榜日",
            "上榜次数-总计",
            "上榜次数-溢价",
            "上榜次数-折价",
            "总成交额",
            "折溢率",
            "成交总额/流通市值",
            "上榜日后平均涨跌幅-1日",
            "上榜日后平均涨跌幅-5日",
            "上榜日后平均涨跌幅-10日",
            "上榜日后平均涨跌幅-20日",
        ]
    ]
    big_df["最近上榜日"] = pd.to_datetime(big_df["最近上榜日"], errors="coerce").dt.date
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["上榜次数-总计"] = pd.to_numeric(big_df["上榜次数-总计"], errors="coerce")
    big_df["上榜次数-溢价"] = pd.to_numeric(big_df["上榜次数-溢价"], errors="coerce")
    big_df["上榜次数-折价"] = pd.to_numeric(big_df["上榜次数-折价"], errors="coerce")
    big_df["总成交额"] = pd.to_numeric(big_df["总成交额"], errors="coerce")
    big_df["折溢率"] = pd.to_numeric(big_df["折溢率"], errors="coerce")
    big_df["成交总额/流通市值"] = pd.to_numeric(
        big_df["成交总额/流通市值"], errors="coerce"
    )
    big_df["上榜日后平均涨跌幅-1日"] = pd.to_numeric(
        big_df["上榜日后平均涨跌幅-1日"], errors="coerce"
    )
    big_df["上榜日后平均涨跌幅-5日"] = pd.to_numeric(
        big_df["上榜日后平均涨跌幅-5日"], errors="coerce"
    )
    big_df["上榜日后平均涨跌幅-10日"] = pd.to_numeric(
        big_df["上榜日后平均涨跌幅-10日"], errors="coerce"
    )
    big_df["上榜日后平均涨跌幅-20日"] = pd.to_numeric(
        big_df["上榜日后平均涨跌幅-20日"], errors="coerce"
    )
    return big_df


def stock_dzjy_hyyybtj(symbol: str = "近3日") -> pd.DataFrame:
    """
    东方财富网-数据中心-大宗交易-活跃营业部统计
    https://data.eastmoney.com/dzjy/dzjy_hyyybtj.html
    :param symbol: choice of {'当前交易日', '近3日', '近5日', '近10日', '近30日'}
    :type symbol: str
    :return: 活跃营业部统计
    :rtype: pandas.DataFrame
    """
    period_map = {
        "当前交易日": "1",
        "近3日": "3",
        "近5日": "5",
        "近10日": "10",
        "近30日": "30",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "BUYER_NUM,TOTAL_BUYAMT",
        "sortTypes": "-1,-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_BLOCKTRADE_OPERATEDEPTSTATISTICS",
        "columns": "OPERATEDEPT_CODE,OPERATEDEPT_NAME,ONLIST_DATE,STOCK_DETAILS,"
        "BUYER_NUM,SELLER_NUM,TOTAL_BUYAMT,TOTAL_SELLAMT,TOTAL_NETAMT,N_DATE",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(N_DATE=-{period_map[symbol]})",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    for page in range(1, int(total_page) + 1):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "_",
        "营业部名称",
        "最近上榜日",
        "买入的股票",
        "次数总计-买入",
        "次数总计-卖出",
        "成交金额统计-买入",
        "成交金额统计-卖出",
        "成交金额统计-净买入额",
        "_",
    ]
    big_df = big_df[
        [
            "序号",
            "最近上榜日",
            "营业部名称",
            "次数总计-买入",
            "次数总计-卖出",
            "成交金额统计-买入",
            "成交金额统计-卖出",
            "成交金额统计-净买入额",
            "买入的股票",
        ]
    ]
    big_df["最近上榜日"] = pd.to_datetime(big_df["最近上榜日"], errors="coerce").dt.date
    big_df["次数总计-买入"] = pd.to_numeric(big_df["次数总计-买入"], errors="coerce")
    big_df["次数总计-卖出"] = pd.to_numeric(big_df["次数总计-卖出"], errors="coerce")
    big_df["成交金额统计-买入"] = pd.to_numeric(
        big_df["成交金额统计-买入"], errors="coerce"
    )
    big_df["成交金额统计-卖出"] = pd.to_numeric(
        big_df["成交金额统计-卖出"], errors="coerce"
    )
    big_df["成交金额统计-净买入额"] = pd.to_numeric(
        big_df["成交金额统计-净买入额"], errors="coerce"
    )
    return big_df


def stock_dzjy_yybph(symbol: str = "近三月") -> pd.DataFrame:
    """
    东方财富网-数据中心-大宗交易-营业部排行
    https://data.eastmoney.com/dzjy/dzjy_yybph.html
    :param symbol: choice of {'近一月', '近三月', '近六月', '近一年'}
    :type symbol: str
    :return: 营业部排行
    :rtype: pandas.DataFrame
    """
    period_map = {
        "近一月": "30",
        "近三月": "90",
        "近六月": "180",
        "近一年": "360",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "D5_BUYER_NUM,D1_AVERAGE_INCREASE",
        "sortTypes": "-1,-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_BLOCKTRADE_OPERATEDEPT_RANK",
        "columns": "OPERATEDEPT_CODE,OPERATEDEPT_NAME,D1_BUYER_NUM,D1_AVERAGE_INCREASE,"
        "D1_RISE_PROBABILITY,D5_BUYER_NUM,D5_AVERAGE_INCREASE,D5_RISE_PROBABILITY,"
        "D10_BUYER_NUM,D10_AVERAGE_INCREASE,D10_RISE_PROBABILITY,D20_BUYER_NUM,"
        "D20_AVERAGE_INCREASE,D20_RISE_PROBABILITY,N_DATE,RELATED_ORG_CODE",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(N_DATE=-{period_map[symbol]})",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    for page in range(1, int(total_page) + 1):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = big_df.index + 1
    big_df.columns = [
        "序号",
        "_",
        "营业部名称",
        "上榜后1天-买入次数",
        "上榜后1天-平均涨幅",
        "上榜后1天-上涨概率",
        "上榜后5天-买入次数",
        "上榜后5天-平均涨幅",
        "上榜后5天-上涨概率",
        "上榜后10天-买入次数",
        "上榜后10天-平均涨幅",
        "上榜后10天-上涨概率",
        "上榜后20天-买入次数",
        "上榜后20天-平均涨幅",
        "上榜后20天-上涨概率",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "序号",
            "营业部名称",
            "上榜后1天-买入次数",
            "上榜后1天-平均涨幅",
            "上榜后1天-上涨概率",
            "上榜后5天-买入次数",
            "上榜后5天-平均涨幅",
            "上榜后5天-上涨概率",
            "上榜后10天-买入次数",
            "上榜后10天-平均涨幅",
            "上榜后10天-上涨概率",
            "上榜后20天-买入次数",
            "上榜后20天-平均涨幅",
            "上榜后20天-上涨概率",
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
    big_df["上榜后20天-买入次数"] = pd.to_numeric(
        big_df["上榜后20天-买入次数"], errors="coerce"
    )
    big_df["上榜后20天-平均涨幅"] = pd.to_numeric(
        big_df["上榜后20天-平均涨幅"], errors="coerce"
    )
    big_df["上榜后20天-上涨概率"] = pd.to_numeric(
        big_df["上榜后20天-上涨概率"], errors="coerce"
    )
    return big_df


if __name__ == "__main__":
    stock_dzjy_sctj_df = stock_dzjy_sctj()
    print(stock_dzjy_sctj_df)

    stock_dzjy_mrmx_df = stock_dzjy_mrmx(
        symbol="债券", start_date="20220104", end_date="20220104"
    )
    print(stock_dzjy_mrmx_df)

    stock_dzjy_mrtj_df = stock_dzjy_mrtj(start_date="20220105", end_date="20220105")
    print(stock_dzjy_mrtj_df)

    stock_dzjy_hygtj_df = stock_dzjy_hygtj(symbol="近三月")
    print(stock_dzjy_hygtj_df)

    stock_dzjy_hyyybtj_df = stock_dzjy_hyyybtj(symbol="近3日")
    print(stock_dzjy_hyyybtj_df)

    stock_dzjy_yybph_df = stock_dzjy_yybph(symbol="近三月")
    print(stock_dzjy_yybph_df)
