#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/1/14 17:00
Desc: 新浪财经-美股实时行情数据和历史行情数据
https://finance.sina.com.cn/stock/usstock/sector.shtml
"""

import json
from functools import lru_cache

import pandas as pd
import requests
import py_mini_racer
from tqdm import tqdm

from akshare.stock.cons import (
    js_hash_text,
    zh_js_decode,
    us_sina_stock_list_url,
    us_sina_stock_dict_payload,
    us_sina_stock_hist_qfq_url,
)


@lru_cache()
def __get_us_page_count() -> int:
    """
    新浪财经-美股-总页数
    https://finance.sina.com.cn/stock/usstock/sector.shtml
    :return: 美股总页数
    :rtype: int
    """
    page = "1"
    us_js_decode = (
        f"US_CategoryService.getList?page={page}&num=20&sort=&asc=0&market=&id="
    )
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(js_hash_text)
    dict_list = js_code.call("d", us_js_decode)  # 执行js解密代码
    us_sina_stock_dict_payload.update({"page": "{}".format(page)})
    res = requests.get(
        us_sina_stock_list_url.format(dict_list),
        params=us_sina_stock_dict_payload,
    )
    data_json = json.loads(res.text[res.text.find("({") + 1 : res.text.rfind(");")])
    if not isinstance(int(data_json["count"]) / 20, int):
        page_count = int(int(data_json["count"]) / 20) + 1
    else:
        page_count = int(int(data_json["count"]) / 20)
    return page_count


@lru_cache()
def get_us_stock_name() -> pd.DataFrame:
    """
    u.s. stock's english name, chinese name and symbol
    you should use symbol to get apply into the next function
    https://finance.sina.com.cn/stock/usstock/sector.shtml
    :return: stock's english name, chinese name and symbol
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page_count = __get_us_page_count()
    for page in tqdm(range(1, page_count + 1), leave=False):
        us_js_decode = (
            "US_CategoryService.getList?page={}&num=20&sort=&asc=0&market=&id=".format(
                page
            )
        )
        js_code = py_mini_racer.MiniRacer()
        js_code.eval(js_hash_text)
        dict_list = js_code.call("d", us_js_decode)  # 执行js解密代码
        us_sina_stock_dict_payload.update({"page": "{}".format(page)})
        res = requests.get(
            us_sina_stock_list_url.format(dict_list),
            params=us_sina_stock_dict_payload,
        )
        data_json = json.loads(res.text[res.text.find("({") + 1 : res.text.rfind(");")])
        big_df = pd.concat(
            objs=[big_df, pd.DataFrame(data_json["data"])], ignore_index=True
        )
    return big_df[["name", "cname", "symbol"]]


