#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/11 17:00
Desc: 九期网-期货手续费
https://www.9qihuo.com/qihuoshouxufei
"""

from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup


def _futures_comm_qihuo_process(df: pd.DataFrame, name: str = None) -> pd.DataFrame:
    """
    期货手续费数据细节处理函数
    https://www.9qihuo.com/qihuoshouxufei
    :param df: 获取到的 pandas.DataFrame 数据
    :type df: pandas.DataFrame
    :param name: 交易所名称
    :type name: str
    :return: 处理后的数据
    :rtype: pandas.DataFrame
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    common_temp_df = df.copy()
    common_temp_df["合约名称"] = (
        common_temp_df["合约品种"].str.split("(", expand=True).iloc[:, 0].str.strip()
    )
    common_temp_df["合约代码"] = (
        common_temp_df["合约品种"].str.split("(", expand=True).iloc[:, 1].str.strip(")")
    )
    common_temp_df["涨停板"] = (
        common_temp_df["涨/跌停板"].str.split("/", expand=True).iloc[:, 0].str.strip()
    )
    common_temp_df["跌停板"] = (
        common_temp_df["涨/跌停板"].str.split("/", expand=True).iloc[:, 1].str.strip()
    )
    common_temp_df["保证金-买开"] = common_temp_df["保证金-买开"].str.strip("%")
    common_temp_df["保证金-卖开"] = common_temp_df["保证金-卖开"].str.strip("%")
    common_temp_df["保证金-每手"] = common_temp_df["保证金-保证金/每手"].str.strip("元")
    common_temp_df["手续费"] = common_temp_df["手续费(开+平)"].str.strip("元")
    try:
        temp_df_ratio = (
            common_temp_df["手续费标准-开仓"][
                common_temp_df["手续费标准-开仓"].str.contains("万分之")
            ]
            .str.split("/", expand=True)
            .iloc[:, 0]
            .astype(float)
            / 10000
        )
    except IndexError:
        temp_df_ratio = pd.NA
    temp_df_yuan = common_temp_df["手续费标准-开仓"][
        common_temp_df["手续费标准-开仓"].str.contains("元")
    ]
    common_temp_df["手续费标准-开仓-万分之"] = temp_df_ratio
    common_temp_df["手续费标准-开仓-元"] = temp_df_yuan.str.strip("元")
    try:
        temp_df_ratio = (
            common_temp_df["手续费标准-平昨"][
                common_temp_df["手续费标准-平昨"].str.contains("万分之")
            ]
            .str.split("/", expand=True)
            .iloc[:, 0]
            .astype(float)
            / 10000
        )
    except IndexError:
        temp_df_ratio = pd.NA
    temp_df_yuan = common_temp_df["手续费标准-平昨"][
        common_temp_df["手续费标准-平昨"].str.contains("元")
    ]
    common_temp_df["手续费标准-平昨-万分之"] = temp_df_ratio
    common_temp_df["手续费标准-平昨-元"] = temp_df_yuan.str.strip("元")
    try:
        temp_df_ratio = (
            common_temp_df["手续费标准-平今"][
                common_temp_df["手续费标准-平今"].str.contains("万分之")
            ]
            .str.split("/", expand=True)
            .iloc[:, 0]
            .astype(float)
            / 10000
        )
    except IndexError:
        temp_df_ratio = pd.NA
    temp_df_yuan = common_temp_df["手续费标准-平今"][
        common_temp_df["手续费标准-平今"].str.contains("元")
    ]
    common_temp_df["手续费标准-平今-万分之"] = temp_df_ratio
    common_temp_df["手续费标准-平今-元"] = temp_df_yuan.str.strip("元")
    del common_temp_df["手续费标准-开仓"]
    del common_temp_df["手续费标准-平昨"]
    del common_temp_df["手续费标准-平今"]
    del common_temp_df["合约品种"]
    del common_temp_df["涨/跌停板"]
    del common_temp_df["手续费(开+平)"]
    del common_temp_df["保证金-保证金/每手"]
    common_temp_df["交易所名称"] = name
    common_temp_df = common_temp_df[
        [
            "交易所名称",
            "合约名称",
            "合约代码",
            "现价",
            "涨停板",
            "跌停板",
            "保证金-买开",
            "保证金-卖开",
            "保证金-每手",
            "手续费标准-开仓-万分之",
            "手续费标准-开仓-元",
            "手续费标准-平昨-万分之",
            "手续费标准-平昨-元",
            "手续费标准-平今-万分之",
            "手续费标准-平今-元",
            "每跳毛利",
            "手续费",
            "每跳净利",
            "备注",
        ]
    ]
    common_temp_df["现价"] = pd.to_numeric(common_temp_df["现价"])
    common_temp_df["涨停板"] = pd.to_numeric(common_temp_df["涨停板"])
    common_temp_df["跌停板"] = pd.to_numeric(common_temp_df["跌停板"])
    common_temp_df["保证金-买开"] = pd.to_numeric(common_temp_df["保证金-买开"])
    common_temp_df["保证金-卖开"] = pd.to_numeric(common_temp_df["保证金-卖开"])
    common_temp_df["保证金-每手"] = pd.to_numeric(common_temp_df["保证金-每手"])
    # common_temp_df["手续费标准-开仓-元"] = pd.to_numeric(common_temp_df["手续费标准-开仓-元"])
    # common_temp_df["手续费标准-平昨-元"] = pd.to_numeric(common_temp_df["手续费标准-平昨-元"])
    # common_temp_df["手续费标准-平今-元"] = pd.to_numeric(common_temp_df["手续费标准-平今-元"])
    common_temp_df["每跳毛利"] = pd.to_numeric(common_temp_df["每跳毛利"])
    common_temp_df["手续费"] = pd.to_numeric(common_temp_df["手续费"])
    common_temp_df["每跳净利"] = pd.to_numeric(common_temp_df["每跳净利"])
    url = "https://www.9qihuo.com/qihuoshouxufei"
    r = requests.get(url, verify=False)
    soup = BeautifulSoup(r.text, features="lxml")
    raw_date_text = soup.find(name="a", attrs={"id": "dlink"}).previous
    comm_update_time = raw_date_text.split("，")[0].strip("（手续费更新时间：")
    price_update_time = (
        raw_date_text.split("，")[1].strip("价格更新时间：").strip("。）")
    )
    common_temp_df["手续费更新时间"] = comm_update_time
    common_temp_df["价格更新时间"] = price_update_time
    return common_temp_df


