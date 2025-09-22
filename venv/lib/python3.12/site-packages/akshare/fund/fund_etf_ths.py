#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/21 17:00
Desc: 同花顺理财-基金数据-每日净值-ETF
https://fund.10jqka.com.cn/datacenter/jz/kfs/etf/
"""

import json

import pandas as pd
import requests


def fund_etf_spot_ths(date: str = "") -> pd.DataFrame:
    """
    同花顺理财-基金数据-每日净值-ETF-实时行情
    https://fund.10jqka.com.cn/datacenter/jz/kfs/etf/
    :return: ETF 实时行情
    :rtype: pandas.DataFrame
    """
    inner_date = "-".join([date[:4], date[4:6], date[6:]]) if date != "" else 0
    url = f"https://fund.10jqka.com.cn/data/Net/info/ETF_rate_desc_{inner_date}_0_1_9999_0_0_0_jsonp_g.html"
    r = requests.get(url, timeout=15)
    data_text = r.text[2:-1]
    data_json = json.loads(data_text)
    temp_df = pd.DataFrame(data_json["data"]["data"]).T
    temp_df.reset_index(inplace=True, drop=True)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"] + 1
    temp_df.rename(
        columns={
            "index": "序号",
            "code": "基金代码",
            "typename": "基金类型",
            "net": "当前-单位净值",
            "name": "基金名称",
            "totalnet": "当前-累计净值",
            "newnet": "最新-单位净值",
            "newtotalnet": "最新-累计净值",
            "newdate": "最新-交易日",
            "net1": "前一日-单位净值",
            "totalnet1": "前一日-累计净值",
            "ranges": "增长值",
            "rate": "增长率",
            "shstat": "赎回状态",
            "sgstat": "申购状态",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "序号",
            "基金代码",
            "基金名称",
            "当前-单位净值",
            "当前-累计净值",
            "前一日-单位净值",
            "前一日-累计净值",
            "增长值",
            "增长率",
            "赎回状态",
            "申购状态",
            "最新-交易日",
            "最新-单位净值",
            "最新-累计净值",
            "基金类型",
        ]
    ]
    query_date = inner_date if inner_date != 0 else temp_df["最新-交易日"][0]
    temp_df["查询日期"] = query_date
    temp_df["查询日期"] = pd.to_datetime(temp_df["查询日期"], errors="coerce").dt.date
    temp_df["当前-单位净值"] = pd.to_numeric(temp_df["当前-单位净值"], errors="coerce")
    temp_df["当前-累计净值"] = pd.to_numeric(temp_df["当前-累计净值"], errors="coerce")
    temp_df["前一日-单位净值"] = pd.to_numeric(
        temp_df["前一日-单位净值"], errors="coerce"
    )
    temp_df["前一日-累计净值"] = pd.to_numeric(
        temp_df["前一日-累计净值"], errors="coerce"
    )
    temp_df["增长值"] = pd.to_numeric(temp_df["增长值"], errors="coerce")
    temp_df["增长率"] = pd.to_numeric(temp_df["增长率"], errors="coerce")
    temp_df["最新-单位净值"] = pd.to_numeric(temp_df["最新-单位净值"], errors="coerce")
    temp_df["最新-累计净值"] = pd.to_numeric(temp_df["最新-累计净值"], errors="coerce")
    temp_df["最新-交易日"] = pd.to_datetime(
        temp_df["最新-交易日"], errors="coerce"
    ).dt.date
    return temp_df


if __name__ == "__main__":
    fund_etf_spot_ths_df = fund_etf_spot_ths(date="20240620")
    print(fund_etf_spot_ths_df)
