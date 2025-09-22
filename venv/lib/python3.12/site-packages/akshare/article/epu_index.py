#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/20 22:00
Desc: 经济政策不确定性指数
https://www.policyuncertainty.com/index.html
"""

import pandas as pd


def article_epu_index(symbol: str = "China") -> pd.DataFrame:
    """
    经济政策不确定性指数
    https://www.policyuncertainty.com/index.html
    :param symbol: 指定的国家名称, e.g. “China”
    :type symbol: str
    :return: 经济政策不确定性指数数据
    :rtype: pandas.DataFrame
    """
    # 切勿修改 http 否则会读取不到 csv 文件
    if symbol == "China New":
        symbol = "SCMP_China"
    if symbol == "China":
        symbol = "SCMP_China"
    if symbol == "USA":
        symbol = "US"
    if symbol == "Hong Kong":
        symbol = "HK"
        epu_df = pd.read_excel(
            io=f"http://www.policyuncertainty.com/media/{symbol}_EPU_Data_Annotated.xlsx",
            engine="openpyxl",
        )
        return epu_df
    if symbol in ["Germany", "France", "Italy"]:  # 欧洲
        symbol = "Europe"
    if symbol == "South Korea":
        symbol = "Korea"
    if symbol == "Spain New":
        symbol = "Spain"
    if symbol in ["Ireland", "Chile", "Colombia", "Netherlands", "Singapore", "Sweden"]:
        epu_df = pd.read_excel(
            io=f"http://www.policyuncertainty.com/media/{symbol}_Policy_Uncertainty_Data.xlsx",
            engine="openpyxl",
        )
        return epu_df
    if symbol == "Greece":
        epu_df = pd.read_excel(
            io=f"http://www.policyuncertainty.com/media/FKT_{symbol}_Policy_Uncertainty_Data.xlsx",
            engine="openpyxl",
        )
        return epu_df
    url = f"http://www.policyuncertainty.com/media/{symbol}_Policy_Uncertainty_Data.csv"
    epu_df = pd.read_csv(url)
    return epu_df


if __name__ == "__main__":
    article_epu_index_df = article_epu_index(symbol="China")
    print(article_epu_index_df)
