#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/7 15:00
Desc: 东方财富网-数据中心-研究报告-盈利预测
https://data.eastmoney.com/report/profitforecast.jshtml
"""

from io import StringIO

import pandas as pd
import requests


def stock_hk_profit_forecast_et(
    symbol: str = "09999", indicator: str = "盈利预测概览"
) -> pd.DataFrame:
    """
    经济通-公司资料-盈利预测
    https://www.etnet.com.hk/www/sc/stocks/realtime/quote_profit.php?code=9999
    :param symbol: 股票代码
    :type symbol: str
    :param indicator: "盈利预测概览"; choice of {"评级总览", "去年度业绩表现", "综合盈利预测", "盈利预测概览"}
    :type indicator: str
    :return: 盈利预测
    :rtype: pandas.DataFrame
    """
    url = "https://www.etnet.com.hk/www/sc/stocks/realtime/quote_profit.php"
    params = {
        "code": str(int(symbol)),
    }
    r = requests.get(url, params=params)
    if indicator == "评级总览":
        temp_df = pd.read_html(StringIO(r.text))[0]
        inner_list = [item for item in temp_df.iloc[0, 0].split(" ") if item != ""]
        inner_list.remove("平均评级")
        temp_df = pd.DataFrame(inner_list).T
        temp_df.columns = ["方向", "评级数量", "平均评级"]
        return temp_df
    elif indicator == "去年度业绩表现":
        temp_df = pd.read_html(StringIO(r.text))[2]
        temp_df_upper = temp_df.iloc[:, :2].copy()
        temp_df_upper.reset_index(inplace=True, drop=True)
        temp_df_upper.columns = ["item", "value"]
        temp_df_down = temp_df.iloc[:, 3:].copy()
        temp_df_down.reset_index(inplace=True, drop=True)
        temp_df_down.columns = ["item", "value"]
        temp_df = pd.concat(objs=[temp_df_upper, temp_df_down], ignore_index=True)
        return temp_df
    elif indicator == "综合盈利预测":
        temp_df = pd.read_html(StringIO(r.text), header=0)[3]
        temp_df.rename(
            columns={
                "纯利/(亏损)  (百万元人民币)": "纯利/亏损",
                "纯利/(亏损)  (百万港元)": "纯利/亏损",
                "每股盈利/  (亏损)(分)": "每股盈利/每股亏损",
                "每股盈利/  (亏损)(港仙)": "每股盈利/每股亏损",
                "每股派息  (分)": "每股派息",
                "每股派息  (港仙)": "每股派息",
                "每股资产净值  (人民币元)": "每股资产净值",
                "每股资产净值  (港元)": "每股资产净值",
                "最高  (百万元人民币)": "最高",
                "最高  (百万港元)": "最高",
                "最低  (百万元人民币)": "最低",
                "最低  (百万港元)": "最低",
            },
            inplace=True,
        )
        temp_df["纯利/亏损"] = pd.to_numeric(temp_df["纯利/亏损"], errors="coerce")
        temp_df["每股盈利/每股亏损"] = pd.to_numeric(
            temp_df["每股盈利/每股亏损"], errors="coerce"
        )
        temp_df["每股派息"] = pd.to_numeric(temp_df["每股派息"], errors="coerce")
        temp_df["每股资产净值"] = pd.to_numeric(
            temp_df["每股资产净值"], errors="coerce"
        )
        temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
        temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
        return temp_df
    elif indicator == "盈利预测概览":
        temp_df = pd.read_html(StringIO(r.text), header=0)[4]
        del temp_df["目标价* (港元).1"]
        temp_df.rename(
            columns={
                "纯利/(亏损)  (百万元人民币)": "纯利/亏损",
                "纯利/(亏损)  (百万港元)": "纯利/亏损",
                "每股盈利*/ (亏损)  (港仙)": "每股盈利",
                "每股盈利*/ (亏损)  (分)": "每股盈利",
                "每股派息*  (分)": "每股派息",
                "每股派息*  (港仙)": "每股派息",
                "目标价* (港元)": "目标价",
            },
            inplace=True,
        )
        temp_df.dropna(inplace=True)
        temp_df["纯利/亏损"] = pd.to_numeric(temp_df["纯利/亏损"], errors="coerce")
        temp_df["每股盈利"] = pd.to_numeric(temp_df["每股盈利"], errors="coerce")
        temp_df["每股派息"] = pd.to_numeric(temp_df["每股派息"], errors="coerce")
        temp_df["目标价"] = pd.to_numeric(temp_df["目标价"], errors="coerce")
        temp_df["更新日期"] = pd.to_datetime(
            temp_df["更新日期"], errors="coerce", dayfirst=True
        ).dt.date
        temp_df["财政年度"] = temp_df["财政年度"].astype(int).astype(str)
        return temp_df


if __name__ == "__main__":
    stock_hk_profit_forecast_et_df = stock_hk_profit_forecast_et(
        symbol="09999", indicator="评级总览"
    )
    print(stock_hk_profit_forecast_et_df)

    stock_hk_profit_forecast_et_df = stock_hk_profit_forecast_et(
        symbol="09999", indicator="去年度业绩表现"
    )
    print(stock_hk_profit_forecast_et_df)

    stock_hk_profit_forecast_et_df = stock_hk_profit_forecast_et(
        symbol="09999", indicator="综合盈利预测"
    )
    print(stock_hk_profit_forecast_et_df)

    stock_hk_profit_forecast_et_df = stock_hk_profit_forecast_et(
        symbol="09999", indicator="盈利预测概览"
    )
    print(stock_hk_profit_forecast_et_df)
