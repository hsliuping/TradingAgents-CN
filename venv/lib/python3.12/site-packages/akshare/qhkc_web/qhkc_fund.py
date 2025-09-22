#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/4/10 18:00
Desc: 奇货可查网站目前已经商业化运营, 特提供奇货可查-资金数据接口, 方便您程序化调用
注：期货价格为收盘价; 现货价格来自网络; 基差=现货价格-期货价格; 基差率=(现货价格-期货价格)/现货价格 * 100 %.
"""

import datetime
from typing import AnyStr

import pandas as pd
import requests

from akshare.futures.cons import (
    QHKC_FUND_BS_URL,
    QHKC_FUND_POSITION_URL,
    QHKC_FUND_POSITION_CHANGE_URL,
    QHKC_FUND_DEAL_URL,
)


def get_qhkc_fund_bs(
    date: datetime.datetime.date = "20190924", url: AnyStr = QHKC_FUND_BS_URL
):
    """
    奇货可查-资金-净持仓分布
    可获取数据的时间段为:"2016-10-10:2019-09-30"
    :param url: 网址
    :param date: 中文名称
    :return: pd.DataFrame
    symbol_df
       name       value        ratio      date
       IC  1552535406     0.195622  20190924
       IF   536644080    0.0676182  20190924
       橡胶   536439921    0.0675924  20190924
       沪铜   460851099    0.0580681  20190924
       豆粕   401005794    0.0505275  20190924
      螺纹钢   329159263    0.0414747  20190924
       焦炭   325646968    0.0410321  20190924
      燃料油   313246789    0.0394697  20190924
       IH   245556750    0.0309406  20190924
       棉花   214538541    0.0270323  20190924
      PTA   206340552    0.0259993  20190924
       白糖   139901255    0.0176278  20190924
       豆油   133664010    0.0168419  20190924
       沪铝   109789864    0.0138337  20190924
       沪锌   107440906    0.0135378  20190924
       纸浆    95517374    0.0120354  20190924
       苹果    81058733    0.0102136  20190924
       塑料    63665245   0.00802194  20190924
       菜油    61544593   0.00775474  20190924
      铁矿石    60751108   0.00765475  20190924
       焦煤    58327920   0.00734943  20190924
       甲醇    52148752   0.00657084  20190924
       沥青    49207374   0.00620022  20190924
       菜粕    48266258   0.00608164  20190924
      棕榈油    31615548   0.00398362  20190924
       PP    29374826   0.00370128  20190924
       豆一    22368376   0.00281846  20190924
       玉米    13861567   0.00174658  20190924
       沪锡     7485903  0.000943238  20190924
       淀粉     4811234  0.000606225  20190924
       棉纱     3627240  0.000457039  20190924
       尿素     2290674  0.000288629  20190924
       鸡蛋     2035406  0.000256465  20190924
       粳米     1999282  0.000251913  20190924
      油菜籽      533482  6.72197e-05  20190924
      晚籼稻           0            0  20190924
       强麦           0            0  20190924
       沪铅       89914  1.13293e-05  20190924
       豆二      379200  4.77799e-05  20190924
       硅铁     5025872  0.000633269  20190924
       红枣     8521668   0.00107375  20190924
       锰硅     9472832   0.00119359  20190924
       郑煤     9888272   0.00124594  20190924
      乙二醇    18324242   0.00230889  20190924
      PVC    19454830   0.00245135  20190924
       玻璃    27076226   0.00341166  20190924
       热卷    28832929     0.003633  20190924
       沪银   375076371    0.0472603  20190924
       沪镍   411622624    0.0518652  20190924
       沪金   719371823    0.0906422  20190924

    long_short_df
          name       value     ratio      date
        空  6303252093  0.794222  20190924
        多  1633136803  0.205778  20190924
    """
    date = str(date)
    date = date[:4] + "-" + date[4:6] + "-" + date[6:]
    print(date)
    payload_id = {"date": date}
    r = requests.post(url, data=payload_id)
    print("数据获取成功")
    json_data = r.json()
    symbol_name = []
    for item in json_data["data"]["datas1"]:
        symbol_name.append(item["name"])
    symbol_value = []
    for item in json_data["data"]["datas1"]:
        symbol_value.append(item["value"])
    long_short_name = []
    for item in json_data["data"]["datas2"]:
        long_short_name.append(item["name"])
    long_short_value = []
    for item in json_data["data"]["datas2"]:
        long_short_value.append(item["value"])
    symbol_df = pd.DataFrame([symbol_name, symbol_value]).T
    long_short_df = pd.DataFrame([long_short_name, long_short_value]).T
    symbol_df.columns = ["name", "value"]
    symbol_df["ratio"] = symbol_df["value"] / symbol_df["value"].sum()
    symbol_df["date"] = date
    long_short_df.columns = ["name", "value"]
    long_short_df["ratio"] = long_short_df["value"] / long_short_df["value"].sum()
    long_short_df["date"] = date
    return symbol_df, long_short_df


def get_qhkc_fund_position(
    date: datetime.datetime.date = "20190924", url: AnyStr = QHKC_FUND_POSITION_URL
):
    """
    奇货可查-资金-总持仓分布
    可获取数据的时间段为:"2016-10-10:2019-09-30"
    :param url: 网址
    :param date: 中文名称
    :return: pd.DataFrame
    symbol_df
       name       value        ratio      date
       IC  1552535406     0.195622  20190924
       IF   536644080    0.0676182  20190924
       橡胶   536439921    0.0675924  20190924
       沪铜   460851099    0.0580681  20190924
       豆粕   401005794    0.0505275  20190924
      螺纹钢   329159263    0.0414747  20190924
       焦炭   325646968    0.0410321  20190924
      燃料油   313246789    0.0394697  20190924
       IH   245556750    0.0309406  20190924
       棉花   214538541    0.0270323  20190924
      PTA   206340552    0.0259993  20190924
       白糖   139901255    0.0176278  20190924
       豆油   133664010    0.0168419  20190924
       沪铝   109789864    0.0138337  20190924
       沪锌   107440906    0.0135378  20190924
       纸浆    95517374    0.0120354  20190924
       苹果    81058733    0.0102136  20190924
       塑料    63665245   0.00802194  20190924
       菜油    61544593   0.00775474  20190924
      铁矿石    60751108   0.00765475  20190924
       焦煤    58327920   0.00734943  20190924
       甲醇    52148752   0.00657084  20190924
       沥青    49207374   0.00620022  20190924
       菜粕    48266258   0.00608164  20190924
      棕榈油    31615548   0.00398362  20190924
       PP    29374826   0.00370128  20190924
       豆一    22368376   0.00281846  20190924
       玉米    13861567   0.00174658  20190924
       沪锡     7485903  0.000943238  20190924
       淀粉     4811234  0.000606225  20190924
       棉纱     3627240  0.000457039  20190924
       尿素     2290674  0.000288629  20190924
       鸡蛋     2035406  0.000256465  20190924
       粳米     1999282  0.000251913  20190924
      油菜籽      533482  6.72197e-05  20190924
      晚籼稻           0            0  20190924
       强麦           0            0  20190924
       沪铅       89914  1.13293e-05  20190924
       豆二      379200  4.77799e-05  20190924
       硅铁     5025872  0.000633269  20190924
       红枣     8521668   0.00107375  20190924
       锰硅     9472832   0.00119359  20190924
       郑煤     9888272   0.00124594  20190924
      乙二醇    18324242   0.00230889  20190924
      PVC    19454830   0.00245135  20190924
       玻璃    27076226   0.00341166  20190924
       热卷    28832929     0.003633  20190924
       沪银   375076371    0.0472603  20190924
       沪镍   411622624    0.0518652  20190924
       沪金   719371823    0.0906422  20190924

    long_short_df
          name       value     ratio      date
        空  6303252093  0.794222  20190924
        多  1633136803  0.205778  20190924
    """
    date = str(date)
    date = date[:4] + "-" + date[4:6] + "-" + date[6:]
    print(date)
    payload_id = {"date": date}
    r = requests.post(url, data=payload_id)
    print(url)
    print("数据获取成功")
    json_data = r.json()
    symbol_name = []
    for item in json_data["data"]["datas1"]:
        symbol_name.append(item["name"])
    symbol_value = []
    for item in json_data["data"]["datas1"]:
        symbol_value.append(item["value"])
    long_short_name = []
    for item in json_data["data"]["datas2"]:
        long_short_name.append(item["name"])
    long_short_value = []
    for item in json_data["data"]["datas2"]:
        long_short_value.append(item["value"])
    symbol_df = pd.DataFrame([symbol_name, symbol_value]).T
    long_short_df = pd.DataFrame([long_short_name, long_short_value]).T
    symbol_df.columns = ["name", "value"]
    symbol_df["ratio"] = symbol_df["value"] / symbol_df["value"].sum()
    symbol_df["date"] = date
    long_short_df.columns = ["name", "value"]
    long_short_df["ratio"] = long_short_df["value"] / long_short_df["value"].sum()
    long_short_df["date"] = date
    return symbol_df, long_short_df


def get_qhkc_fund_position_change(
    date: datetime.datetime.date = "20190924",
    url: AnyStr = QHKC_FUND_POSITION_CHANGE_URL,
):
    """
    奇货可查-资金-净持仓变化分布
    可获取数据的时间段为:"2016-10-10:2019-09-30"
    :param url: 网址
    :param date: 中文名称
    :return: pd.DataFrame
    symbol_df
       name       value        ratio      date
       IC  1552535406     0.195622  20190924
       IF   536644080    0.0676182  20190924
       橡胶   536439921    0.0675924  20190924
       沪铜   460851099    0.0580681  20190924
       豆粕   401005794    0.0505275  20190924
      螺纹钢   329159263    0.0414747  20190924
       焦炭   325646968    0.0410321  20190924
      燃料油   313246789    0.0394697  20190924
       IH   245556750    0.0309406  20190924
       棉花   214538541    0.0270323  20190924
      PTA   206340552    0.0259993  20190924
       白糖   139901255    0.0176278  20190924
       豆油   133664010    0.0168419  20190924
       沪铝   109789864    0.0138337  20190924
       沪锌   107440906    0.0135378  20190924
       纸浆    95517374    0.0120354  20190924
       苹果    81058733    0.0102136  20190924
       塑料    63665245   0.00802194  20190924
       菜油    61544593   0.00775474  20190924
      铁矿石    60751108   0.00765475  20190924
       焦煤    58327920   0.00734943  20190924
       甲醇    52148752   0.00657084  20190924
       沥青    49207374   0.00620022  20190924
       菜粕    48266258   0.00608164  20190924
      棕榈油    31615548   0.00398362  20190924
       PP    29374826   0.00370128  20190924
       豆一    22368376   0.00281846  20190924
       玉米    13861567   0.00174658  20190924
       沪锡     7485903  0.000943238  20190924
       淀粉     4811234  0.000606225  20190924
       棉纱     3627240  0.000457039  20190924
       尿素     2290674  0.000288629  20190924
       鸡蛋     2035406  0.000256465  20190924
       粳米     1999282  0.000251913  20190924
      油菜籽      533482  6.72197e-05  20190924
      晚籼稻           0            0  20190924
       强麦           0            0  20190924
       沪铅       89914  1.13293e-05  20190924
       豆二      379200  4.77799e-05  20190924
       硅铁     5025872  0.000633269  20190924
       红枣     8521668   0.00107375  20190924
       锰硅     9472832   0.00119359  20190924
       郑煤     9888272   0.00124594  20190924
      乙二醇    18324242   0.00230889  20190924
      PVC    19454830   0.00245135  20190924
       玻璃    27076226   0.00341166  20190924
       热卷    28832929     0.003633  20190924
       沪银   375076371    0.0472603  20190924
       沪镍   411622624    0.0518652  20190924
       沪金   719371823    0.0906422  20190924

    long_short_df
          name       value     ratio      date
        空  6303252093  0.794222  20190924
        多  1633136803  0.205778  20190924
    """
    date = str(date)
    date = date[:4] + "-" + date[4:6] + "-" + date[6:]
    print(date)
    payload_id = {"date": date}
    r = requests.post(url, data=payload_id)
    print(url)
    print("数据获取成功")
    json_data = r.json()
    symbol_name = []
    for item in json_data["data"]["datas1"]:
        symbol_name.append(item["name"])
    symbol_value = []
    for item in json_data["data"]["datas1"]:
        symbol_value.append(item["value"])
    long_short_name = []
    for item in json_data["data"]["datas2"]:
        long_short_name.append(item["name"])
    long_short_value = []
    for item in json_data["data"]["datas2"]:
        long_short_value.append(item["value"])
    symbol_df = pd.DataFrame([symbol_name, symbol_value]).T
    long_short_df = pd.DataFrame([long_short_name, long_short_value]).T
    symbol_df.columns = ["name", "value"]
    symbol_df["ratio"] = symbol_df["value"] / symbol_df["value"].sum()
    symbol_df["date"] = date
    long_short_df.columns = ["name", "value"]
    long_short_df["ratio"] = long_short_df["value"] / long_short_df["value"].sum()
    long_short_df["date"] = date
    return symbol_df, long_short_df


def get_qhkc_fund_money_change(
    date: datetime.datetime.date = "20190924", url: AnyStr = QHKC_FUND_DEAL_URL
):
    """
    奇货可查-资金-成交额分布
    可获取数据的时间段为:"2016-10-10:2019-09-30"
    :param url: 网址
    :param date: 中文名称
    :return: pd.DataFrame
        name        value        ratio        date
       沪镍    2.292e+10     0.145963  2019-09-25
       沪银  1.22788e+10    0.0781956  2019-09-25
       沪金  11196166005    0.0713011  2019-09-25
       IC  1.10958e+10    0.0706619  2019-09-25
      螺纹钢  1.02918e+10    0.0655416  2019-09-25
       IF   9134893794    0.0581742  2019-09-25
      铁矿石   7991427128    0.0508922  2019-09-25
       原油   7695016910    0.0490045  2019-09-25
       焦炭   5936589656    0.0378063  2019-09-25
       甲醇  4.00966e+09    0.0255349  2019-09-25
       沪铜   3806033147    0.0242381  2019-09-25
      乙二醇  3.64376e+09    0.0232047  2019-09-25
       橡胶   3286445958    0.0209292  2019-09-25
      燃料油   3227355810    0.0205529  2019-09-25
       豆粕   3124163112    0.0198958  2019-09-25
       苹果  3.08134e+09    0.0196231  2019-09-25
       沪锌   3076039116    0.0195893  2019-09-25
      PTA  2.93901e+09    0.0187167  2019-09-25
       IH   2578970688    0.0164238  2019-09-25
       豆油   2371404714    0.0151019  2019-09-25
       沥青  2.17662e+09    0.0138615  2019-09-25
       白糖   1814626125    0.0115562  2019-09-25
      棕榈油   1687834936    0.0107487  2019-09-25
       菜粕  1.58244e+09    0.0100775  2019-09-25
       焦煤  1.52553e+09   0.00971509  2019-09-25
       PP  1.51981e+09    0.0096787  2019-09-25
       塑料   1468988065   0.00935503  2019-09-25
       沪铝  1.35968e+09   0.00865893  2019-09-25
      不锈钢   1213656556   0.00772899  2019-09-25
       棉花   1186243285   0.00755441  2019-09-25
       鸡蛋   1175239681   0.00748433  2019-09-25
       热卷  1.12293e+09   0.00715118  2019-09-25
       纸浆  9.23876e+08   0.00588356  2019-09-25
       沪铅    659297524   0.00419864  2019-09-25
       菜油    587372274   0.00374059  2019-09-25
       郑煤  5.82494e+08   0.00370953  2019-09-25
       红枣    499089640   0.00317838  2019-09-25
       玉米    458548474    0.0029202  2019-09-25
      PVC    334434410   0.00212979  2019-09-25
       玻璃    333819628   0.00212588  2019-09-25
       沪锡  2.02186e+08   0.00128759  2019-09-25
       豆二    185554169   0.00118167  2019-09-25
       豆一    184729205   0.00117642  2019-09-25
       硅铁  1.54719e+08  0.000985305  2019-09-25
       淀粉    112331976  0.000715369  2019-09-25
       锰硅  1.10791e+08  0.000705557  2019-09-25
       尿素     78648750  0.000500862  2019-09-25
       棉纱  5.17932e+07  0.000329837  2019-09-25
       NR     34806750  0.000221661  2019-09-25
       粳米      7375683  4.69709e-05  2019-09-25
      油菜籽      2680922   1.7073e-05  2019-09-25
      纤维板      2286460   1.4561e-05  2019-09-25
      胶合板       831250  5.29369e-06  2019-09-25
       强麦       472400  3.00841e-06  2019-09-25
      晚籼稻       159318  1.01459e-06  2019-09-25
       线材        90608  5.77023e-07  2019-09-25
       粳稻            0            0  2019-09-25
       普麦            0            0  2019-09-25
       稻谷            0            0  2019-09-25
    """
    date = str(date)
    date = date[:4] + "-" + date[4:6] + "-" + date[6:]
    print(date)
    payload_id = {"date": date}
    r = requests.post(url, data=payload_id)
    print(url)
    print("数据获取成功")
    json_data = r.json()
    symbol_name = []
    for item in json_data["data"]["datas"]:
        symbol_name.append(item["name"])
    symbol_value = []
    for item in json_data["data"]["datas"]:
        symbol_value.append(item["value"])
    symbol_df = pd.DataFrame([symbol_name, symbol_value]).T
    symbol_df.columns = ["name", "value"]
    symbol_df["ratio"] = symbol_df["value"] / symbol_df["value"].sum()
    symbol_df["date"] = date
    return symbol_df


if __name__ == "__main__":
    # df1, df2 = get_qhkc_fund_bs(20190925)
    # print(df1)
    # print(df2)

    # df1, df2 = get_qhkc_fund_position(20190925)
    # print(df1)
    # print(df2)

    # df1, df2 = get_qhkc_fund_position_change(20190925)
    # print(df1)
    # print(df2)

    get_qhkc_fund_money_change_df = get_qhkc_fund_money_change(20211208)
    print(get_qhkc_fund_money_change_df)
