#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/29 15:00
Desc: 东方财富网-数据中心-特色数据-停复牌信息
https://data.eastmoney.com/tfpxx/
"""

import pandas as pd
import requests


def stock_tfp_em(date: str = "20240426") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-停复牌信息
    https://data.eastmoney.com/tfpxx/
    :param date: 查询参数 "20240426"
    :type date: str
    :return: 停复牌信息表
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "SUSPEND_START_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_CUSTOM_SUSPEND_DATA_INTERFACE",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"""(MARKET="全部")(DATETIME='{"-".join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    for page in range(1, total_page + 1):
        params.update({"pageNumber": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df.columns = [
        "序号",
        "代码",
        "名称",
        "停牌时间",
        "停牌截止时间",
        "停牌期限",
        "停牌原因",
        "所属市场",
        "停牌开始日期",
        "预计复牌时间",
        "-",
        "-",
        "-",
    ]
    big_df = big_df[
        [
            "序号",
            "代码",
            "名称",
            "停牌时间",
            "停牌截止时间",
            "停牌期限",
            "停牌原因",
            "所属市场",
            "预计复牌时间",
        ]
    ]
    big_df["停牌时间"] = pd.to_datetime(big_df["停牌时间"], errors="coerce").dt.date
    big_df["停牌截止时间"] = pd.to_datetime(
        big_df["停牌截止时间"], errors="coerce"
    ).dt.date
    big_df["预计复牌时间"] = pd.to_datetime(
        big_df["预计复牌时间"], errors="coerce"
    ).dt.date
    return big_df


if __name__ == "__main__":
    stock_tfp_em_df = stock_tfp_em(date="20240426")
    print(stock_tfp_em_df)
