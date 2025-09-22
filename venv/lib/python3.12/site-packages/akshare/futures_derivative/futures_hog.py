#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/3/18 14:00
Desc: 玄田数据
https://zhujia.zhuwang.com.cn
"""

import pandas as pd
import requests


def futures_hog_core(symbol: str = "外三元") -> pd.DataFrame:
    """
    玄田数据-核心数据
    https://zhujia.zhuwang.com.cn
    :param symbol: choice of {"外三元", "内三元", "土杂猪"}
    :type symbol: str
    :return: 玄田数据-核心数据
    :rtype: pandas.DataFrame
    """
    if symbol == "外三元":
        url = "https://xt.yangzhu.vip/data/getzhujiahitsdata"
        params = {"ptype": "1", "areano": "-1", "datetype": "0"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["value", "date"]
        temp_df = temp_df[["date", "value"]]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df
    elif symbol == "内三元":
        url = "https://xt.yangzhu.vip/data/getzhujiahitsdata"
        params = {"ptype": "2", "areano": "-1", "datetype": "0"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["value", "date"]
        temp_df = temp_df[["date", "value"]]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df
    elif symbol == "土杂猪":
        url = "https://xt.yangzhu.vip/data/getzhujiahitsdata"
        params = {"ptype": "3", "areano": "-1", "datetype": "0"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["value", "date"]
        temp_df = temp_df[["date", "value"]]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df


def futures_hog_cost(symbol: str = "玉米") -> pd.DataFrame:
    """
    玄田数据-成本维度
    https://zhujia.zhuwang.com.cn
    :param symbol: choice of {"玉米", "豆粕", "二元母猪价格", "仔猪价格"}
    :type symbol: str
    :return: 玄田数据-成本维度
    :rtype: pandas.DataFrame
    """
    if symbol == "玉米":
        url = "https://xt.yangzhu.vip/data/getzhujiahitsdata"
        params = {"ptype": "4", "areano": "-1", "datetype": "0"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["value", "date"]
        temp_df = temp_df[["date", "value"]]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df
    elif symbol == "豆粕":
        url = "https://xt.yangzhu.vip/data/getzhujiahitsdata"
        params = {"ptype": "5", "areano": "-1", "datetype": "0"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["value", "date"]
        temp_df = temp_df[["date", "value"]]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df
    elif symbol == "二元母猪价格":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {
            "ptype": "1",
            "areano": "-1",
        }
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["date", "value"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df
    elif symbol == "仔猪价格":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {
            "ptype": "2",
            "areano": "-1",
        }
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["date", "value"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df


def futures_hog_supply(symbol: str = "猪肉批发价") -> pd.DataFrame:
    """
    玄田数据-供应维度
    https://zhujia.zhuwang.com.cn
    :param symbol: choice of {"猪肉批发价", "储备冻猪肉", "饲料原料数据", "白条肉",
    "生猪产能", "育肥猪", "肉类价格指数", "猪粮比价"}
    :type symbol: str
    :return: 玄田数据-供应维度
    :rtype: pandas.DataFrame
    """
    if symbol == "猪肉批发价":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {"ptype": "3", "areano": "-1"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["date", "item", "value"]
        del temp_df["item"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df
    elif symbol == "储备冻猪肉":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {"ptype": "4", "areano": "-1"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["date", "value"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df
    elif symbol == "饲料原料数据":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {"ptype": "5", "areano": "-1"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = [
            "周期",
            "大豆进口金额",
            "大豆播种面积",
            "玉米进口金额",
            "玉米播种面积",
        ]
        temp_df["周期"] = temp_df["周期"].astype(int).astype(str)
        temp_df["大豆进口金额"] = pd.to_numeric(
            temp_df["大豆进口金额"], errors="coerce"
        )
        temp_df["大豆播种面积"] = pd.to_numeric(
            temp_df["大豆播种面积"], errors="coerce"
        )
        temp_df["玉米进口金额"] = pd.to_numeric(
            temp_df["玉米进口金额"], errors="coerce"
        )
        temp_df["玉米播种面积"] = pd.to_numeric(
            temp_df["玉米播种面积"], errors="coerce"
        )
        return temp_df
    elif symbol == "白条肉":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {"ptype": "6", "areano": "-1"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["周期", "白条肉平均出厂价格", "环比", "同比"]
        temp_df["白条肉平均出厂价格"] = pd.to_numeric(
            temp_df["白条肉平均出厂价格"], errors="coerce"
        )
        temp_df["环比"] = pd.to_numeric(temp_df["环比"], errors="coerce")
        temp_df["同比"] = pd.to_numeric(temp_df["同比"], errors="coerce")
        return temp_df
    elif symbol == "生猪产能":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {"ptype": "7", "areano": "-1"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["周期", "能繁母猪存栏", "猪肉产量", "生猪存栏", "生猪出栏"]
        temp_df["能繁母猪存栏"] = pd.to_numeric(
            temp_df["能繁母猪存栏"], errors="coerce"
        )
        temp_df["猪肉产量"] = pd.to_numeric(temp_df["猪肉产量"], errors="coerce")
        temp_df["生猪存栏"] = pd.to_numeric(temp_df["生猪存栏"], errors="coerce")
        temp_df["生猪出栏"] = pd.to_numeric(temp_df["生猪出栏"], errors="coerce")
        return temp_df
    elif symbol == "育肥猪":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {"ptype": "9", "areano": "-1"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df = temp_df[["date", "benzhou"]]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["benzhou"] = pd.to_numeric(temp_df["benzhou"], errors="coerce")
        return temp_df
    elif symbol == "肉类价格指数":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {"ptype": "10", "areano": "-1"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["date", "item", "value"]
        del temp_df["item"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df
    elif symbol == "猪粮比价":
        url = "https://xt.yangzhu.vip/data/getmapdata"
        params = {"ptype": "11", "areano": "-1"}
        r = requests.post(url, params=params)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["data"])
        temp_df.columns = ["date", "value"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["value"] = pd.to_numeric(temp_df["value"], errors="coerce")
        return temp_df


if __name__ == "__main__":
    futures_hog_core_df = futures_hog_core(symbol="外三元")
    print(futures_hog_core_df)

    futures_hog_core_df = futures_hog_core(symbol="内三元")
    print(futures_hog_core_df)

    futures_hog_core_df = futures_hog_core(symbol="土杂猪")
    print(futures_hog_core_df)

    futures_hog_cost_df = futures_hog_cost(symbol="玉米")
    print(futures_hog_cost_df)

    futures_hog_cost_df = futures_hog_cost(symbol="豆粕")
    print(futures_hog_cost_df)

    futures_hog_cost_df = futures_hog_cost(symbol="二元母猪价格")
    print(futures_hog_cost_df)

    futures_hog_cost_df = futures_hog_cost(symbol="仔猪价格")
    print(futures_hog_cost_df)

    futures_hog_supply_df = futures_hog_supply(symbol="猪肉批发价")
    print(futures_hog_supply_df)

    futures_hog_supply_df = futures_hog_supply(symbol="储备冻猪肉")
    print(futures_hog_supply_df)

    futures_hog_supply_df = futures_hog_supply(symbol="饲料原料数据")
    print(futures_hog_supply_df)

    futures_hog_supply_df = futures_hog_supply(symbol="白条肉")
    print(futures_hog_supply_df)

    futures_hog_supply_df = futures_hog_supply(symbol="生猪产能")
    print(futures_hog_supply_df)

    futures_hog_supply_df = futures_hog_supply(symbol="育肥猪")
    print(futures_hog_supply_df)

    futures_hog_supply_df = futures_hog_supply(symbol="肉类价格指数")
    print(futures_hog_supply_df)

    futures_hog_supply_df = futures_hog_supply(symbol="猪粮比价")
    print(futures_hog_supply_df)
