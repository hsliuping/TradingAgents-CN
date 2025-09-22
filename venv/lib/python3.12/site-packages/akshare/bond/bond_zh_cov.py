#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/7/4 15:00
Desc: 新浪财经-债券-沪深可转债-实时行情数据和历史行情数据
https://vip.stock.finance.sina.com.cn/mkt/#hskzz_z
"""

import datetime
import re

import pandas as pd
import py_mini_racer
import requests

from akshare.bond.cons import (
    zh_sina_bond_hs_cov_count_url,
    zh_sina_bond_hs_cov_payload,
    zh_sina_bond_hs_cov_url,
    zh_sina_bond_hs_cov_hist_url,
)
from akshare.stock.cons import hk_js_decode
from akshare.utils import demjson
from akshare.utils.func import fetch_paginated_data
from akshare.utils.tqdm import get_tqdm


def _get_zh_bond_hs_cov_page_count() -> int:
    """
    新浪财经-行情中心-债券-沪深可转债的总页数
    https://vip.stock.finance.sina.com.cn/mkt/#hskzz_z
    :return: 总页数
    :rtype: int
    """
    params = {
        "node": "hskzz_z",
    }
    r = requests.get(zh_sina_bond_hs_cov_count_url, params=params)
    page_count = int(re.findall(re.compile(r"\d+"), r.text)[0]) / 80
    if isinstance(page_count, int):
        return page_count
    else:
        return int(page_count) + 1


def bond_zh_hs_cov_spot() -> pd.DataFrame:
    """
    新浪财经-债券-沪深可转债的实时行情数据; 大量抓取容易封IP
    https://vip.stock.finance.sina.com.cn/mkt/#hskzz_z
    :return: 所有沪深可转债在当前时刻的实时行情数据
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page_count = _get_zh_bond_hs_cov_page_count()
    zh_sina_bond_hs_payload_copy = zh_sina_bond_hs_cov_payload.copy()
    tqdm = get_tqdm()
    for page in tqdm(range(1, page_count + 1), leave=False):
        zh_sina_bond_hs_payload_copy.update({"page": page})
        res = requests.get(zh_sina_bond_hs_cov_url, params=zh_sina_bond_hs_payload_copy)
        data_json = demjson.decode(res.text)
        big_df = pd.concat(objs=[big_df, pd.DataFrame(data_json)], ignore_index=True)
    return big_df


def bond_zh_hs_cov_daily(symbol: str = "sh010107") -> pd.DataFrame:
    """
    新浪财经-债券-沪深可转债的历史行情数据, 大量抓取容易封 IP
    https://vip.stock.finance.sina.com.cn/mkt/#hskzz_z
    :param symbol: 沪深可转债代码; e.g., sh010107
    :type symbol: str
    :return: 指定沪深可转债代码的日 K 线数据
    :rtype: pandas.DataFrame
    """
    r = requests.get(
        zh_sina_bond_hs_cov_hist_url.format(
            symbol, datetime.datetime.now().strftime("%Y_%m_%d")
        )
    )
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call(
        "d", r.text.split("=")[1].split(";")[0].replace('"', "")
    )  # 执行js解密代码
    data_df = pd.DataFrame(dict_list)
    data_df["date"] = pd.to_datetime(data_df["date"]).dt.date
    return data_df


def _code_id_map() -> dict:
    """
    东方财富-股票和市场代码
    https://quote.eastmoney.com/center/gridlist.html#hs_a_board
    :return: 股票和市场代码
    :rtype: dict
    """
    url = "https://80.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:1 t:2,m:1 t:23",
        "fields": "f3,f12",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df["market_id"] = 1
    temp_df.rename(columns={"f12": "sh_code", "market_id": "sh_id"}, inplace=True)
    code_id_dict = dict(zip(temp_df["sh_code"], temp_df["sh_id"]))
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:0 t:6,m:0 t:80",
        "fields": "f3,f12",
    }
    temp_df_sz = fetch_paginated_data(url, params)
    temp_df_sz["sz_id"] = 0
    code_id_dict.update(dict(zip(temp_df_sz["f12"], temp_df_sz["sz_id"])))
    return code_id_dict


