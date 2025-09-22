#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/12/12 17:00
Desc: 生意社网站采集大宗商品现货价格及相应基差数据, 数据时间段从 20110104-至今
备注：现期差 = 现货价格 - 期货价格(这里的期货价格为结算价)
黄金为 元/克, 白银为 元/千克, 玻璃现货为 元/平方米, 鸡蛋现货为 元/公斤, 鸡蛋期货为 元/500千克, 其余为 元/吨.
焦炭现货规格是: 一级冶金焦; 焦炭期货规格: 介于一级和二级之间, 焦炭现期差仅供参考.
铁矿石现货价格是: 湿吨, 铁矿石期货价格是: 干吨
网页地址: https://www.100ppi.com/sf/
历史数据可以通过修改 url 地址来获取, 比如: https://www.100ppi.com/sf/day-2017-09-12.html
发现生意社的 bugs:
1. 2018-09-12 周三 数据缺失是因为生意社源数据在该交易日缺失: https://www.100ppi.com/sf/day-2018-09-12.html
"""

import datetime
import re
import time
import warnings
from typing import List

import pandas as pd

from akshare.futures import cons
from akshare.futures.requests_fun import pandas_read_html_link
from akshare.futures.symbol_var import chinese_to_english

calendar = cons.get_calendar()


def futures_spot_price_daily(
    start_day: str = "20210201",
    end_day: str = "20210208",
    vars_list: list = cons.contract_symbols,
):
    """
    指定时间段内大宗商品现货价格及相应基差
    https://www.100ppi.com/sf/
    :param start_day: str 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象; 默认为当天
    :param end_day: str 结束数据 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象; 默认为当天
    :param vars_list: list 合约品种如 [RB, AL]; 默认参数为所有商品
    :return: pandas.DataFrame
    展期收益率数据:
    var               商品品种                      string
    sp                现货价格                      float
    near_symbol       临近交割合约                  string
    near_price        临近交割合约结算价             float
    dom_symbol        主力合约                      string
    dom_price         主力合约结算价                 float
    near_basis        临近交割合约相对现货的基差      float
    dom_basis         主力合约相对现货的基差          float
    near_basis_rate   临近交割合约相对现货的基差率    float
    dom_basis_rate    主力合约相对现货的基差率        float
    date              日期                          string YYYYMMDD
    """
    start_day = (
        cons.convert_date(start_day) if start_day is not None else datetime.date.today()
    )
    end_day = (
        cons.convert_date(end_day)
        if end_day is not None
        else cons.convert_date(cons.get_latest_data_date(datetime.datetime.now()))
    )
    df_list = []
    while start_day <= end_day:
        temp_df = futures_spot_price(start_day, vars_list)
        if temp_df is False:
            return pd.concat(df_list).reset_index(drop=True)
        elif temp_df is not None:
            df_list.append(temp_df)
        start_day += datetime.timedelta(days=1)
    if len(df_list) > 0:
        temp_df = pd.concat(df_list)
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df


def futures_spot_price(
    date: str = "20240430", vars_list: list = cons.contract_symbols
) -> pd.DataFrame:
    """
    指定交易日大宗商品现货价格及相应基差
    https://www.100ppi.com/sf/day-2017-09-12.html
    :param date: 开始日期 format: YYYY-MM-DD 或 YYYYMMDD 或 datetime.date 对象; 为空时为当天
    :param vars_list: 合约品种如 RB、AL 等列表 为空时为所有商品
    :return: pandas.DataFrame
    展期收益率数据:
    var              商品品种                     string
    sp               现货价格                     float
    near_symbol      临近交割合约                  string
    near_price       临近交割合约结算价             float
    dom_symbol       主力合约                     string
    dom_price        主力合约结算价                float
    near_basis       临近交割合约相对现货的基差      float
    dom_basis        主力合约相对现货的基差         float
    near_basis_rate  临近交割合约相对现货的基差率    float
    dom_basis_rate   主力合约相对现货的基差率       float
    date             日期                         string YYYYMMDD
    """
    date = cons.convert_date(date) if date is not None else datetime.date.today()
    if date < datetime.date(2011, 1, 4):
        raise Exception(
            "数据源开始日期为 20110104, 请将获取数据时间点设置在 20110104 后"
        )
    if date.strftime("%Y%m%d") not in calendar:
        warnings.warn(f"{date.strftime('%Y%m%d')}非交易日")
        return pd.DataFrame()
    u1 = "https://www.100ppi.com/sf/"
    u2 = f'https://www.100ppi.com/sf/day-{date.strftime("%Y-%m-%d")}.html'
    i = 1
    while True:
        for url in [u2, u1]:
            try:
                # url = u2
                r = pandas_read_html_link(url)
                string = r[0].loc[1, 1]
                news = "".join(re.findall(r"[0-9]", string))
                if news[3:11] == date.strftime("%Y%m%d"):
                    records = _check_information(r[1], date)
                    records.index = records["symbol"]
                    var_list_in_market = [i for i in vars_list if i in records.index]
                    temp_df = records.loc[var_list_in_market, :]
                    temp_df.reset_index(drop=True, inplace=True)
                    return temp_df
                else:
                    time.sleep(3)
            except Exception as e:  # noqa: E722
                print(
                    f"{date.strftime('%Y-%m-%d')}日生意社数据连接失败[错误信息:{e}]，第{str(i)}次尝试，最多5次"
                )
                i += 1
                if i > 5:
                    print(
                        f"{date.strftime('%Y-%m-%d')}日生意社数据连接失败, 如果当前交易日是 2018-09-12, "
                        f"由于生意社源数据缺失, 无法访问, 否则为重复访问已超过5次，您的地址被网站墙了，"
                        f"请保存好返回数据，稍后从该日期起重试"
                    )
                    return pd.DataFrame()


def _check_information(df_data, date):
    """
    数据验证和计算模块
    :param df_data: pandas.DataFrame 采集的数据
    :param date: datetime.date 具体某一天 YYYYMMDD
    :return: pandas.DataFrame
    中间数据
    symbol  spot_price near_contract  ...  near_basis_rate dom_basis_rate      date
     CU    49620.00        cu1811  ...        -0.002418      -0.003426  20181108
     RB     4551.54        rb1811  ...        -0.013521      -0.134359  20181108
     ZN    22420.00        zn1811  ...        -0.032114      -0.076271  20181108
     AL    13900.00        al1812  ...         0.005396       0.003957  20181108
     AU      274.10        au1811  ...         0.005655       0.020430  20181108
     WR     4806.25        wr1903  ...        -0.180026      -0.237035  20181108
     RU    10438.89        ru1811  ...        -0.020969       0.084406  20181108
     PB    18600.00        pb1811  ...        -0.001344      -0.010215  20181108
     AG     3542.67        ag1811  ...        -0.000754       0.009408  20181108
     BU     4045.53        bu1811  ...        -0.129904      -0.149679  20181108
     HC     4043.33        hc1811  ...        -0.035449      -0.088128  20...
    """
    df_data = df_data.loc[:, [0, 1, 2, 3, 5, 6]]
    df_data.columns = [
        "symbol",
        "spot_price",
        "near_contract",
        "near_contract_price",
        "dominant_contract",
        "dominant_contract_price",
    ]
    records = pd.DataFrame()
    for string in df_data["symbol"].tolist():
        news = "".join(re.findall(r"[\u4e00-\u9fa5]", string))
        if news == "":
            news = string.strip()

        """
        if string == "PTA":
            news = "PTA"
        else:
            news = "".join(re.findall(r"[\u4e00-\u9fa5]", string))
        """

        if news != "" and news not in [
            "商品",
            "价格",
            "上海期货交易所",
            "郑州商品交易所",
            "大连商品交易所",
            "广州期货交易所",
            # 某些天网站没有数据，比如 20180912，此时返回"暂无数据"，但并不是网站被墙了
            "暂无数据",
        ]:
            symbol = chinese_to_english(news)
            record = pd.DataFrame(df_data[df_data["symbol"] == string])
            record.loc[:, "symbol"] = symbol
            record.loc[:, "spot_price"] = record.loc[:, "spot_price"].astype(float)
            if (
                symbol == "JD"
            ):  # 鸡蛋现货为元/公斤, 鸡蛋期货为元/500千克, 其余元/吨(http://www.100ppi.com/sf/)
                record.loc[:, "spot_price"] = float(record["spot_price"].iloc[0]) * 500
            elif (
                symbol == "FG"
            ):  # 上表中现货单位为元/平方米, 期货单位为元/吨. 换算公式：元/平方米*80=元/吨(http://www.100ppi.com/sf/959.html)
                record.loc[:, "spot_price"] = float(record["spot_price"].iloc[0]) * 80
            elif (
                symbol == "LH"
            ):  # 上表中现货单位为元/公斤, 期货单位为元/吨. 换算公式：元/公斤*1000=元/吨(http://www.100ppi.com/sf/959.html)
                record.loc[:, "spot_price"] = float(record["spot_price"].iloc[0]) * 1000
            records = pd.concat([records, record])

    # 20241129:如果某日没有数据，直接返回返回空表
    if records.empty:
        records = df_data.iloc[0:0]
        records["near_basis"] = pd.Series(dtype="float")
        records["dom_basis"] = pd.Series(dtype="float")
        records["near_basis_rate"] = pd.Series(dtype="float")
        records["dom_basis_rate"] = pd.Series(dtype="float")
        records["date"] = pd.Series(dtype="object")
        return records

    records.loc[:, ["near_contract_price", "dominant_contract_price", "spot_price"]] = (
        records.loc[
            :, ["near_contract_price", "dominant_contract_price", "spot_price"]
        ].astype("float")
    )

    records.loc[:, "near_contract"] = records["near_contract"].replace(
        r"[^0-9]*(\d*)$", r"\g<1>", regex=True
    )
    records.loc[:, "dominant_contract"] = records["dominant_contract"].replace(
        r"[^0-9]*(\d*)$", r"\g<1>", regex=True
    )

    records.loc[:, "near_month"] = records.loc[:, "near_contract"]
    records.loc[:, "near_contract"] = records["symbol"] + records.loc[
        :, "near_contract"
    ].astype("int").astype("str")
    records.loc[:, "dominant_month"] = records.loc[:, "dominant_contract"]
    records.loc[:, "dominant_contract"] = records["symbol"] + records.loc[
        :, "dominant_contract"
    ].astype("int").astype("str")

    records["near_contract"] = records["near_contract"].apply(
        lambda x: x.lower()
        if x[:-4]
        in cons.market_exchange_symbols["shfe"] + cons.market_exchange_symbols["dce"]
        else x
    )
    records.loc[:, "dominant_contract"] = records.loc[:, "dominant_contract"].apply(
        lambda x: x.lower()
        if x[:-4]
        in cons.market_exchange_symbols["shfe"] + cons.market_exchange_symbols["dce"]
        else x
    )
    records.loc[:, "near_contract"] = records.loc[:, "near_contract"].apply(
        lambda x: x[:-4] + x[-3:]
        if x[:-4] in cons.market_exchange_symbols["czce"]
        else x
    )
    records.loc[:, "dominant_contract"] = records.loc[:, "dominant_contract"].apply(
        lambda x: x[:-4] + x[-3:]
        if x[:-4] in cons.market_exchange_symbols["czce"]
        else x
    )

    records["near_basis"] = records["near_contract_price"] - records["spot_price"]
    records["dom_basis"] = records["dominant_contract_price"] - records["spot_price"]
    records["near_basis_rate"] = (
        records["near_contract_price"] / records["spot_price"] - 1
    )
    records["dom_basis_rate"] = (
        records["dominant_contract_price"] / records["spot_price"] - 1
    )
    # records.loc[:, "date"] = date.strftime("%Y%m%d")
    records.insert(0, "date", date.strftime("%Y%m%d"))
    return records


def _join_head(content: pd.DataFrame) -> List:
    headers = []
    for s1, s2 in zip(content.iloc[0], content.iloc[1]):
        if s1 != s2:
            s = f"{s1}{s2}"
        else:
            s = s1
        headers.append(s)
    return headers


def futures_spot_price_previous(date: str = "20240430") -> pd.DataFrame:
    """
    具体交易日大宗商品现货价格及相应基差
    https://www.100ppi.com/sf/day-2017-09-12.html
    :param date: 交易日; 历史日期
    :type date: str
    :return: 现货价格及相应基差
    :rtype: pandas.DataFrame
    """
    date = cons.convert_date(date) if date is not None else datetime.date.today()
    if date < datetime.date(2011, 1, 4):
        raise Exception(
            "数据源开始日期为 20110104, 请将获取数据时间点设置在 20110104 后"
        )
    if date.strftime("%Y%m%d") not in calendar:
        warnings.warn(f"{date.strftime('%Y%m%d')}非交易日")
        return pd.DataFrame()
    url = date.strftime("https://www.100ppi.com/sf2/day-%Y-%m-%d.html")
    content = pandas_read_html_link(url)
    main = content[1]
    # Header
    header = _join_head(main)
    # Values
    values = main[main[4].str.endswith("%")]
    values.columns = header
    # Basis
    # 对于没有数据的天，xml文件中没有数据，所以content[2:-1]可能为空
    if len(content[2:-1]) > 0:
        basis = pd.concat(content[2:-1])
    else:
        basis = pd.DataFrame(columns=["主力合约基差", "主力合约基差(%)"])

    basis.columns = ["主力合约基差", "主力合约基差(%)"]
    # 20241125(jasonudu)：因为部分日期，存在多个品种的现货价格，比如20151125的白糖、豆粕、豆油等，如果用商品名来merge，会出现重复列名，所以改用index来merge
    # basis["商品"] = values["商品"].tolist()
    basis.index = values.index
    basis = pd.merge(
        values[["商品", "现货价格", "主力合约代码", "主力合约价格"]],
        basis,
        left_index=True,
        right_index=True,
    )
    basis = pd.merge(
        basis,
        values[
            [
                "180日内主力基差最高",
                "180日内主力基差最低",
                "180日内主力基差平均",
            ]
        ],
        left_index=True,
        right_index=True,
    )
    basis.columns = [
        "商品",
        "现货价格",
        "主力合约代码",
        "主力合约价格",
        "主力合约基差",
        "主力合约变动百分比",
        "180日内主力基差最高",
        "180日内主力基差最低",
        "180日内主力基差平均",
    ]
    basis["主力合约变动百分比"] = basis["主力合约变动百分比"].str.strip("%")
    return basis


if __name__ == "__main__":
    futures_spot_price_daily_df = futures_spot_price_daily(
        start_day="20250708", end_day="20250709", vars_list=["BZ", "RB"]
    )
    print(futures_spot_price_daily_df)

    futures_spot_price_df = futures_spot_price(date="20250620")
    print(futures_spot_price_df)

    futures_spot_price_previous_df = futures_spot_price_previous(date="20240430")
    print(futures_spot_price_previous_df)
