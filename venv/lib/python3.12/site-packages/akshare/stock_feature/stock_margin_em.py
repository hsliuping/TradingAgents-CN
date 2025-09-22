#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/6/14 17:00
Desc: 东方财富网-数据中心-融资融券-融资融券账户统计-两融账户信息
https://www.szse.cn/disclosure/margin/object/index.html
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_margin_account_info() -> pd.DataFrame:
    """
    东方财富网-数据中心-融资融券-融资融券账户统计-两融账户信息
    https://data.eastmoney.com/rzrq/zhtjday.html
    :return: 融资融券账户统计
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPTA_WEB_MARGIN_DAILYTRADE",
        "columns": "ALL",
        "pageNumber": "1",
        "pageSize": "500",
        "sortColumns": "STATISTICS_DATE",
        "sortTypes": "-1",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url=url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    tqdm = get_tqdm()
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update(
            {
                "pageNumber": page,
                "p": page,
                "pageNo": page,
                "pageNum": page,
            }
        )
        r = requests.get(url=url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.rename(
        columns={
            "STATISTICS_DATE": "日期",
            "FIN_BALANCE": "融资余额",
            "LOAN_BALANCE": "融券余额",
            "FIN_BUY_AMT": "融资买入额",
            "LOAN_SELL_AMT": "融券卖出额",
            "SECURITY_ORG_NUM": "证券公司数量",
            "OPERATEDEPT_NUM": "营业部数量",
            "PERSONAL_INVESTOR_NUM": "个人投资者数量",
            "ORG_INVESTOR_NUM": "机构投资者数量",
            "INVESTOR_NUM": "参与交易的投资者数量",
            "MARGINLIAB_INVESTOR_NUM": "有融资融券负债的投资者数量",
            "TOTAL_GUARANTEE": "担保物总价值",
            "AVG_GUARANTEE_RATIO": "平均维持担保比例",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "日期",
            "融资余额",
            "融券余额",
            "融资买入额",
            "融券卖出额",
            "证券公司数量",
            "营业部数量",
            "个人投资者数量",
            "机构投资者数量",
            "参与交易的投资者数量",
            "有融资融券负债的投资者数量",
            "担保物总价值",
            "平均维持担保比例",
        ]
    ]

    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    for item in big_df.columns[1:]:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    big_df.sort_values(["日期"], ignore_index=True, inplace=True)
    return big_df


if __name__ == "__main__":
    stock_margin_account_info_df = stock_margin_account_info()
    print(stock_margin_account_info_df)