def futures_comm_info(symbol: str = "所有") -> pd.DataFrame:
    """
    九期网-期货手续费
    https://www.9qihuo.com/qihuoshouxufei
    :param symbol: choice of {"所有", "上海期货交易所", "大连商品交易所", "郑州商品交易所", "上海国际能源交易中心", "中国金融期货交易所", "广州期货交易所"}
    :type symbol: str
    :return: 期货手续费
    :rtype: pandas.DataFrame
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = "https://www.9qihuo.com/qihuoshouxufei"
    r = requests.get(url, verify=False)
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df.columns = [
        "合约品种",
        "现价",
        "涨/跌停板",
        "保证金-买开",
        "保证金-卖开",
        "保证金-保证金/每手",
        "手续费标准-开仓",
        "手续费标准-平昨",
        "手续费标准-平今",
        "每跳毛利",
        "手续费(开+平)",
        "每跳净利",
        "备注",
        "-",
        "-",
    ]
    df_0 = temp_df[temp_df["合约品种"].str.contains("上海期货交易所")].index.values[0]
    df_1 = temp_df[temp_df["合约品种"].str.contains("大连商品交易所")].index.values[0]
    df_2 = temp_df[temp_df["合约品种"].str.contains("郑州商品交易所")].index.values[0]
    df_3 = temp_df[
        temp_df["合约品种"].str.contains("上海国际能源交易中心")
    ].index.values[0]
    df_4 = temp_df[temp_df["合约品种"].str.contains("广州期货交易所")].index.values[0]
    df_5 = temp_df[temp_df["合约品种"].str.contains("中国金融期货交易所")].index.values[
        0
    ]
    shfe_df = temp_df.iloc[df_0 + 3 : df_1, :].reset_index(drop=True)
    dce_df = temp_df.iloc[df_1 + 3 : df_2, :].reset_index(drop=True)
    czce_df = temp_df.iloc[df_2 + 3 : df_3, :].reset_index(drop=True)
    ine_df = temp_df.iloc[df_3 + 3 : df_4, :].reset_index(drop=True)
    gfex_df = temp_df.iloc[df_4 + 3 : df_5, :].reset_index(drop=True)
    cffex_df = temp_df.iloc[df_5 + 3 :, :].reset_index(drop=True)
    if symbol == "上海期货交易所":
        return _futures_comm_qihuo_process(shfe_df, name="上海期货交易所")
    elif symbol == "大连商品交易所":
        return _futures_comm_qihuo_process(dce_df, name="大连商品交易所")
    elif symbol == "郑州商品交易所":
        return _futures_comm_qihuo_process(czce_df, name="郑州商品交易所")
    elif symbol == "上海国际能源交易中心":
        return _futures_comm_qihuo_process(ine_df, name="上海国际能源交易中心")
    elif symbol == "广州期货交易所":
        return _futures_comm_qihuo_process(gfex_df, name="广州期货交易所")
    elif symbol == "中国金融期货交易所":
        return _futures_comm_qihuo_process(cffex_df, name="中国金融期货交易所")
    else:
        big_df = pd.DataFrame()
        big_df = pd.concat(
            objs=[big_df, _futures_comm_qihuo_process(shfe_df, name="上海期货交易所")],
            ignore_index=True,
        )
        big_df = pd.concat(
            objs=[big_df, _futures_comm_qihuo_process(dce_df, name="大连商品交易所")],
            ignore_index=True,
        )
        big_df = pd.concat(
            objs=[big_df, _futures_comm_qihuo_process(czce_df, name="郑州商品交易所")],
            ignore_index=True,
        )
        big_df = pd.concat(
            objs=[
                big_df,
                _futures_comm_qihuo_process(ine_df, name="上海国际能源交易中心"),
            ],
            ignore_index=True,
        )
        big_df = pd.concat(
            objs=[big_df, _futures_comm_qihuo_process(gfex_df, name="广州期货交易所")],
            ignore_index=True,
        )
        big_df = pd.concat(
            objs=[
                big_df,
                _futures_comm_qihuo_process(cffex_df, name="中国金融期货交易所"),
            ],
            ignore_index=True,
        )
        return big_df


if __name__ == "__main__":
    futures_comm_info_df = futures_comm_info(symbol="所有")
    print(futures_comm_info_df)
