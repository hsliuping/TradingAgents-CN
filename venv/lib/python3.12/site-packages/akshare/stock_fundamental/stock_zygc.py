# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/5/6 14:30
Desc: 主营构成
https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/Index?type=web&code=SH688041#
"""

import pandas as pd
import requests


def stock_zygc_em(symbol: str = "SH688041") -> pd.DataFrame:
    """
    东方财富网-个股-主营构成
    https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/Index?type=web&code=SH688041#
    :param symbol: 带市场标识的股票代码
    :type symbol: str
    :return: 主营构成
    :rtype: pandas.DataFrame
    """
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax"
    params = {"code": symbol}
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["zygcfx"])
    temp_df.rename(
        columns={
            "SECUCODE": "-",
            "SECURITY_CODE": "股票代码",
            "REPORT_DATE": "报告日期",
            "MAINOP_TYPE": "分类类型",
            "ITEM_NAME": "主营构成",
            "MAIN_BUSINESS_INCOME": "主营收入",
            "MBI_RATIO": "收入比例",
            "MAIN_BUSINESS_COST": "主营成本",
            "MBC_RATIO": "成本比例",
            "MAIN_BUSINESS_RPOFIT": "主营利润",
            "MBR_RATIO": "利润比例",
            "GROSS_RPOFIT_RATIO": "毛利率",
            "RANK": "-",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "股票代码",
            "报告日期",
            "分类类型",
            "主营构成",
            "主营收入",
            "收入比例",
            "主营成本",
            "成本比例",
            "主营利润",
            "利润比例",
            "毛利率",
        ]
    ]
    temp_df["报告日期"] = pd.to_datetime(temp_df["报告日期"], errors="coerce").dt.date
    temp_df["分类类型"] = temp_df["分类类型"].map(
        {"2": "按产品分类", "3": "按地区分类"}
    )
    temp_df["主营收入"] = pd.to_numeric(temp_df["主营收入"], errors="coerce")
    temp_df["收入比例"] = pd.to_numeric(temp_df["收入比例"], errors="coerce")
    temp_df["主营成本"] = pd.to_numeric(temp_df["主营成本"], errors="coerce")
    temp_df["成本比例"] = pd.to_numeric(temp_df["成本比例"], errors="coerce")
    temp_df["主营利润"] = pd.to_numeric(temp_df["主营利润"], errors="coerce")
    temp_df["利润比例"] = pd.to_numeric(temp_df["利润比例"], errors="coerce")
    temp_df["毛利率"] = pd.to_numeric(temp_df["毛利率"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_zygc_em_df = stock_zygc_em(symbol="SH688041")
    print(stock_zygc_em_df)
