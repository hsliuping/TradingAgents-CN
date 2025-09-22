#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2022/4/27 19:18
Desc: 东方财富网-数据中心-特色数据-一致行动人
https://data.eastmoney.com/yzxdr/
"""

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm

from akshare.utils import demjson


def stock_yzxdr_em(date: str = "20240930") -> pd.DataFrame:
    """
    东方财富网-数据中心-特色数据-一致行动人
    https://data.eastmoney.com/yzxdr/
    :param date: 每年的季度末时间点
    :type date: str
    :return: 一致行动人
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.simplefilter(action="ignore", category=FutureWarning)  # 忽略所有
    date = "-".join([date[:4], date[4:6], date[6:]])
    url = "https://datacenter.eastmoney.com/api/data/get"
    params = {
        "type": "RPTA_WEB_YZXDRINDEX",
        "sty": "ALL",
        "source": "WEB",
        "p": "1",
        "ps": "500",
        "st": "noticedate",
        "sr": "-1",
        "var": "mwUyirVm",
        "filter": f"(enddate='{date}')",
        "rt": "53575609",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -1])
    total_pages = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_pages + 1), leave=False):
        params.update(
            {
                "p": str(page),
                "filter": f"(enddate='{date}')",
            }
        )
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -1])
        temp_df = pd.DataFrame(data_json["result"]["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    big_df.columns = [
        "序号",
        "一致行动人",
        "股票代码",
        "股东排名",
        "公告日期",
        "股票简称",
        "持股数量",
        "持股比例",
        "持股数量变动",
        "_",
        "行业",
        "_",
        "_",
        "数据日期",
        "股票市场",
    ]
    big_df["数据日期"] = pd.to_datetime(big_df["数据日期"], errors="coerce")
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce")

    big_df = big_df[
        [
            "序号",
            "股票代码",
            "股票简称",
            "一致行动人",
            "股东排名",
            "持股数量",
            "持股比例",
            "持股数量变动",
            "行业",
            "公告日期",
        ]
    ]
    big_df["公告日期"] = pd.to_datetime(big_df["公告日期"], errors="coerce").dt.date
    big_df["持股数量"] = pd.to_numeric(big_df["持股数量"], errors="coerce")
    big_df["持股比例"] = pd.to_numeric(big_df["持股比例"], errors="coerce")
    big_df["持股数量变动"] = pd.to_numeric(big_df["持股数量变动"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_yzxdr_em_df = stock_yzxdr_em(date="20240930")
    print(stock_yzxdr_em_df)
