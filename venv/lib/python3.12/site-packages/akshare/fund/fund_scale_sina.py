# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/9/1 16:20
Desc: 新浪财经-基金规模
https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjgmall
"""

import pandas as pd
import requests

from akshare.utils import demjson


def fund_scale_open_sina(symbol: str = "股票型基金") -> pd.DataFrame:
    """
    新浪财经-基金数据中心-基金规模-开放式基金
    https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf
    :param symbol: choice of {"股票型基金", "混合型基金", "债券型基金", "货币型基金", "QDII基金"}
    :type symbol: str
    :return: 基金规模
    :rtype: pandas.DataFrame
    """
    fund_map = {
        "股票型基金": "2",
        "混合型基金": "1",
        "债券型基金": "3",
        "货币型基金": "5",
        "QDII基金": "6",
    }
    url = (
        "http://vip.stock.finance.sina.com.cn/fund_center/data/jsonp.php/IO.XSRV2."
        "CallbackList['J2cW8KXheoWKdSHc']/NetValueReturn_Service.NetValueReturnOpen"
    )
    params = {
        "page": "1",
        "num": "10000",
        "sort": "zmjgm",
        "asc": "0",
        "ccode": "",
        "type2": fund_map[symbol],
        "type3": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("({") + 1 : -2])
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = range(1, len(temp_df) + 1)
    temp_df.rename(
        columns={
            "index": "序号",
            "symbol": "基金代码",
            "sname": "基金简称",
            "per_nav": "-",
            "total_nav": "-",
            "three_month": "-",
            "six_month": "-",
            "one_year": "-",
            "form_year": "-",
            "form_start": "-",
            "name": "-",
            "zmjgm": "总募集规模",
            "clrq": "成立日期",
            "jjjl": "基金经理",
            "dwjz": "单位净值",
            "ljjz": "-",
            "jzrq": "更新日期",
            "zjzfe": "最近总份额",
            "jjglr_code": "-",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "单位净值",
            "总募集规模",
            "最近总份额",
            "成立日期",
            "基金经理",
            "更新日期",
        ]
    ]
    temp_df["成立日期"] = pd.to_datetime(temp_df["成立日期"], errors="coerce").dt.date
    temp_df["更新日期"] = pd.to_datetime(temp_df["更新日期"], errors="coerce").dt.date
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["总募集规模"] = pd.to_numeric(temp_df["总募集规模"], errors="coerce")
    temp_df["最近总份额"] = pd.to_numeric(temp_df["最近总份额"], errors="coerce")
    return temp_df


def fund_scale_close_sina() -> pd.DataFrame:
    """
    新浪财经-基金数据中心-基金规模-封闭式基金
    https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf
    :return: 基金规模
    :rtype: pandas.DataFrame
    """
    url = (
        "http://vip.stock.finance.sina.com.cn/fund_center/data/jsonp.php/IO.XSRV2."
        "CallbackList['_bjN6KvXOkfPy2Bu']/NetValueReturn_Service.NetValueReturnClose"
    )
    params = {
        "page": "1",
        "num": "1000",
        "sort": "zmjgm",
        "asc": "0",
        "ccode": "",
        "type2": "",
        "type3": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("({") + 1 : -2])
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = range(1, len(temp_df) + 1)
    temp_df.rename(
        columns={
            "index": "序号",
            "symbol": "基金代码",
            "sname": "基金简称",
            "per_nav": "-",
            "total_nav": "-",
            "three_month": "-",
            "six_month": "-",
            "one_year": "-",
            "form_year": "-",
            "form_start": "-",
            "name": "-",
            "zmjgm": "总募集规模",
            "clrq": "成立日期",
            "jjjl": "基金经理",
            "dwjz": "单位净值",
            "ljjz": "-",
            "jzrq": "更新日期",
            "zjzfe": "最近总份额",
            "jjglr_code": "-",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "单位净值",
            "总募集规模",
            "最近总份额",
            "成立日期",
            "基金经理",
            "更新日期",
        ]
    ]
    temp_df["成立日期"] = pd.to_datetime(temp_df["成立日期"], errors="coerce").dt.date
    temp_df["更新日期"] = pd.to_datetime(temp_df["更新日期"], errors="coerce").dt.date
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["总募集规模"] = pd.to_numeric(temp_df["总募集规模"], errors="coerce")
    temp_df["最近总份额"] = pd.to_numeric(temp_df["最近总份额"], errors="coerce")
    return temp_df


def fund_scale_structured_sina() -> pd.DataFrame:
    """
    新浪财经-基金数据中心-基金规模-分级子基金
    https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjgmfjall
    :return: 基金规模
    :rtype: pandas.DataFrame
    """
    url = (
        "http://vip.stock.finance.sina.com.cn/fund_center/data/jsonp.php/IO.XSRV2."
        "CallbackList['cRrwseM7NWX68rDa']/NetValueReturn_Service.NetValueReturnCX"
    )
    params = {
        "page": "1",
        "num": "1000",
        "sort": "zmjgm",
        "asc": "0",
        "ccode": "",
        "type2": "",
        "type3": "",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("({") + 1 : -2])
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = range(1, len(temp_df) + 1)
    temp_df.rename(
        columns={
            "index": "序号",
            "symbol": "基金代码",
            "sname": "基金简称",
            "per_nav": "-",
            "total_nav": "-",
            "three_month": "-",
            "six_month": "-",
            "one_year": "-",
            "form_year": "-",
            "form_start": "-",
            "name": "-",
            "zmjgm": "总募集规模",
            "clrq": "成立日期",
            "jjjl": "基金经理",
            "dwjz": "单位净值",
            "ljjz": "-",
            "jzrq": "更新日期",
            "zjzfe": "最近总份额",
            "jjglr_code": "-",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金简称",
            "单位净值",
            "总募集规模",
            "最近总份额",
            "成立日期",
            "基金经理",
            "更新日期",
        ]
    ]
    temp_df["成立日期"] = pd.to_datetime(temp_df["成立日期"], errors="coerce").dt.date
    temp_df["更新日期"] = pd.to_datetime(temp_df["更新日期"], errors="coerce").dt.date
    temp_df["单位净值"] = pd.to_numeric(temp_df["单位净值"], errors="coerce")
    temp_df["总募集规模"] = pd.to_numeric(temp_df["总募集规模"], errors="coerce")
    temp_df["最近总份额"] = pd.to_numeric(temp_df["最近总份额"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    fund_scale_open_sina_df = fund_scale_open_sina(symbol="股票型基金")
    print(fund_scale_open_sina_df)

    fund_scale_close_sina_df = fund_scale_close_sina()
    print(fund_scale_close_sina_df)

    fund_scale_structured_sina_df = fund_scale_structured_sina()
    print(fund_scale_structured_sina_df)

    fund_scale_open_sina_df = fund_scale_open_sina(symbol="股票型基金")
    print(fund_scale_open_sina_df)