def bond_zh_hs_cov_min(
    symbol: str = "sz128039",
    period: str = "15",
    adjust: str = "",
    start_date: str = "1979-09-01 09:32:00",
    end_date: str = "2222-01-01 09:32:00",
) -> pd.DataFrame:
    """
    东方财富网-可转债-分时行情
    https://quote.eastmoney.com/concept/sz128039.html
    :param symbol: 转债代码
    :type symbol: str
    :param period: choice of {'1', '5', '15', '30', '60'}
    :type period: str
    :param adjust: choice of {'', 'qfq', 'hfq'}
    :type adjust: str
    :param start_date: 开始日期
    :type start_date: str
    :param end_date: 结束日期
    :type end_date: str
    :return: 分时行情
    :rtype: pandas.DataFrame
    """
    market_type = {"sh": "1", "sz": "0"}
    if period == "1":
        url = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
        params = {
            "secid": f"{market_type[symbol[:2]]}.{symbol[2:]}",
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "iscr": "0",
            "iscca": "0",
            "ut": "f057cbcbce2a86e2866ab8877db1d059",
            "ndays": "1",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            [item.split(",") for item in data_json["data"]["trends"]]
        )
        temp_df.columns = [
            "时间",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "最新价",
        ]
        temp_df.index = pd.to_datetime(temp_df["时间"])
        temp_df = temp_df[start_date:end_date]
        temp_df.reset_index(drop=True, inplace=True)
        temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
        temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
        temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
        temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
        temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
        temp_df["时间"] = pd.to_datetime(temp_df["时间"]).astype(
            str
        )  # show datatime here
        return temp_df
    else:
        adjust_map = {
            "": "0",
            "qfq": "1",
            "hfq": "2",
        }
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": f"{market_type[symbol[:2]]}.{symbol[2:]}",
            "klt": period,
            "fqt": adjust_map[adjust],
            "lmt": "66",
            "end": "20500000",
            "iscca": "1",
            "fields1": "f1,f2,f3,f4,f5",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "forcect": "1",
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(
            [item.split(",") for item in data_json["data"]["klines"]]
        )
        temp_df.columns = [
            "时间",
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
        temp_df.index = pd.to_datetime(temp_df["时间"])
        temp_df = temp_df[start_date:end_date]
        temp_df.reset_index(drop=True, inplace=True)
        temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
        temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
        temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
        temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
        temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
        temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
        temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
        temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
        temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
        temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
        temp_df["时间"] = pd.to_datetime(temp_df["时间"]).astype(str)
        temp_df = temp_df[
            [
                "时间",
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
        return temp_df


def bond_zh_hs_cov_pre_min(symbol: str = "sh113570") -> pd.DataFrame:
    """
    东方财富网-可转债-分时行情-盘前
    https://quote.eastmoney.com/concept/sz128039.html
    :param symbol: 转债代码
    :type symbol: str
    :return: 分时行情-盘前
    :rtype: pandas.DataFrame
    """
    market_type = {"sh": "1", "sz": "0"}
    url = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "ndays": "1",
        "iscr": "1",
        "iscca": "0",
        "secid": f"{market_type[symbol[:2]]}.{symbol[2:]}",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["trends"]])
    temp_df.columns = [
        "时间",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "最新价",
    ]
    temp_df.index = pd.to_datetime(temp_df["时间"])
    temp_df.reset_index(drop=True, inplace=True)
    temp_df["开盘"] = pd.to_numeric(temp_df["开盘"], errors="coerce")
    temp_df["收盘"] = pd.to_numeric(temp_df["收盘"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["时间"] = pd.to_datetime(temp_df["时间"]).astype(str)
    return temp_df


def bond_zh_cov() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-可转债数据
    https://data.eastmoney.com/kzz/default.html
    :return: 可转债数据
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "PUBLIC_START_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_BOND_CB_LIST",
        "columns": "ALL",
        "quoteColumns": "f2~01~CONVERT_STOCK_CODE~CONVERT_STOCK_PRICE,"
                        "f235~10~SECURITY_CODE~TRANSFER_PRICE,f236~10~SECURITY_CODE~TRANSFER_VALUE,"
                        "f2~10~SECURITY_CODE~CURRENT_BOND_PRICE,f237~10~SECURITY_CODE~TRANSFER_PREMIUM_RATIO,"
                        "f239~10~SECURITY_CODE~RESALE_TRIG_PRICE,f240~10~SECURITY_CODE~REDEEM_TRIG_PRICE,"
                        "f23~01~CONVERT_STOCK_CODE~PBV_RATIO",
        "source": "WEB",
        "client": "WEB",
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

    big_df.columns = [
        "债券代码",
        "_",
        "_",
        "债券简称",
        "_",
        "上市时间",
        "正股代码",
        "_",
        "信用评级",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "发行规模",
        "申购上限",
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
        "_",
        "_",
        "_",
        "申购代码",
        "_",
        "申购日期",
        "_",
        "_",
        "中签号发布日",
        "原股东配售-股权登记日",
        "正股简称",
        "原股东配售-每股配售额",
        "_",
        "中签率",
        "-",
        "_",
        "_",
        "_",
        "_",
        "_",
        "正股价",
        "转股价",
        "转股价值",
        "债现价",
        "转股溢价率",
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
    big_df = big_df[
        [
            "债券代码",
            "债券简称",
            "申购日期",
            "申购代码",
            "申购上限",
            "正股代码",
            "正股简称",
            "正股价",
            "转股价",
            "转股价值",
            "债现价",
            "转股溢价率",
            "原股东配售-股权登记日",
            "原股东配售-每股配售额",
            "发行规模",
            "中签号发布日",
            "中签率",
            "上市时间",
            "信用评级",
        ]
    ]

    big_df["申购上限"] = pd.to_numeric(big_df["申购上限"], errors="coerce")
    big_df["正股价"] = pd.to_numeric(big_df["正股价"], errors="coerce")
    big_df["转股价"] = pd.to_numeric(big_df["转股价"], errors="coerce")
    big_df["转股价值"] = pd.to_numeric(big_df["转股价值"], errors="coerce")
    big_df["债现价"] = pd.to_numeric(big_df["债现价"], errors="coerce")
    big_df["转股溢价率"] = pd.to_numeric(big_df["转股溢价率"], errors="coerce")
    big_df["原股东配售-每股配售额"] = pd.to_numeric(
        big_df["原股东配售-每股配售额"], errors="coerce"
    )
    big_df["发行规模"] = pd.to_numeric(big_df["发行规模"], errors="coerce")
    big_df["中签率"] = pd.to_numeric(big_df["中签率"], errors="coerce")
    big_df["中签号发布日"] = pd.to_datetime(
        big_df["中签号发布日"], errors="coerce"
    ).dt.date
    big_df["上市时间"] = pd.to_datetime(big_df["上市时间"], errors="coerce").dt.date
    big_df["申购日期"] = pd.to_datetime(big_df["申购日期"], errors="coerce").dt.date
    big_df["原股东配售-股权登记日"] = pd.to_datetime(
        big_df["原股东配售-股权登记日"], errors="coerce"
    ).dt.date
    big_df["债现价"] = big_df["债现价"].fillna(100)
    return big_df


def bond_cov_comparison() -> pd.DataFrame:
    """
    东方财富网-行情中心-债券市场-可转债比价表
    https://quote.eastmoney.com/center/fullscreenlist.html#convertible_comparison
    :return: 可转债比价表数据
    :rtype: pandas.DataFrame
    """
    url = "https://16.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f243",
        "fs": "b:MK0354",
        "fields": "f1,f152,f2,f3,f12,f13,f14,f227,f228,f229,f230,f231,f232,f233,f234,"
                  "f235,f236,f237,f238,f239,f240,f241,f242,f26,f243",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.columns = [
        "序号",
        "_",
        "转债最新价",
        "转债涨跌幅",
        "转债代码",
        "_",
        "转债名称",
        "上市日期",
        "_",
        "纯债价值",
        "_",
        "正股最新价",
        "正股涨跌幅",
        "_",
        "正股代码",
        "_",
        "正股名称",
        "转股价",
        "转股价值",
        "转股溢价率",
        "纯债溢价率",
        "回售触发价",
        "强赎触发价",
        "到期赎回价",
        "开始转股日",
        "申购日期",
    ]
    temp_df = temp_df[
        [
            "序号",
            "转债代码",
            "转债名称",
            "转债最新价",
            "转债涨跌幅",
            "正股代码",
            "正股名称",
            "正股最新价",
            "正股涨跌幅",
            "转股价",
            "转股价值",
            "转股溢价率",
            "纯债溢价率",
            "回售触发价",
            "强赎触发价",
            "到期赎回价",
            "纯债价值",
            "开始转股日",
            "上市日期",
            "申购日期",
        ]
    ]
    return temp_df


def bond_zh_cov_info(
    symbol: str = "123121", indicator: str = "基本信息"
) -> pd.DataFrame:
    """
    https://data.eastmoney.com/kzz/detail/123121.html
    东方财富网-数据中心-新股数据-可转债详情
    :param symbol: 可转债代码
    :type symbol: str
    :param indicator: choice of {"基本信息", "中签号", "筹资用途", "重要日期"}
    :type indicator: str
    :return: 可转债详情
    :rtype: pandas.DataFrame
    """
    indicator_map = {
        "基本信息": "RPT_BOND_CB_LIST",
        "中签号": "RPT_CB_BALLOTNUM",
        "筹资用途": "RPT_BOND_BS_OPRFINVESTITEM",
        "重要日期": "RPT_CB_IMPORTANTDATE",
    }
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_BOND_CB_LIST",
        "columns": "ALL",
        "quoteColumns": "f2~01~CONVERT_STOCK_CODE~CONVERT_STOCK_PRICE,f235~10~SECURITY_CODE~TRANSFER_PRICE,"
                        "f236~10~SECURITY_CODE~TRANSFER_VALUE,f2~10~SECURITY_CODE~CURRENT_BOND_PRICE,"
                        "f237~10~SECURITY_CODE~TRANSFER_PREMIUM_RATIO,f239~10~SECURITY_CODE~RESALE_TRIG_PRICE,"
                        "f240~10~SECURITY_CODE~REDEEM_TRIG_PRICE,f23~01~CONVERT_STOCK_CODE~PBV_RATIO",
        "quoteType": "0",
        "source": "WEB",
        "client": "WEB",
        "filter": f'(SECURITY_CODE="{symbol}")',
    }
    if indicator == "基本信息":
        params.update(
            {
                "reportName": indicator_map[indicator],
                "quoteColumns": "f2~01~CONVERT_STOCK_CODE~CONVERT_STOCK_PRICE,f235~10~SECURITY_CODE~TRANSFER_PRICE,"
                                "f236~10~SECURITY_CODE~TRANSFER_VALUE,f2~10~SECURITY_CODE~CURRENT_BOND_PRICE,"
                                "f237~10~SECURITY_CODE~TRANSFER_PREMIUM_RATIO,f239~10~SECURITY_CODE~RESALE_TRIG_PRICE,"
                                "f240~10~SECURITY_CODE~REDEEM_TRIG_PRICE,f23~01~CONVERT_STOCK_CODE~PBV_RATIO",
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame.from_dict(data_json["result"]["data"])
        return temp_df
    elif indicator == "中签号":
        params.update(
            {
                "reportName": indicator_map[indicator],
                "quoteColumns": "",
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame.from_dict(data_json["result"]["data"])
        return temp_df
    elif indicator == "筹资用途":
        params.update(
            {
                "reportName": indicator_map[indicator],
                "quoteColumns": "",
                "sortColumns": "SORT",
                "sortTypes": "1",
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame.from_dict(data_json["result"]["data"])
        return temp_df
    elif indicator == "重要日期":
        params.update(
            {
                "reportName": indicator_map[indicator],
                "quoteColumns": "",
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame.from_dict(data_json["result"]["data"])
        return temp_df
    else:
        return pd.DataFrame()


def bond_zh_cov_value_analysis(symbol: str = "113527") -> pd.DataFrame:
    """
    https://data.eastmoney.com/kzz/detail/113527.html
    东方财富网-数据中心-新股数据-可转债数据-价值分析-溢价率分析
    :return: 可转债价值分析
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/get"
    params = {
        "sty": "ALL",
        "token": "894050c76af8597a853f5b408b759f5d",
        "st": "date",
        "sr": "1",
        "source": "WEB",
        "type": "RPTA_WEB_KZZ_LS",
        "filter": f'(zcode="{symbol}")',
        "p": "1",
        "ps": "8000",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.columns = [
        "日期",
        "-",
        "-",
        "转股价值",
        "纯债价值",
        "纯债溢价率",
        "转股溢价率",
        "收盘价",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "日期",
            "收盘价",
            "纯债价值",
            "转股价值",
            "纯债溢价率",
            "转股溢价率",
        ]
    ]
    temp_df["收盘价"] = pd.to_numeric(temp_df["收盘价"], errors="coerce")
    temp_df["纯债价值"] = pd.to_numeric(temp_df["纯债价值"], errors="coerce")
    temp_df["转股价值"] = pd.to_numeric(temp_df["转股价值"], errors="coerce")
    temp_df["纯债溢价率"] = pd.to_numeric(temp_df["纯债溢价率"], errors="coerce")
    temp_df["转股溢价率"] = pd.to_numeric(temp_df["转股溢价率"], errors="coerce")
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    return temp_df


if __name__ == "__main__":
    bond_zh_hs_cov_min_df = bond_zh_hs_cov_min(
        symbol="sz128039",
        period="1",
        adjust="hfq",
        start_date="1979-09-01 09:32:00",
        end_date="2222-01-01 09:32:00",
    )
    print(bond_zh_hs_cov_min_df)

    bond_zh_hs_cov_pre_min_df = bond_zh_hs_cov_pre_min(symbol="sz128039")
    print(bond_zh_hs_cov_pre_min_df)

    bond_zh_hs_cov_daily_df = bond_zh_hs_cov_daily(symbol="sz128039")
    print(bond_zh_hs_cov_daily_df)

    bond_zh_hs_cov_spot_df = bond_zh_hs_cov_spot()
    print(bond_zh_hs_cov_spot_df)

    bond_zh_cov_df = bond_zh_cov()
    print(bond_zh_cov_df)

    bond_cov_comparison_df = bond_cov_comparison()
    print(bond_cov_comparison_df)

    bond_zh_cov_info_df = bond_zh_cov_info(symbol="123121", indicator="基本信息")
    print(bond_zh_cov_info_df)

    bond_zh_cov_value_analysis_df = bond_zh_cov_value_analysis(symbol="113527")
    print(bond_zh_cov_value_analysis_df)
