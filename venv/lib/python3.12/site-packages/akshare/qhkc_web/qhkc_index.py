#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/4/10 18:00
Desc: 奇货可查网站目前已经商业化运营, 特提供奇货可查-指数数据接口, 方便您程序化调用
注：期货价格为收盘价; 现货价格来自网络; 基差=现货价格-期货价格; 基差率=(现货价格-期货价格)/现货价格 * 100 %.
"""

from typing import AnyStr

import pandas as pd
import requests

from akshare.futures.cons import (
    QHKC_INDEX_URL,
    QHKC_INDEX_TREND_URL,
    QHKC_INDEX_PROFIT_LOSS_URL,
)


def get_qhkc_index(name: AnyStr = "奇货商品", url: AnyStr = QHKC_INDEX_URL):
    """
    奇货可查-指数-指数详情
    获得奇货可查的指数数据: '奇货黑链', '奇货商品', '奇货谷物', '奇货贵金属', '奇货饲料', '奇货软商品', '奇货化工', '奇货有色', '奇货股指', '奇货铁合金', '奇货油脂'
    :param url: 网址
    :param name 中文名称
    :return: pd.DataFrame
        date    price   volume  ...      margin     profit long_short_ratio
        2013-01-04     1000   260820  ...  1130485758    1816940            52.78
        2013-01-07  998.244   245112  ...  1132228518    2514410            52.15
        2013-01-08   1000.8   318866  ...  1160374489    2981010            51.99
        2013-01-09  998.661   247352  ...  1166611242    3904220            52.44
        2013-01-10  999.802   161292  ...  1153164771    1448190            52.81
               ...      ...      ...  ...         ...        ...              ...
        2019-09-24  845.391   881138  ...  1895149977  128379050             48.5
        2019-09-25  845.674   715180  ...  1797235248  128788230            48.29
        2019-09-26  840.154  1347570  ...  1730488227  137104890            48.44
        2019-09-27  834.831   920160  ...  1605342767  143128540            48.77
        2019-09-30  831.959  1031558  ...  1521875378  147810580            48.82
    """
    name_id_dict = {}
    qhkc_index_url = "https://qhkch.com/ajax/official_indexes.php"
    r = requests.post(qhkc_index_url)
    display_name = [item["name"] for item in r.json()["data"]]
    index_id = [item["id"] for item in r.json()["data"]]
    for item in range(len(display_name)):
        name_id_dict[display_name[item]] = index_id[item]
    payload_id = {"id": name_id_dict[name]}
    r = requests.post(url, data=payload_id)
    print(name, "数据获取成功")
    json_data = r.json()
    date = json_data["data"]["date"]
    price = json_data["data"]["price"]
    volume = json_data["data"]["volume"]
    open_interest = json_data["data"]["openint"]
    total_value = json_data["data"]["total_value"]
    profit = json_data["data"]["profit"]
    long_short_ratio = json_data["data"]["line"]
    df_temp = pd.DataFrame(
        [date, price, volume, open_interest, total_value, profit, long_short_ratio]
    ).T
    df_temp.columns = [
        "date",
        "price",
        "volume",
        "open_interest",
        "margin",
        "profit",
        "long_short_ratio",
    ]
    return df_temp


def get_qhkc_index_trend(name: AnyStr = "奇货商品", url: AnyStr = QHKC_INDEX_TREND_URL):
    """
    奇货可查-指数-大资金动向
    获得奇货可查的指数数据: '奇货黑链', '奇货商品', '奇货谷物', '奇货贵金属', '奇货饲料', '奇货软商品', '奇货化工', '奇货有色', '奇货股指', '奇货铁合金', '奇货油脂'
    :param url: 网址
    :param name None
    :return: pd.DataFrame
        broker    grade    money     open_order     variety
        中金期货     B -3.68209e+07  3.68209e+07      沪金
        浙商期货     D    -25845534     25845534      沪银
        永安期货     A    -25614000     25614000      沪银
        招商期货     D    -23517351     23517351      沪银
        海通期货     A     21440845     21440845      沪金
         美尔雅     D     21370975     21370975      沪金
        中原期货     C    -21204612     21204612      沪银
        国投安信     A -1.52374e+07  1.52374e+07      沪银
        中信期货     C  1.50941e+07  1.50941e+07      沪银
        海通期货     A -1.47184e+07  1.47184e+07      沪银
        方正中期     E -1.31432e+07  1.31432e+07      沪银
        东证期货     D   -1.283e+07    1.283e+07      沪银
        一德期货     A  1.24973e+07  1.24973e+07      沪银
        国投安信     A    -11602860     11602860      沪金
        国泰君安     B -1.09363e+07  1.09363e+07      沪金
        华安期货     D -9.99499e+06  9.99499e+06      沪金
        南华期货     B -9.23675e+06  9.23675e+06      沪银
        国贸期货     B  8.55245e+06  8.55245e+06      沪银
        道通期货     C      8527675      8527675      沪金
        招商期货     D -7.85457e+06  7.85457e+06      沪金
        东方财富     E -7.58235e+06  7.58235e+06      沪银
        五矿经易     A  6.95354e+06  6.95354e+06      沪银
        银河期货     B  6.84522e+06  6.84522e+06      沪银
        国贸期货     B      6731025      6731025      沪金
        平安期货     D     -6710418      6710418      沪银
        上海中期     C      6628800      6628800      沪金
        中信期货     C     -6345830      6345830      沪金
        银河期货     B     -6126295      6126295      沪金
        华泰期货     A -5.96254e+06  5.96254e+06      沪金
        招金期货     E -5.53029e+06  5.53029e+06      沪银
        东证期货     D -5.47486e+06  5.47486e+06      沪金
        光大期货     C     -5334730      5334730      沪金
        广发期货     D  5.31904e+06  5.31904e+06      沪金
        国信期货     D -5.05211e+06  5.05211e+06      沪金
    """
    name_id_dict = {}
    qhkc_index_url = "https://qhkch.com/ajax/official_indexes.php"
    r = requests.post(qhkc_index_url)
    display_name = [item["name"] for item in r.json()["data"]]
    index_id = [item["id"] for item in r.json()["data"]]
    for item in range(len(display_name)):
        name_id_dict[display_name[item]] = index_id[item]
    payload_id = {"page": 1, "limit": 10, "index": name_id_dict[name], "date": ""}
    r = requests.post(url, data=payload_id)
    print(f"{name}期货指数-大资金动向数据获取成功")
    json_data = r.json()
    df_temp = pd.DataFrame()
    for item in json_data["data"]:
        broker = item["broker"]
        grade = item["grade"]
        money = item["money"]
        order_money = item["order_money"]
        variety = item["variety"]
        df_temp = df_temp._append(
            pd.DataFrame([broker, grade, money, order_money, variety]).T
        )
    df_temp.columns = ["broker", "grade", "money", "open_order", "variety"]
    df_temp.reset_index(drop=True, inplace=True)
    return df_temp


def get_qhkc_index_profit_loss(
    name: AnyStr = "奇货商品",
    url: AnyStr = QHKC_INDEX_PROFIT_LOSS_URL,
    start_date="",
    end_date="",
):
    """
    奇货可查-指数-盈亏详情
    获得奇货可查的指数数据: '奇货黑链', '奇货商品', '奇货谷物', '奇货贵金属', '奇货饲料', '奇货软商品', '奇货化工', '奇货有色', '奇货股指', '奇货铁合金', '奇货油脂'
    :param url: 网址
    :param name None
    :param start_date: ""
    :param end_date: "20190716" 指定 end_date 就可以了
    :return: pd.DataFrame
        indexes       value  trans_date
        招金期货-沪金  -307489200  2019-09-30
        平安期货-沪银  -195016650  2019-09-30
        建信期货-沪银  -160327350  2019-09-30
        国贸期货-沪银  -159820965  2019-09-30
        东证期货-沪银  -123508635  2019-09-30
            ...         ...         ...
        永安期货-沪银   187411350  2019-09-30
        中信期货-沪金   242699750  2019-09-30
        华泰期货-沪银   255766185  2019-09-30
        永安期货-沪金   293008700  2019-09-30
        国泰君安-沪金   302774950  2019-09-30
    """
    name_id_dict = {}
    qhkc_index_url = "https://qhkch.com/ajax/official_indexes.php"
    r = requests.post(qhkc_index_url)
    display_name = [item["name"] for item in r.json()["data"]]
    index_id = [item["id"] for item in r.json()["data"]]
    for item in range(len(display_name)):
        name_id_dict[display_name[item]] = index_id[item]
    payload_id = {"index": name_id_dict[name], "date1": start_date, "date2": end_date}
    r = requests.post(url, data=payload_id)
    print(f"{name}期货指数-盈亏分布数据获取成功")
    json_data = r.json()
    indexes = json_data["data"]["indexes"]
    value = json_data["data"]["value"]
    trans_date = [json_data["data"]["trans_date"]] * len(value)
    df_temp = pd.DataFrame([indexes, value, trans_date]).T
    df_temp.columns = ["indexes", "value", "trans_date"]
    return df_temp


if __name__ == "__main__":
    get_qhkc_index_df = get_qhkc_index("奇货谷物")
    print(get_qhkc_index_df)

    get_qhkc_index_trend_df = get_qhkc_index_trend("奇货贵金属")
    print(get_qhkc_index_trend_df)

    get_qhkc_index_profit_loss_df = get_qhkc_index_profit_loss("奇货贵金属", end_date="20250410")
    print(get_qhkc_index_profit_loss_df)
