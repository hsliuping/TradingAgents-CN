#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/4/5 17:00
Desc: 东方财富网-数据中心-经济数据-中美国债收益率
https://data.eastmoney.com/cjsj/zmgzsyl.html
"""

import pandas as pd
import requests
from akshare.utils.tqdm import get_tqdm


def bond_zh_us_rate(start_date: str = "19901219") -> pd.DataFrame:
    """
    东方财富网-数据中心-经济数据-中美国债收益率
    https://data.eastmoney.com/cjsj/zmgzsyl.html
    :param start_date: 开始统计时间
    :type start_date: str
    :return: 中美国债收益率
    :rtype: pandas.DataFrame
    """
    url = "https://datacenter.eastmoney.com/api/data/get"
    params = {
        "type": "RPTA_WEB_TREASURYYIELD",
        "sty": "ALL",
        "st": "SOLAR_DATE",
        "sr": "-1",
        "token": "894050c76af8597a853f5b408b759f5d",
        "p": "1",
        "ps": "500",
        "pageNo": "1",
        "pageNum": "1",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    total_page = data_json["result"]["pages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params = {
            "type": "RPTA_WEB_TREASURYYIELD",
            "sty": "ALL",
            "st": "SOLAR_DATE",
            "sr": "-1",
            "token": "894050c76af8597a853f5b408b759f5d",
            "p": page,
            "ps": "500",
            "pageNo": page,
            "pageNum": page,
        }
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["result"]["data"])
        for col in temp_df.columns:
            if temp_df[col].isnull().all():  # 检查列是否包含 None 或 NaN
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        if big_df.empty:
            big_df = temp_df
        else:
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)

        temp_date_list = pd.to_datetime(big_df["SOLAR_DATE"]).dt.date.to_list()
        if pd.to_datetime(start_date) in pd.date_range(
            temp_date_list[-1], temp_date_list[0]
        ):
            break

    big_df.rename(
        columns={
            "SOLAR_DATE": "日期",
            "EMM00166462": "中国国债收益率5年",
            "EMM00166466": "中国国债收益率10年",
            "EMM00166469": "中国国债收益率30年",
            "EMM00588704": "中国国债收益率2年",
            "EMM01276014": "中国国债收益率10年-2年",
            "EMG00001306": "美国国债收益率2年",
            "EMG00001308": "美国国债收益率5年",
            "EMG00001310": "美国国债收益率10年",
            "EMG00001312": "美国国债收益率30年",
            "EMG01339436": "美国国债收益率10年-2年",
            "EMM00000024": "中国GDP年增率",
            "EMG00159635": "美国GDP年增率",
        },
        inplace=True,
    )
    big_df = big_df[
        [
            "日期",
            "中国国债收益率2年",
            "中国国债收益率5年",
            "中国国债收益率10年",
            "中国国债收益率30年",
            "中国国债收益率10年-2年",
            "中国GDP年增率",
            "美国国债收益率2年",
            "美国国债收益率5年",
            "美国国债收益率10年",
            "美国国债收益率30年",
            "美国国债收益率10年-2年",
            "美国GDP年增率",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce")
    big_df["中国国债收益率2年"] = pd.to_numeric(
        big_df["中国国债收益率2年"], errors="coerce"
    )
    big_df["中国国债收益率5年"] = pd.to_numeric(
        big_df["中国国债收益率5年"], errors="coerce"
    )
    big_df["中国国债收益率10年"] = pd.to_numeric(
        big_df["中国国债收益率10年"], errors="coerce"
    )
    big_df["中国国债收益率30年"] = pd.to_numeric(
        big_df["中国国债收益率30年"], errors="coerce"
    )
    big_df["中国国债收益率10年-2年"] = pd.to_numeric(
        big_df["中国国债收益率10年-2年"], errors="coerce"
    )
    big_df["中国GDP年增率"] = pd.to_numeric(big_df["中国GDP年增率"], errors="coerce")
    big_df["美国国债收益率2年"] = pd.to_numeric(
        big_df["美国国债收益率2年"], errors="coerce"
    )
    big_df["美国国债收益率5年"] = pd.to_numeric(
        big_df["美国国债收益率5年"], errors="coerce"
    )
    big_df["美国国债收益率10年"] = pd.to_numeric(
        big_df["美国国债收益率10年"], errors="coerce"
    )
    big_df["美国国债收益率30年"] = pd.to_numeric(
        big_df["美国国债收益率30年"], errors="coerce"
    )
    big_df["美国国债收益率10年-2年"] = pd.to_numeric(
        big_df["美国国债收益率10年-2年"], errors="coerce"
    )
    big_df["美国GDP年增率"] = pd.to_numeric(big_df["美国GDP年增率"], errors="coerce")
    big_df.sort_values("日期", inplace=True)
    big_df.set_index(["日期"], inplace=True)
    big_df = big_df[pd.to_datetime(start_date) :]
    big_df.reset_index(inplace=True)
    big_df["日期"] = pd.to_datetime(big_df["日期"]).dt.date
    return big_df


if __name__ == "__main__":
    bond_zh_us_rate_df = bond_zh_us_rate(start_date="19901219")
    print(bond_zh_us_rate_df)
