#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/11/7 18:30
Desc: 基金数据-新发基金-新成立基金
https://fund.eastmoney.com/data/xinfound.html
"""

import pandas as pd
import requests

from akshare.utils import demjson


def fund_new_found_em() -> pd.DataFrame:
    """
    基金数据-新发基金-新成立基金
    https://fund.eastmoney.com/data/xinfound.html
    :return: 新成立基金
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/data/FundNewIssue.aspx"
    params = {
        "t": "xcln",
        "sort": "jzrgq,desc",
        "y": "",
        "page": "1,50000",
        "isbuy": "1",
        "v": "0.4069919776543214",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text.strip("var newfunddata="))
    temp_df = pd.DataFrame(data_json["datas"])
    temp_df.columns = [
        "基金代码",
        "基金简称",
        "发行公司",
        "_",
        "基金类型",
        "募集份额",
        "成立日期",
        "成立来涨幅",
        "基金经理",
        "申购状态",
        "集中认购期",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "优惠费率",
    ]
    temp_df = temp_df[
        [
            "基金代码",
            "基金简称",
            "发行公司",
            "基金类型",
            "集中认购期",
            "募集份额",
            "成立日期",
            "成立来涨幅",
            "基金经理",
            "申购状态",
            "优惠费率",
        ]
    ]
    temp_df["募集份额"] = pd.to_numeric(temp_df["募集份额"], errors="coerce")
    temp_df["成立日期"] = pd.to_datetime(temp_df["成立日期"], errors="coerce").dt.date
    temp_df["成立来涨幅"] = pd.to_numeric(
        temp_df["成立来涨幅"].str.replace(",", ""), errors="coerce"
    )
    temp_df["优惠费率"] = temp_df["优惠费率"].str.strip("%")
    temp_df["优惠费率"] = pd.to_numeric(temp_df["优惠费率"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    fund_new_found_em_df = fund_new_found_em()
    print(fund_new_found_em_df)
