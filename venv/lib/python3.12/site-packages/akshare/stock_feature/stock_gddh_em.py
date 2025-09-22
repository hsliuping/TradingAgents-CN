#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/11 16:00
Desc: 东方财富网-数据中心-股东大会
https://data.eastmoney.com/gddh/
"""

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm


def stock_gddh_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-股东大会
    https://data.eastmoney.com/gddh/
    :return: 股东大会
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "NOTICE_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_GENERALMEETING_DETAIL",
        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,MEETING_TITLE,START_ADJUST_DATE,EQUITY_RECORD_DATE,"
        "ONSITE_RECORD_DATE,DECISION_NOTICE_DATE,NOTICE_DATE,WEB_START_DATE,"
        "WEB_END_DATE,SERIAL_NUM,PROPOSAL",
        "filter": '(IS_LASTDATE="1")',
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
            }
        )
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], axis=0, ignore_index=True)
    big_df.rename(
        columns={
            "SECURITY_CODE": "代码",
            "SECURITY_NAME_ABBR": "简称",
            "MEETING_TITLE": "股东大会名称",
            "START_ADJUST_DATE": "召开开始日",
            "EQUITY_RECORD_DATE": "股权登记日",
            "ONSITE_RECORD_DATE": "现场登记日",
            "DECISION_NOTICE_DATE": "决议公告日",
            "NOTICE_DATE": "公告日",
            "WEB_START_DATE": "网络投票时间-开始日",
            "WEB_END_DATE": "网络投票时间-结束日",
            "SERIAL_NUM": "序列号",
            "PROPOSAL": "提案",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "代码",
            "简称",
            "股东大会名称",
            "召开开始日",
            "股权登记日",
            "现场登记日",
            "网络投票时间-开始日",
            "网络投票时间-结束日",
            "决议公告日",
            "公告日",
            "序列号",
            "提案",
        ]
    ]
    big_df["召开开始日"] = pd.to_datetime(big_df["召开开始日"], errors="coerce").dt.date
    big_df["股权登记日"] = pd.to_datetime(big_df["股权登记日"], errors="coerce").dt.date
    big_df["现场登记日"] = pd.to_datetime(big_df["现场登记日"], errors="coerce").dt.date
    big_df["网络投票时间-开始日"] = pd.to_datetime(
        big_df["网络投票时间-开始日"], errors="coerce"
    ).dt.date
    big_df["网络投票时间-结束日"] = pd.to_datetime(
        big_df["网络投票时间-结束日"], errors="coerce"
    ).dt.date
    big_df["决议公告日"] = pd.to_datetime(big_df["决议公告日"], errors="coerce").dt.date
    big_df["公告日"] = pd.to_datetime(big_df["公告日"], errors="coerce").dt.date
    big_df["提案"] = big_df["提案"].str.replace("\r\n2", "").str.replace("\r\n3", "")
    return big_df


if __name__ == "__main__":
    stock_gddh_em_df = stock_gddh_em()
    print(stock_gddh_em_df)
