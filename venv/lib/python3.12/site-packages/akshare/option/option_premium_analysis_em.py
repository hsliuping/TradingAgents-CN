# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/3/11 17:00
Desc: 东方财富网-数据中心-特色数据-期权折溢价
https://data.eastmoney.com/other/premium.html
"""

import pandas as pd

from akshare.utils.func import fetch_paginated_data


def option_premium_analysis_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-期权折溢价
    https://data.eastmoney.com/other/premium.html
    :return: 期权折溢价
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "fid": "f250",
        "po": "1",
        "pz": "100",
        "pn": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fields": "f1,f2,f3,f12,f13,f14,f161,f250,f330,f331,f332,f333,f334,f335,f337,f301,f152",
        "fs": "m:10",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.columns = [
        "-",
        "-",
        "最新价",
        "涨跌幅",
        "期权代码",
        "-",
        "期权名称",
        "-",
        "行权价",
        "折溢价率",
        "到期日",
        "-",
        "-",
        "-",
        "标的名称",
        "标的最新价",
        "标的涨跌幅",
        "盈亏平衡价",
    ]
    temp_df = temp_df[
        [
            "期权代码",
            "期权名称",
            "最新价",
            "涨跌幅",
            "行权价",
            "折溢价率",
            "标的名称",
            "标的最新价",
            "标的涨跌幅",
            "盈亏平衡价",
            "到期日",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["行权价"] = pd.to_numeric(temp_df["行权价"], errors="coerce")
    temp_df["折溢价率"] = pd.to_numeric(temp_df["折溢价率"], errors="coerce")
    temp_df["标的最新价"] = pd.to_numeric(temp_df["标的最新价"], errors="coerce")
    temp_df["标的涨跌幅"] = pd.to_numeric(temp_df["标的涨跌幅"], errors="coerce")
    temp_df["盈亏平衡价"] = pd.to_numeric(temp_df["盈亏平衡价"], errors="coerce")
    temp_df["到期日"] = pd.to_datetime(
        temp_df["到期日"].astype(str), errors="coerce"
    ).dt.date
    return temp_df


if __name__ == "__main__":
    option_premium_analysis_em_df = option_premium_analysis_em()
    print(option_premium_analysis_em_df)
