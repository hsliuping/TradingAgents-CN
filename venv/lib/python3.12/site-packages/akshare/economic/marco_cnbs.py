#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/8/14 11:10
Desc: 国家金融与发展实验室-中国宏观杠杆率数据
http://114.115.232.154:8080/
"""

import pandas as pd


def macro_cnbs() -> pd.DataFrame:
    """
    国家金融与发展实验室-中国宏观杠杆率数据
    http://114.115.232.154:8080/
    :return: 中国宏观杠杆率数据
    :rtype: pandas.DataFrame
    """
    url = "http://114.115.232.154:8080/handler/download.ashx"
    temp_df = pd.read_excel(
        url, sheet_name="Data", header=0, skiprows=1, engine="openpyxl"
    )

    temp_df["Period"] = pd.to_datetime(temp_df["Period"]).dt.strftime("%Y-%m")
    temp_df.dropna(axis=1, inplace=True)

    temp_df.rename(
        columns={
            "Period": "年份",
            "Household": "居民部门",
            "Non-financial corporations": "非金融企业部门",
            "Central government ": "中央政府",
            "Local government": "地方政府",
            "General government": "政府部门",
            "Non financial sector": "实体经济部门",
            "Financial sector(asset side)": "金融部门资产方",
            "Financial sector(liability side)": "金融部门负债方",
        },
        inplace=True,
    )

    column_order = [
        "年份",
        "居民部门",
        "非金融企业部门",
        "政府部门",
        "中央政府",
        "地方政府",
        "实体经济部门",
        "金融部门资产方",
        "金融部门负债方",
    ]
    temp_df = temp_df.reindex(columns=column_order)
    temp_df["居民部门"] = pd.to_numeric(temp_df["居民部门"], errors="coerce")
    temp_df["非金融企业部门"] = pd.to_numeric(
        temp_df["非金融企业部门"], errors="coerce"
    )
    temp_df["政府部门"] = pd.to_numeric(temp_df["政府部门"], errors="coerce")
    temp_df["中央政府"] = pd.to_numeric(temp_df["中央政府"], errors="coerce")
    temp_df["地方政府"] = pd.to_numeric(temp_df["地方政府"], errors="coerce")
    temp_df["实体经济部门"] = pd.to_numeric(temp_df["实体经济部门"], errors="coerce")
    temp_df["金融部门资产方"] = pd.to_numeric(
        temp_df["金融部门资产方"], errors="coerce"
    )
    temp_df["金融部门负债方"] = pd.to_numeric(
        temp_df["金融部门负债方"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    macro_cnbs_df = macro_cnbs()
    print(macro_cnbs_df)