def stock_us_spot() -> pd.DataFrame:
    """
    新浪财经-所有美股的数据, 注意延迟 15 分钟
    https://finance.sina.com.cn/stock/usstock/sector.shtml
    :return: 美股所有股票实时行情
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page_count = __get_us_page_count()
    for page in tqdm(range(1, page_count + 1), leave=False):
        # page = "1"
        us_js_decode = (
            "US_CategoryService.getList?page={}&num=20&sort=&asc=0&market=&id=".format(
                page
            )
        )
        js_code = py_mini_racer.MiniRacer()
        js_code.eval(js_hash_text)
        dict_list = js_code.call("d", us_js_decode)  # 执行js解密代码
        us_sina_stock_dict_payload.update({"page": "{}".format(page)})
        res = requests.get(
            us_sina_stock_list_url.format(dict_list),
            params=us_sina_stock_dict_payload,
        )
        data_json = json.loads(res.text[res.text.find("({") + 1 : res.text.rfind(");")])
        big_df = pd.concat(
            objs=[big_df, pd.DataFrame(data_json["data"])], ignore_index=True
        )
    return big_df


def stock_us_daily(symbol: str = "FB", adjust: str = "") -> pd.DataFrame:
    """
    新浪财经-美股
    https://finance.sina.com.cn/stock/usstock/sector.shtml
    备注：
    1. CIEN 新浪复权因子错误
    2. AI 新浪复权因子错误, 该股票刚上市未发生复权, 但是返回复权因子
    :param symbol: 可以使用 get_us_stock_name 获取
    :type symbol: str
    :param adjust: "": 返回未复权的数据 ; qfq: 返回前复权后的数据; qfq-factor: 返回前复权因子和调整;
    :type adjust: str
    :return: 指定 adjust 的数据
    :rtype: pandas.DataFrame
    """
    url = f"https://finance.sina.com.cn/staticdata/us/{symbol}"
    res = requests.get(url)
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(zh_js_decode)
    dict_list = js_code.call("d", res.text.split("=")[1].split(";")[0].replace('"', ""))
    data_df = pd.DataFrame(dict_list)
    data_df["date"] = pd.to_datetime(data_df["date"]).dt.date
    data_df.index = pd.to_datetime(data_df["date"])
    del data_df["amount"]
    del data_df["date"]
    data_df = data_df.astype("float")
    url = us_sina_stock_hist_qfq_url.format(symbol)
    res = requests.get(url)
    qfq_factor_df = pd.DataFrame(eval(res.text.split("=")[1].split("\n")[0])["data"])
    qfq_factor_df.rename(
        columns={
            "c": "adjust",
            "d": "date",
            "f": "qfq_factor",
        },
        inplace=True,
    )
    qfq_factor_df.index = pd.to_datetime(qfq_factor_df["date"])
    del qfq_factor_df["date"]

    # 处理复权因子
    temp_date_range = pd.date_range("1900-01-01", qfq_factor_df.index[0].isoformat())
    temp_df = pd.DataFrame(range(len(temp_date_range)), temp_date_range)
    new_range = pd.merge(
        temp_df, qfq_factor_df, left_index=True, right_index=True, how="left"
    )
    new_range = new_range.ffill()
    new_range = new_range.iloc[:, [1, 2]]

    if adjust == "qfq":
        if len(new_range) == 1:
            new_range.index.values[0] = pd.to_datetime(str(data_df.index.date[0]))
        temp_df = pd.merge(
            data_df, new_range, left_index=True, right_index=True, how="left"
        )
        try:
            # try for pandas >= 2.1.0
            temp_df.ffill(inplace=True)
        except Exception:
            try:
                # try for pandas < 2.1.0
                temp_df.fillna(method="ffill", inplace=True)
            except Exception as e:
                print("Error:", e)
        try:
            # try for pandas >= 2.1.0
            temp_df.bfill(inplace=True)
        except Exception:
            try:
                # try for pandas < 2.1.0
                temp_df.fillna(method="bfill", inplace=True)
            except Exception as e:
                print("Error:", e)

        temp_df = temp_df.astype(float)
        temp_df["open"] = temp_df["open"] * temp_df["qfq_factor"] + temp_df["adjust"]
        temp_df["high"] = temp_df["high"] * temp_df["qfq_factor"] + temp_df["adjust"]
        temp_df["close"] = temp_df["close"] * temp_df["qfq_factor"] + temp_df["adjust"]
        temp_df["low"] = temp_df["low"] * temp_df["qfq_factor"] + temp_df["adjust"]
        temp_df = temp_df.apply(lambda x: round(x, 4))
        temp_df = temp_df.astype("float")
        # 处理复权因子错误的情况-开始
        check_df = temp_df[["open", "high", "low", "close"]].copy()
        check_df.dropna(inplace=True)
        if check_df.empty:
            data_df.reset_index(inplace=True)
            return data_df
        # 处理复权因子错误的情况-结束
        result_data = temp_df.iloc[:, :-2]
        result_data.reset_index(inplace=True)
        return result_data

    if adjust == "qfq-factor":
        qfq_factor_df.reset_index(inplace=True)
        return qfq_factor_df

    if adjust == "":
        data_df.reset_index(inplace=True)
        return data_df


if __name__ == "__main__":
    stock_us_stock_name_df = get_us_stock_name()
    print(stock_us_stock_name_df)

    stock_us_spot_df = stock_us_spot()
    print(stock_us_spot_df)

    stock_us_daily_df = stock_us_daily(symbol=".DJI", adjust="")
    print(stock_us_daily_df)

    stock_us_daily_qfq_df = stock_us_daily(symbol=".DJI", adjust="qfq")
    print(stock_us_daily_qfq_df)

    stock_us_daily_qfq_factor_df = stock_us_daily(symbol="AAPL", adjust="qfq-factor")
    print(stock_us_daily_qfq_factor_df)
