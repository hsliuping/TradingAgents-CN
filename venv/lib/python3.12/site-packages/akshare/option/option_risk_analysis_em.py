# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/3/13 21:50
Desc: 东方财富网-数据中心-特色数据-期权风险分析
https://data.eastmoney.com/other/riskanal.html
"""

import pandas as pd

from akshare.utils.func import fetch_paginated_data


def option_risk_analysis_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-期权风险分析
    https://data.eastmoney.com/other/riskanal.html
    :return: 期权风险分析
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "fid": "f12",
        "po": "1",
        "pz": "100",
        "pn": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fields": "f1,f2,f3,f12,f13,f14,f302,f303,f325,f326,f327,f329,f328,f301,f152,f154",
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
        "-",
        "到期日",
        "杠杆比率",
        "实际杠杆比率",
        "Delta",
        "Gamma",
        "Vega",
        "Theta",
        "Rho",
    ]
    temp_df = temp_df[
        [
            "期权代码",
            "期权名称",
            "最新价",
            "涨跌幅",
            "杠杆比率",
            "实际杠杆比率",
            "Delta",
            "Gamma",
            "Vega",
            "Rho",
            "Theta",
            "到期日",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["杠杆比率"] = pd.to_numeric(temp_df["杠杆比率"], errors="coerce")
    temp_df["实际杠杆比率"] = pd.to_numeric(temp_df["实际杠杆比率"], errors="coerce")
    temp_df["Delta"] = pd.to_numeric(temp_df["Delta"], errors="coerce")
    temp_df["Gamma"] = pd.to_numeric(temp_df["Gamma"], errors="coerce")
    temp_df["Vega"] = pd.to_numeric(temp_df["Vega"], errors="coerce")
    temp_df["Rho"] = pd.to_numeric(temp_df["Rho"], errors="coerce")
    temp_df["Theta"] = pd.to_numeric(temp_df["Theta"], errors="coerce")
    temp_df["到期日"] = pd.to_datetime(
        temp_df["到期日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    return temp_df


if __name__ == "__main__":
    option_risk_analysis_em_df = option_risk_analysis_em()
    print(option_risk_analysis_em_df)
