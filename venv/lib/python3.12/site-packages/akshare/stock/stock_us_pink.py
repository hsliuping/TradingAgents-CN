#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/6/17 14:00
Desc: 东方财富网-行情中心-美股市场-粉单市场
https://quote.eastmoney.com/center/gridlist.html#us_pinksheet
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_us_pink_spot_em() -> pd.DataFrame:
    """
    东方财富网-行情中心-美股市场-粉单市场
    https://quote.eastmoney.com/center/gridlist.html#us_pinksheet
    :return: 粉单市场实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://23.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "np": "1",
        "fltt": "1",
        "invt": "1",
        "fs": "m:153",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,"
                  "f26,f22,f33,f11,f62,f128,f136,f115,f152",
        "fid": "f3",
        "pn": "1",
        "pz": "100",
        "po": "1",
        "dect": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    import math
    total_page = math.ceil(data_json['data']["total"] / 100)
    tqdm = get_tqdm()
    big_df = pd.DataFrame()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"pn": page})
        r = requests.get(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"]["diff"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "_",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "简称",
        "编码",
        "名称",
        "最高价",
        "最低价",
        "开盘价",
        "昨收价",
        "总市值",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "_",
        "市盈率",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    big_df.rename(columns={"index": "序号"}, inplace=True)
    big_df["代码"] = big_df["编码"].astype(str) + "." + big_df["简称"]
    big_df = big_df[
        [
            "序号",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "开盘价",
            "最高价",
            "最低价",
            "昨收价",
            "总市值",
            "市盈率",
            "代码",
        ]
    ]
    big_df["最新价"] = pd.to_numeric(big_df["最新价"], errors="coerce")
    big_df["涨跌额"] = pd.to_numeric(big_df["涨跌额"], errors="coerce")
    big_df["涨跌幅"] = pd.to_numeric(big_df["涨跌幅"], errors="coerce")
    big_df["开盘价"] = pd.to_numeric(big_df["开盘价"], errors="coerce")
    big_df["最高价"] = pd.to_numeric(big_df["最高价"], errors="coerce")
    big_df["最低价"] = pd.to_numeric(big_df["最低价"], errors="coerce")
    big_df["昨收价"] = pd.to_numeric(big_df["昨收价"], errors="coerce")
    big_df["总市值"] = pd.to_numeric(big_df["总市值"], errors="coerce")
    big_df["市盈率"] = pd.to_numeric(big_df["市盈率"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_us_pink_spot_em_df = stock_us_pink_spot_em()
    print(stock_us_pink_spot_em_df)
