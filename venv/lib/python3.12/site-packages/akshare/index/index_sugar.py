# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2023/6/19 17:00
Desc: 沐甜科技数据中心-中国食糖指数
https://www.msweet.com.cn/mtkj/sjzx13/index.html
"""

import requests
import pandas as pd


def index_sugar_msweet() -> pd.DataFrame:
    """
    沐甜科技数据中心-中国食糖指数
    https://www.msweet.com.cn/mtkj/sjzx13/index.html
    :return: 中国食糖指数
    :rtype: pandas.DataFrame
    """
    url = "https://www.msweet.com.cn/eportal/ui"
    params = {
        "struts.portlet.action": "/portlet/price!getSTZSJson.action",
        "moduleId": "cb752447cfe24b44b18c7a7e9abab048",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.concat(
        [pd.DataFrame(data_json["category"]), pd.DataFrame(data_json["data"])], axis=1
    )
    temp_df.columns = ["日期", "综合价格", "原糖价格", "现货价格"]
    temp_df.loc[3226, ["原糖价格"]] = 12.88  # 数据源错误
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["综合价格"] = pd.to_numeric(temp_df["综合价格"], errors="coerce")
    temp_df["原糖价格"] = pd.to_numeric(temp_df["原糖价格"], errors="coerce")
    temp_df["现货价格"] = pd.to_numeric(temp_df["现货价格"], errors="coerce")
    return temp_df


def index_inner_quote_sugar_msweet() -> pd.DataFrame:
    """
    沐甜科技数据中心-配额内进口糖估算指数
    https://www.msweet.com.cn/mtkj/sjzx13/index.html
    :return: 配额内进口糖估算指数
    :rtype: pandas.DataFrame
    """
    url = "https://www.msweet.com.cn/datacenterapply/datacenter/json/JinKongTang.json"
    r = requests.get(url)
    data_json = r.json()
    temp_df = pd.concat(
        [pd.DataFrame(data_json["category"]), pd.DataFrame(data_json["data"])], axis=1
    )
    temp_df.columns = [
        "日期",
        "利润空间",
        "泰国糖",
        "泰国MA5",
        "巴西MA5",
        "利润MA5",
        "巴西MA10",
        "巴西糖",
        "柳州现货价",
        "广州现货价",
        "泰国MA10",
        "利润MA30",
        "利润MA10",
    ]
    temp_df.loc[988, ["泰国糖"]] = 4045.2  # 数据源错误
    temp_df["日期"] = temp_df["日期"].str.replace("/", "-")
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["利润空间"] = pd.to_numeric(temp_df["利润空间"], errors="coerce")
    temp_df["泰国糖"] = pd.to_numeric(temp_df["泰国糖"], errors="coerce")
    temp_df["泰国MA5"] = pd.to_numeric(temp_df["泰国MA5"], errors="coerce")
    temp_df["巴西MA5"] = pd.to_numeric(temp_df["巴西MA5"], errors="coerce")
    temp_df["巴西MA10"] = pd.to_numeric(temp_df["巴西MA10"], errors="coerce")
    temp_df["巴西糖"] = pd.to_numeric(temp_df["巴西糖"], errors="coerce")
    temp_df["柳州现货价"] = pd.to_numeric(temp_df["柳州现货价"], errors="coerce")
    temp_df["广州现货价"] = pd.to_numeric(temp_df["广州现货价"], errors="coerce")
    temp_df["泰国MA10"] = pd.to_numeric(temp_df["泰国MA10"], errors="coerce")
    temp_df["利润MA30"] = pd.to_numeric(temp_df["利润MA30"], errors="coerce")
    temp_df["利润MA10"] = pd.to_numeric(temp_df["利润MA10"], errors="coerce")
    return temp_df


def index_outer_quote_sugar_msweet() -> pd.DataFrame:
    """
    沐甜科技数据中心-配额外进口糖估算指数
    https://www.msweet.com.cn/mtkj/sjzx13/index.html
    :return: 配额内进口糖估算指数
    :rtype: pandas.DataFrame
    """
    url = "https://www.msweet.com.cn/datacenterapply/datacenter/json/Jkpewlr.json"
    r = requests.get(url)
    data_json = r.json()
    temp_df = pd.concat(
        [pd.DataFrame(data_json["category"]), pd.DataFrame(data_json["data"])], axis=1
    )
    temp_df.columns = [
        "日期",
        "巴西糖进口成本",
        "泰国糖进口利润空间",
        "巴西糖进口利润空间",
        "泰国糖进口成本",
        "日照现货价",
    ]
    temp_df["日期"] = temp_df["日期"].str.replace("/", "-")
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["巴西糖进口成本"] = pd.to_numeric(
        temp_df["巴西糖进口成本"], errors="coerce"
    )
    temp_df["泰国糖进口利润空间"] = pd.to_numeric(
        temp_df["泰国糖进口利润空间"], errors="coerce"
    )
    temp_df["巴西糖进口利润空间"] = pd.to_numeric(
        temp_df["巴西糖进口利润空间"], errors="coerce"
    )
    temp_df["泰国糖进口成本"] = pd.to_numeric(temp_df["泰国糖进口成本"])
    temp_df["日照现货价"] = pd.to_numeric(temp_df["日照现货价"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    index_sugar_msweet_df = index_sugar_msweet()
    print(index_sugar_msweet_df)

    index_inner_quote_sugar_msweet_df = index_inner_quote_sugar_msweet()
    print(index_inner_quote_sugar_msweet_df)

    index_outer_quote_sugar_msweet_df = index_outer_quote_sugar_msweet()
    print(index_outer_quote_sugar_msweet_df)
