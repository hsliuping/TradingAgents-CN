#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/3 16:08
Desc: 金十数据-数据中心-主要机构-宏观经济
https://datacenter.jin10.com/
"""

import datetime
import time

import pandas as pd
import requests
from tqdm import tqdm


def macro_cons_gold() -> pd.DataFrame:
    """
    全球最大黄金 ETF—SPDR Gold Trust 持仓报告, 数据区间从 20041118-至今
    https://datacenter.jin10.com/reportType/dc_etf_gold
    :return: 持仓报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }
    url = "https://datacenter-api.jin10.com/reports/list_v2"
    params = {
        "category": "etf",
        "attr_id": "1",
        "max_date": "",
        "_": str(int(round(t * 1000))),
    }
    big_df = pd.DataFrame()
    while True:
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        if not data_json["data"]["values"]:
            break
        temp_df = pd.DataFrame(data_json["data"]["values"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
        last_date_str = temp_df.iat[-1, 0]
        last_date_str = (
            (
                datetime.datetime.strptime(last_date_str, "%Y-%m-%d")
                - datetime.timedelta(days=1)
            )
            .date()
            .isoformat()
        )
        params.update({"max_date": f"{last_date_str}"})
    big_df.columns = [
        "日期",
        "总库存",
        "增持/减持",
        "总价值",
    ]
    big_df["商品"] = "黄金"
    big_df = big_df[
        [
            "商品",
            "日期",
            "总库存",
            "增持/减持",
            "总价值",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["总库存"] = pd.to_numeric(big_df["总库存"], errors="coerce")
    big_df["增持/减持"] = pd.to_numeric(big_df["增持/减持"], errors="coerce")
    big_df["总价值"] = pd.to_numeric(big_df["总价值"], errors="coerce")
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_cons_silver() -> pd.DataFrame:
    """
    全球最大白银 ETF—SPDR Gold Trust 持仓报告, 数据区间从 20041118-至今
    https://datacenter.jin10.com/reportType/dc_etf_sliver
    :return: 持仓报告
    :rtype: pandas.DataFrame
    """
    t = time.time()
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "x-csrf-token",
        "x-version": "1.0.0",
    }
    url = "https://datacenter-api.jin10.com/reports/list_v2"
    params = {
        "category": "etf",
        "attr_id": "2",
        "max_date": "",
        "_": str(int(round(t * 1000))),
    }
    big_df = pd.DataFrame()
    while True:
        r = requests.get(url, params=params, headers=headers)
        data_json = r.json()
        if not data_json["data"]["values"]:
            break
        temp_df = pd.DataFrame(data_json["data"]["values"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
        last_date_str = temp_df.iat[-1, 0]
        last_date_str = (
            (
                datetime.datetime.strptime(last_date_str, "%Y-%m-%d")
                - datetime.timedelta(days=1)
            )
            .date()
            .isoformat()
        )
        params.update({"max_date": f"{last_date_str}"})
    big_df.columns = [
        "日期",
        "总库存",
        "增持/减持",
        "总价值",
    ]
    big_df["商品"] = "白银"
    big_df = big_df[
        [
            "商品",
            "日期",
            "总库存",
            "增持/减持",
            "总价值",
        ]
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["总库存"] = pd.to_numeric(big_df["总库存"], errors="coerce")
    big_df["增持/减持"] = pd.to_numeric(big_df["增持/减持"], errors="coerce")
    big_df["总价值"] = pd.to_numeric(big_df["总价值"], errors="coerce")
    big_df.sort_values(["日期"], inplace=True)
    big_df.reset_index(inplace=True, drop=True)
    return big_df


def macro_cons_opec_month() -> pd.DataFrame:
    """
    欧佩克报告-月度, 数据区间从 20170118-至今
    这里返回的具体索引日期的数据为上一个月的数据, 由于某些国家的数据有缺失
    只选择有数据的国家返回
    20200312:fix:由于 “厄瓜多尔” 已经有几个月没有更新数据，在这里加以剔除
    https://datacenter.jin10.com/reportType/dc_opec_report
    :return: 欧佩克报告-月度
    :rtype: pandas.DataFrame
    """
    t = time.time()
    big_df = pd.DataFrame()
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "origin": "https://datacenter.jin10.com",
        "pragma": "no-cache",
        "referer": "https://datacenter.jin10.com/reportType/dc_opec_report",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/79.0.3945.117 Safari/537.36",
        "x-app-id": "rU6QIu7JHe2gOUeR",
        "x-csrf-token": "",
        "x-version": "1.0.0",
    }
    res = requests.get(
        url=f"https://datacenter-api.jin10.com/reports/dates?category=opec&_={str(int(round(t * 1000)))}",
        headers=headers,
    )  # 日期序列
    all_date_list = res.json()["data"]
    bar = tqdm(reversed(all_date_list))
    for item in bar:
        bar.set_description(f"Please wait for a moment, now downloading {item}'s data")
        res = requests.get(
            url=f"https://datacenter-api.jin10.com/reports/list?"
            f"category=opec&date={item}&_={str(int(round(t * 1000)))}",
            headers=headers,
        )
        temp_df = pd.DataFrame(
            res.json()["data"]["values"],
            columns=pd.DataFrame(res.json()["data"]["keys"])["name"].tolist(),
        ).T
        temp_df.columns = temp_df.iloc[0, :]
        temp_df = temp_df.iloc[1:, :]
        try:
            temp_df = temp_df[
                [
                    "阿尔及利亚",
                    "安哥拉",
                    "加蓬",
                    "伊朗",
                    "伊拉克",
                    "科威特",
                    "利比亚",
                    "尼日利亚",
                    "沙特",
                    "阿联酋",
                    "委内瑞拉",
                    "欧佩克产量",
                ]
            ].iloc[-2, :]
        except:  # noqa: E722
            temp_df = temp_df[
                [
                    "阿尔及利亚",
                    "安哥拉",
                    "加蓬",
                    "伊朗",
                    "伊拉克",
                    "科威特",
                    "利比亚",
                    "尼日利亚",
                    "沙特",
                    "阿联酋",
                    "委内瑞拉",
                    "欧佩克产量",
                ]
            ].iloc[-1, :]
        temp_df.dropna(inplace=True)
        big_df[temp_df.name] = temp_df
    big_df = big_df.T
    big_df = big_df.astype(float)
    big_df.reset_index(inplace=True)
    big_df.rename(columns={"index": "日期"}, inplace=True)
    big_df.columns.name = None
    return big_df


if __name__ == "__main__":
    macro_cons_gold_df = macro_cons_gold()
    print(macro_cons_gold_df)

    macro_cons_silver_df = macro_cons_silver()
    print(macro_cons_silver_df)

    macro_cons_opec_month_df = macro_cons_opec_month()
    print(macro_cons_opec_month_df)
