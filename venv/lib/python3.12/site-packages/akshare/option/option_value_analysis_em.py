# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/3/11 17:00
Desc: 东方财富网-数据中心-特色数据-期权价值分析
https://data.eastmoney.com/other/valueAnal.html
"""

import pandas as pd

from akshare.utils.func import fetch_paginated_data


def option_value_analysis_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-期权价值分析
    https://data.eastmoney.com/other/valueAnal.html
    :return: 期权价值分析
    :rtype: pandas.DataFrame
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "fid": "f301",
        "po": "1",
        "pz": "100",
        "pn": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "fields": "f1,f2,f3,f12,f13,f14,f298,f299,f249,f300,f330,f331,f332,f333,f334,f335,f336,f301,f152",
        "fs": "m:10",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.columns = [
        "-",
        "-",
        "最新价",
        "-",
        "期权代码",
        "-",
        "期权名称",
        "-",
        "隐含波动率",
        "时间价值",
        "内在价值",
        "理论价格",
        "到期日",
        "-",
        "-",
        "-",
        "标的名称",
        "标的最新价",
        "-",
        "标的近一年波动率",
    ]
    temp_df = temp_df[
        [
            "期权代码",
            "期权名称",
            "最新价",
            "时间价值",
            "内在价值",
            "隐含波动率",
            "理论价格",
            "标的名称",
            "标的最新价",
            "标的近一年波动率",
            "到期日",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["时间价值"] = pd.to_numeric(temp_df["时间价值"], errors="coerce")
    temp_df["内在价值"] = pd.to_numeric(temp_df["内在价值"], errors="coerce")
    temp_df["隐含波动率"] = pd.to_numeric(temp_df["隐含波动率"], errors="coerce")
    temp_df["理论价格"] = pd.to_numeric(temp_df["理论价格"], errors="coerce")
    temp_df["标的最新价"] = pd.to_numeric(temp_df["标的最新价"], errors="coerce")
    temp_df["标的近一年波动率"] = pd.to_numeric(
        temp_df["标的近一年波动率"], errors="coerce"
    )
    temp_df["到期日"] = pd.to_datetime(
        temp_df["到期日"].astype(str), errors="coerce"
    ).dt.date
    return temp_df


if __name__ == "__main__":
    option_value_analysis_em_df = option_value_analysis_em()
    print(option_value_analysis_em_df)
