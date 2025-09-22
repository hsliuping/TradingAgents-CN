#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/4 18:20
Desc: 增发和配股
东方财富网-数据中心-新股数据-增发-全部增发
https://data.eastmoney.com/other/gkzf.html
东方财富网-数据中心-新股数据-配股
https://data.eastmoney.com/xg/pg/
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_qbzf_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-增发-全部增发
    https://data.eastmoney.com/other/gkzf.html
    :return: 全部增发
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "ISSUE_DATE",
        "sortTypes": "-1",
        "pageSize": "500",
        "pageNumber": "1",
        "reportName": "RPT_SEO_DETAIL",
        "columns": "ALL",
        "quoteColumns": "f2~01~SECURITY_CODE~NEW_PRICE",
        "quoteType": "0",
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
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.rename(
        columns={
            "SECURITY_NAME_ABBR": "股票简称",
            "SECURITY_CODE": "股票代码",
            "CORRECODE": "增发代码",
            "SEO_TYPE": "发行方式",
            "ISSUE_NUM": "发行总数",
            "ONLINE_ISSUE_NUM": "网上发行",
            "ISSUE_PRICE": "发行价格",
            "NEW_PRICE": "最新价",
            "ISSUE_DATE": "发行日期",
            "ISSUE_LISTING_DATE": "增发上市日期",
            "LOCKIN_PERIOD": "锁定期",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "股票代码",
            "股票简称",
            "增发代码",
            "发行方式",
            "发行总数",
            "网上发行",
            "发行价格",
            "最新价",
            "发行日期",
            "增发上市日期",
            "锁定期",
        ]
    ]
    big_df["发行总数"] = pd.to_numeric(big_df["发行总数"], errors="coerce")
    big_df["发行价格"] = pd.to_numeric(big_df["发行价格"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["发行方式"] = big_df["发行方式"].map({"2": "公开增发", "1": "定向增发"})
    big_df["发行日期"] = pd.to_datetime(big_df["发行日期"], errors="coerce").dt.date
    big_df["增发上市日期"] = pd.to_datetime(
        big_df["增发上市日期"], errors="coerce"
    ).dt.date
    return big_df


def stock_pg_em() -> pd.DataFrame:
    """
    东方财富网-数据中心-新股数据-配股
    https://data.eastmoney.com/xg/pg/
    :return: 配股
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "EQUITY_RECORD_DATE",
        "sortTypes": "-1",
        "pageSize": "50000",
        "pageNumber": "1",
        "reportName": "RPT_IPO_ALLOTMENT",
        "columns": "ALL",
        "quoteColumns": "f2~01~SECURITY_CODE~NEW_PRICE",
        "quoteType": "0",
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
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "_",
        "_",
        "股票代码",
        "-",
        "股票简称",
        "配售代码",
        "_",
        "配股比例",
        "配股价",
        "配股前总股本",
        "配股数量",
        "配股后总股本",
        "股权登记日",
        "缴款起始日期",
        "缴款截止日期",
        "上市日",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "最新价",
    ]
    big_df = big_df[
        [
            "股票代码",
            "股票简称",
            "配售代码",
            "配股数量",
            "配股比例",
            "配股价",
            "最新价",
            "配股前总股本",
            "配股后总股本",
            "股权登记日",
            "缴款起始日期",
            "缴款截止日期",
            "上市日",
        ]
    ]
    big_df["配股比例"] = "10配" + big_df["配股比例"].astype(str)
    big_df["配股数量"] = pd.to_numeric(big_df["配股数量"], errors="coerce")
    big_df["配股价"] = pd.to_numeric(big_df["配股价"], errors="coerce")
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["配股前总股本"] = pd.to_numeric(big_df["配股前总股本"], errors="coerce")
    big_df["配股后总股本"] = pd.to_numeric(big_df["配股后总股本"], errors="coerce")
    big_df["股权登记日"] = pd.to_datetime(big_df["股权登记日"], errors="coerce").dt.date
    big_df["缴款起始日期"] = pd.to_datetime(
        big_df["缴款起始日期"], errors="coerce"
    ).dt.date
    big_df["缴款截止日期"] = pd.to_datetime(
        big_df["缴款截止日期"], errors="coerce"
    ).dt.date
    big_df["上市日"] = pd.to_datetime(big_df["上市日"], errors="coerce").dt.date
    return big_df


if __name__ == "__main__":
    stock_qbzf_em_df = stock_qbzf_em()
    print(stock_qbzf_em_df)

    stock_pg_em_df = stock_pg_em()
    print(stock_pg_em_df)
