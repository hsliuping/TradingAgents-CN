#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/8/8 21:30
Desc: 东方财富网-数据中心-股市日历
https://data.eastmoney.com/gsrl/gsdt.html
"""

import pandas as pd
import requests


def stock_gsrl_gsdt_em(date: str = "20230808") -> pd.DataFrame:
    """
    东方财富网-数据中心-股市日历-公司动态
    https://data.eastmoney.com/gsrl/gsdt.html
    :param date: 交易日
    :type date: str
    :return: 公司动态
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "SECURITY_CODE",
        "sortTypes": "1",
        "pageSize": "5000",
        "pageNumber": "1",
        "columns": "SECURITY_CODE,SECUCODE,SECURITY_NAME_ABBR,EVENT_TYPE,EVENT_CONTENT,TRADE_DATE",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ORGOP_ALL",
        "filter": f"""(TRADE_DATE='{"-".join([date[:4], date[4:6], date[6:]])}')""",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"]["data"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"] + 1
    temp_df.rename(
        columns={
            "index": "序号",
            "SECURITY_CODE": "代码",
            "SECUCODE": "-",
            "SECURITY_NAME_ABBR": "简称",
            "EVENT_TYPE": "事件类型",
            "EVENT_CONTENT": "具体事项",
            "TRADE_DATE": "交易日",
        },
        inplace=True,
    )

    temp_df = temp_df[
        [
            "序号",
            "代码",
            "简称",
            "事件类型",
            "具体事项",
            "交易日",
        ]
    ]
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"], errors="coerce").dt.date
    return temp_df


if __name__ == "__main__":
    stock_gsrl_gsdt_em_df = stock_gsrl_gsdt_em(date="20230808")
    print(stock_gsrl_gsdt_em_df)
