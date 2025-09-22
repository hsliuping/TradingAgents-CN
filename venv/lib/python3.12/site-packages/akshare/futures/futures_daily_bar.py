#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/11/30 18:00
Desc: 期货日线行情
"""

import datetime
import json
import re
import zipfile
from io import BytesIO, StringIO

import numpy as np
import pandas as pd
import requests

from akshare.futures import cons
from akshare.futures.requests_fun import requests_link

calendar = cons.get_calendar()


def _futures_daily_czce(
    date: str = "20100824", dataset: str = "datahistory2010"
) -> pd.DataFrame:
    """
    郑州商品交易所-交易数据-历史行情下载
    http://www.czce.com.cn/cn/jysj/lshqxz/H770319index_1.htm
    :param date: 需要的日期
    :type date: str
    :param dataset: 数据集的名称; 此处只需要替换 datahistory2010 中的 2010 即可
    :type dataset: str
    :return: 指定日期的所有品种行情数据
    :rtype: pandas.DataFrame
    """
    url = f"http://www.czce.com.cn/cn/exchange/{dataset}.zip"
    r = requests.get(url)
    with zipfile.ZipFile(BytesIO(r.content)) as file:
        with file.open(f"{dataset}.txt") as my_file:
            data = my_file.read().decode("gb2312")
            data_df = pd.read_table(StringIO(data), sep=r"|", header=1)
            data_df.columns = [item.strip() for item in data_df.columns]
            data_df.dropna(axis=1, inplace=True)
            for column in data_df.columns:
                try:
                    data_df[column] = data_df[column].str.strip("\t")
                    data_df[column] = data_df[column].str.replace(",", "")
                except:  # noqa: E722
                    data_df[column] = data_df[column]
    data_df["昨结算"] = pd.to_numeric(data_df["昨结算"])
    data_df["今开盘"] = pd.to_numeric(data_df["今开盘"])
    data_df["最高价"] = pd.to_numeric(data_df["最高价"])
    data_df["最低价"] = pd.to_numeric(data_df["最低价"])
    data_df["今收盘"] = pd.to_numeric(data_df["今收盘"])
    data_df["今结算"] = pd.to_numeric(data_df["今结算"])
    data_df["涨跌1"] = pd.to_numeric(data_df["涨跌1"])
    data_df["涨跌2"] = pd.to_numeric(data_df["涨跌2"])
    data_df["成交量(手)"] = pd.to_numeric(data_df["成交量(手)"])
    data_df["空盘量"] = pd.to_numeric(data_df["空盘量"])
    data_df["增减量"] = pd.to_numeric(data_df["增减量"])
    data_df["成交额(万元)"] = pd.to_numeric(data_df["成交额(万元)"])
    data_df["交割结算价"] = pd.to_numeric(data_df["交割结算价"])
    data_df["交易日期"] = pd.to_datetime(data_df["交易日期"])
    data_df.columns = [
        "date",
        "symbol",
        "pre_settle",
        "open",
        "high",
        "low",
        "close",
        "settle",
        "-",
        "-",
        "volume",
        "open_interest",
        "-",
        "turnover",
        "-",
    ]
    variety_list = [
        re.compile(r"[a-zA-Z_]+").findall(item)[0] for item in data_df["symbol"]
    ]
    data_df["variety"] = variety_list
    data_df = data_df[
        [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_interest",
            "turnover",
            "settle",
            "pre_settle",
            "variety",
        ]
    ]
    temp_df = data_df[data_df["date"] == pd.Timestamp(date)].copy()
    temp_df["date"] = date
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


def get_cffex_daily(date: str = "20100416") -> pd.DataFrame:
    """
    中国金融期货交易所-日频率交易数据
    http://www.cffex.com.cn/rtj/
    :param date: 交易日; 数据开始时间为 20100416
    :type date: str
    :return: 日频率交易数据
    :rtype: pandas.DataFrame
    """
    day = cons.convert_date(date) if date is not None else datetime.date.today()
    if day.strftime("%Y%m%d") not in calendar:
        # warnings.warn("%s非交易日" % day.strftime("%Y%m%d"))
        return pd.DataFrame()
    url = f"http://www.cffex.com.cn/sj/historysj/{date[:-2]}/zip/{date[:-2]}.zip"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36",
    }
    r = requests.get(url, headers=headers)
    try:
        with zipfile.ZipFile(BytesIO(r.content)) as file:
            with file.open(f"{date}_1.csv") as my_file:
                data = my_file.read().decode("gb2312")
                data_df = pd.read_csv(StringIO(data))
    except:  # noqa: E722
        return pd.DataFrame()
    data_df = data_df[data_df["合约代码"] != "小计"]
    data_df = data_df[data_df["合约代码"] != "合计"]
    data_df = data_df[~data_df["合约代码"].str.contains("IO")]
    data_df = data_df[~data_df["合约代码"].str.contains("MO")]
    data_df = data_df[~data_df["合约代码"].str.contains("HO")]
    data_df.reset_index(inplace=True, drop=True)
    data_df["合约代码"] = data_df["合约代码"].str.strip()
    symbol_list = data_df["合约代码"].to_list()
    variety_list = [re.compile(r"[a-zA-Z_]+").findall(item)[0] for item in symbol_list]
    if data_df.shape[1] == 15:
        data_df.columns = [
            "symbol",
            "open",
            "high",
            "low",
            "volume",
            "turnover",
            "open_interest",
            "_",
            "close",
            "settle",
            "pre_settle",
            "_",
            "_",
            "_",
            "_",
        ]
    else:
        data_df.columns = [
            "symbol",
            "open",
            "high",
            "low",
            "volume",
            "turnover",
            "open_interest",
            "_",
            "close",
            "settle",
            "pre_settle",
            "_",
            "_",
            "_",
        ]
    data_df["date"] = date
    data_df["variety"] = variety_list
    data_df = data_df[
        [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_interest",
            "turnover",
            "settle",
            "pre_settle",
            "variety",
        ]
    ]
    return data_df


def get_gfex_daily(date: str = "20221223") -> pd.DataFrame:
    """
    广州期货交易所-日频率-量价数据
    广州期货交易所: 工业硅(上市时间: 20221222)
    http://www.gfex.com.cn/gfex/rihq/hqsj_tjsj.shtml
    :param date: 日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象，默认为当前交易日
    :type date: str or datetime.date
    :return: 广州期货交易所-日频率-量价数据
    :rtype: pandas.DataFrame
    """
    day = cons.convert_date(date) if date is not None else datetime.date.today()
    if day.strftime("%Y%m%d") not in calendar:
        # warnings.warn(f"{day.strftime('%Y%m%d')}非交易日")
        return pd.DataFrame()
    url = "http://www.gfex.com.cn/u/interfacesWebTiDayQuotes/loadList"
    payload = {"trade_date": date, "trade_type": "0"}
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Content-Length": "32",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "www.gfex.com.cn",
        "Origin": "http://www.gfex.com.cn",
        "Pragma": "no-cache",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://www.gfex.com.cn/gfex/rihq/hqsj_tjsj.shtml",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "content-type": "application/x-www-form-urlencoded",
    }
    r = requests.post(url, data=payload, headers=headers)
    try:
        data_json = r.json()
    except:  # noqa: E722
        return pd.DataFrame()
    result_df = pd.DataFrame(data_json["data"])
    result_df = result_df[~result_df["variety"].str.contains("小计")]
    result_df = result_df[~result_df["variety"].str.contains("总计")]
    result_df["symbol"] = (
        result_df["varietyOrder"].str.upper() + result_df["delivMonth"]
    )
    result_df["date"] = date
    result_df["open"] = pd.to_numeric(result_df["open"], errors="coerce")
    result_df["high"] = pd.to_numeric(result_df["high"], errors="coerce")
    result_df["low"] = pd.to_numeric(result_df["low"], errors="coerce")
    result_df["close"] = pd.to_numeric(result_df["close"], errors="coerce")
    result_df["volume"] = pd.to_numeric(result_df["volumn"], errors="coerce")
    result_df["open_interest"] = pd.to_numeric(
        result_df["openInterest"], errors="coerce"
    )
    result_df["turnover"] = pd.to_numeric(result_df["turnover"], errors="coerce")
    result_df["settle"] = pd.to_numeric(result_df["clearPrice"], errors="coerce")
    result_df["pre_settle"] = pd.to_numeric(result_df["lastClear"], errors="coerce")
    result_df["variety"] = result_df["varietyOrder"].str.upper()
    result_df = result_df[
        [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_interest",
            "turnover",
            "settle",
            "pre_settle",
            "variety",
        ]
    ]
    return result_df


def get_ine_daily(date: str = "20241129") -> pd.DataFrame:
    """
    上海国际能源交易中心-日频率-量价数据
    上海国际能源交易中心: 原油期货(上市时间: 20180326); 20号胶期货(上市时间: 20190812)
    trade_price: https://www.ine.cn/statements/daily/?paramid=kx
    trade_note: https://www.ine.cn/data/datanote.dat
    :param date: 日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象，默认为当前交易日
    :type date: str or datetime.date
    :return: 上海国际能源交易中心-日频率-量价数据
    :rtype: pandas.DataFrame or None
    """
    day = cons.convert_date(date) if date is not None else datetime.date.today()
    if day.strftime("%Y%m%d") not in calendar:
        # warnings.warn(f"{day.strftime('%Y%m%d')}非交易日")
        return pd.DataFrame()
    url = f"https://www.ine.cn/data/tradedata/future/dailydata/kx{day.strftime('%Y%m%d')}.dat"
    r = requests.get(url, headers=cons.shfe_headers)
    result_df = pd.DataFrame()
    try:
        data_json = r.json()
    except:  # noqa: E722
        return pd.DataFrame()
    temp_df = pd.DataFrame(data_json["o_curinstrument"]).iloc[:-1, :]
    temp_df = temp_df[temp_df["DELIVERYMONTH"] != "小计"]
    temp_df = temp_df[~temp_df["PRODUCTNAME"].str.contains("总计")]
    try:
        result_df["symbol"] = (
            temp_df["PRODUCTGROUPID"].str.upper().str.strip() + temp_df["DELIVERYMONTH"]
        )
    except:  # noqa: E722
        result_df["symbol"] = (
            temp_df["PRODUCTID"]
            .str.upper()
            .str.strip()
            .str.split("_", expand=True)
            .iloc[:, 0]
            + temp_df["DELIVERYMONTH"]
        )
    result_df["date"] = day.strftime("%Y%m%d")
    result_df["open"] = temp_df["OPENPRICE"]
    result_df["high"] = temp_df["HIGHESTPRICE"]
    result_df["low"] = temp_df["LOWESTPRICE"]
    result_df["close"] = temp_df["CLOSEPRICE"]
    result_df["volume"] = temp_df["VOLUME"]
    result_df["open_interest"] = temp_df["OPENINTEREST"]
    try:
        result_df["turnover"] = temp_df["TURNOVER"]
    except:  # noqa: E722
        result_df["turnover"] = 0
    result_df["settle"] = temp_df["SETTLEMENTPRICE"]
    result_df["pre_settle"] = temp_df["PRESETTLEMENTPRICE"]
    try:
        result_df["variety"] = temp_df["PRODUCTGROUPID"].str.upper().str.strip()
    except:  # noqa: E722
        result_df["variety"] = (
            temp_df["PRODUCTID"]
            .str.upper()
            .str.strip()
            .str.split("_", expand=True)
            .iloc[:, 0]
        )
    result_df = result_df[result_df["symbol"] != "总计"]
    result_df = result_df[~result_df["symbol"].str.contains("efp")]
    return result_df


def get_czce_daily(date: str = "20050525") -> pd.DataFrame:
    """
    郑州商品交易所-日频率-量价数据
    http://www.czce.com.cn/cn/jysj/mrhq/H770301index_1.htm
    :param date: 日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date 对象，默认为当前交易日; 日期需要大于 20100824
    :type date: str or datetime.date
    :return: 郑州商品交易所-日频率-量价数据
    :rtype: pandas.DataFrame
    """
    day = cons.convert_date(date) if date is not None else datetime.date.today()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36"
    }
    url = ""
    if day.strftime("%Y%m%d") not in calendar:
        # warnings.warn(f"{day.strftime('%Y%m%d')}非交易日")
        return pd.DataFrame()
    if day > datetime.date(2010, 8, 24):
        if day > datetime.date(2015, 11, 11):
            u = cons.CZCE_DAILY_URL_3
            url = u % (day.strftime("%Y"), day.strftime("%Y%m%d"))
        elif day <= datetime.date(2015, 11, 11):
            u = cons.CZCE_DAILY_URL_2
            url = u % (day.strftime("%Y"), day.strftime("%Y%m%d"))
        listed_columns = cons.CZCE_COLUMNS
        output_columns = cons.OUTPUT_COLUMNS
        try:
            r = requests.get(url, headers=headers)
            if datetime.date(2015, 11, 12) <= day <= datetime.date(2017, 12, 27):
                html = str(r.content, encoding="gbk")
            else:
                html = r.text
        except requests.exceptions.HTTPError as reason:
            if reason.response.status_code != 404:
                print(
                    cons.CZCE_DAILY_URL_3
                    % (day.strftime("%Y"), day.strftime("%Y%m%d")),
                    reason,
                )
            return pd.DataFrame()
        if html.find("您的访问出错了") >= 0 or html.find("无期权每日行情交易记录") >= 0:
            return pd.DataFrame()
        html = [
            i.replace(" ", "").split("|")
            for i in html.split("\n")[:-3]
            if i[0][0] != "小"
        ]

        if day > datetime.date(2015, 11, 11):
            if html[1][0] not in ["品种月份", "品种代码", "合约代码"]:
                return pd.DataFrame()
            dict_data = list()
            day_const = int(day.strftime("%Y%m%d"))
            for row in html[2:]:
                m = cons.FUTURES_SYMBOL_PATTERN.match(row[0])
                if not m:
                    continue
                row_dict = {
                    "date": day_const,
                    "symbol": row[0],
                    "variety": m.group(1),
                }
                for i, field in enumerate(listed_columns):
                    if row[i + 1] == "\r" or row[i + 1] == "":
                        row_dict[field] = 0.0
                    elif field in [
                        "volume",
                        "open_interest",
                        "oi_chg",
                        "exercise_volume",
                    ]:
                        row[i + 1] = row[i + 1].replace(",", "")
                        row_dict[field] = int(row[i + 1])
                    else:
                        row[i + 1] = row[i + 1].replace(",", "")
                        row_dict[field] = float(row[i + 1])
                dict_data.append(row_dict)
            return pd.DataFrame(dict_data)[output_columns]
        elif day <= datetime.date(2015, 11, 11):
            dict_data = list()
            day_const = int(day.strftime("%Y%m%d"))
            for row in html[1:]:
                row = row[0].split(",")
                m = cons.FUTURES_SYMBOL_PATTERN.match(row[0])
                if not m:
                    continue
                row_dict = {
                    "date": day_const,
                    "symbol": row[0],
                    "variety": m.group(1),
                }
                for i, field in enumerate(listed_columns):
                    if row[i + 1] == "\r":
                        row_dict[field] = 0.0
                    elif field in [
                        "volume",
                        "open_interest",
                        "oi_chg",
                        "exercise_volume",
                    ]:
                        row_dict[field] = int(float(row[i + 1]))
                    else:
                        row_dict[field] = float(row[i + 1])
                dict_data.append(row_dict)
            return pd.DataFrame(dict_data)[output_columns]

    if day <= datetime.date(2010, 8, 24):
        _futures_daily_czce_df = _futures_daily_czce(date)
        return _futures_daily_czce_df


def get_shfe_daily(date: str = "20220415") -> pd.DataFrame:
    """
    上海期货交易所-日频率-量价数据
    https://tsite.shfe.com.cn/statements/dataview.html?paramid=kx
    :param date: 日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象, 默认为当前交易日
    :type date: str or datetime.date
    :return: 上海期货交易所-日频率-量价数据
    :rtype: pandas.DataFrame or None
    上期所日交易数据(DataFrame):
    symbol        合约代码
    date          日期
    open          开盘价
    high          最高价
    low           最低价
    close         收盘价
    volume        成交量
    open_interest 持仓量
    turnover      成交额
    settle        结算价
    pre_settle     前结算价
    variety       合约类别
    或 None(给定交易日没有交易数据)
    """
    day = cons.convert_date(date) if date is not None else datetime.date.today()
    if day.strftime("%Y%m%d") not in calendar:
        # warnings.warn("%s非交易日" % day.strftime("%Y%m%d"))
        return pd.DataFrame()
    try:
        json_data = json.loads(
            requests_link(
                cons.SHFE_DAILY_URL_20250630 % (day.strftime("%Y%m%d")),
                headers=cons.shfe_headers,
            ).text
        )
    except requests.HTTPError as reason:
        if reason.response != 404:
            print(cons.SHFE_DAILY_URL_20250630 % (day.strftime("%Y%m%d")), reason)
        return pd.DataFrame()

    if len(json_data["o_curinstrument"]) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            row
            for row in json_data["o_curinstrument"]
            if row["DELIVERYMONTH"] not in ["小计", "合计"]
            and row["DELIVERYMONTH"] != ""
        ]
    )
    try:
        df["variety"] = df["PRODUCTGROUPID"].str.upper().str.strip()
    except KeyError:
        df["variety"] = (
            df["PRODUCTID"]
            .str.upper()
            .str.split("_", expand=True)
            .iloc[:, 0]
            .str.strip()
        )
    df["symbol"] = df["variety"] + df["DELIVERYMONTH"]
    df["date"] = day.strftime("%Y%m%d")
    df["VOLUME"] = df["VOLUME"].apply(lambda x: 0 if x == "" else x)
    try:
        df["turnover"] = df["TURNOVER"].apply(lambda x: 0 if x == "" else x)
    except KeyError:
        df["turnover"] = np.nan
    df.rename(columns=cons.SHFE_COLUMNS, inplace=True)
    df = df[~df["symbol"].str.contains("efp")]
    df = df[cons.OUTPUT_COLUMNS]
    df.reset_index(inplace=True)
    return df


def get_dce_daily(date: str = "20220308") -> pd.DataFrame:
    """
    大连商品交易所日交易数据
    http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rxq/index.html
    :param date: 交易日, e.g., 20200416
    :type date: str
    :return: 具体交易日的个品种行情数据
    :rtype: pandas.DataFrame
    """
    day = cons.convert_date(date) if date is not None else datetime.date.today()
    if day.strftime("%Y%m%d") not in calendar:
        # warnings.warn("%s非交易日" % day.strftime("%Y%m%d"))
        return pd.DataFrame()
    url = "http://www.dce.com.cn/publicweb/quotesdata/exportDayQuotesChData.html"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "86",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "www.dce.com.cn",
        "Origin": "http://www.dce.com.cn",
        "Pragma": "no-cache",
        "Referer": "http://www.dce.com.cn/publicweb/quotesdata/dayQuotesCh.html",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/84.0.4147.105 Safari/537.36",
    }
    params = {
        "dayQuotes.variety": "all",
        "dayQuotes.trade_type": "0",
        "year": date[:4],
        "month": str(int(date[4:6]) - 1),
        "day": date[6:],
        "exportFlag": "excel",
    }
    r = requests.post(url, data=params, headers=headers)
    data_df = pd.read_excel(BytesIO(r.content), header=1)
    data_df = data_df[~data_df["商品名称"].str.contains("小计")]
    data_df = data_df[~data_df["商品名称"].str.contains("总计")]
    data_df["variety"] = data_df["商品名称"].map(lambda x: cons.DCE_MAP[x])
    data_df["symbol"] = data_df["合约名称"]
    del data_df["商品名称"]
    del data_df["合约名称"]
    data_df.columns = [
        "open",
        "high",
        "low",
        "close",
        "pre_settle",
        "settle",
        "_",
        "_",
        "volume",
        "open_interest",
        "_",
        "turnover",
        "variety",
        "symbol",
    ]
    data_df["date"] = date
    data_df = data_df[
        [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_interest",
            "turnover",
            "settle",
            "pre_settle",
            "variety",
        ]
    ]
    data_df = data_df.map(lambda x: x.replace(",", ""))
    data_df = data_df.astype(
        {
            "open": "float",
            "high": "float",
            "low": "float",
            "close": "float",
            "volume": "float",
            "open_interest": "float",
            "turnover": "float",
            "settle": "float",
            "pre_settle": "float",
        }
    )
    data_df.reset_index(inplace=True, drop=True)
    return data_df


def get_futures_daily(
    start_date: str = "20220208",
    end_date: str = "20220208",
    market: str = "CFFEX",
) -> pd.DataFrame:
    """
    交易所日交易数据
    :param start_date: 开始日期 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象 为空时为当天
    :type start_date: str
    :param end_date: 结束数据 format：YYYY-MM-DD 或 YYYYMMDD 或 datetime.date对象 为空时为当天
    :type end_date: str
    :param market: 'CFFEX' 中金所, 'CZCE' 郑商所,  'SHFE' 上期所, 'DCE' 大商所 之一, 'INE' 上海国际能源交易中心, "GFEX" 广州期货交易所。默认为中金所
    :type market: str
    :return: 交易所日交易数据
    :rtype: pandas.DataFrame
    """
    if market.upper() == "CFFEX":
        f = get_cffex_daily
    elif market.upper() == "CZCE":
        f = get_czce_daily
    elif market.upper() == "SHFE":
        f = get_shfe_daily
    elif market.upper() == "DCE":
        f = get_dce_daily
    elif market.upper() == "INE":
        f = get_ine_daily
    elif market.upper() == "GFEX":
        f = get_gfex_daily
    else:
        print("Invalid Market Symbol")
        return pd.DataFrame()

    start_date = (
        cons.convert_date(start_date)
        if start_date is not None
        else datetime.date.today()
    )
    end_date = (
        cons.convert_date(end_date)
        if end_date is not None
        else cons.convert_date(cons.get_latest_data_date(datetime.datetime.now()))
    )

    df_list = list()
    while start_date <= end_date:
        df = f(date=str(start_date).replace("-", ""))
        if not df.empty:
            df_list.append(df)
        start_date += datetime.timedelta(days=1)

    if len(df_list) == 0:
        return pd.DataFrame()
    elif len(df_list) > 0:
        temp_df = pd.concat(df_list).reset_index(drop=True)
        temp_df = temp_df[~temp_df["symbol"].str.contains("efp")]
        return temp_df
    else:
        return pd.DataFrame()


if __name__ == "__main__":
    get_futures_daily_df = get_futures_daily(
        start_date="20250708", end_date="20250708", market="DCE"
    )
    print(get_futures_daily_df)

    get_dce_daily_df = get_dce_daily(date="20241118")
    print(get_dce_daily_df)

    get_cffex_daily_df = get_cffex_daily(date="20230810")
    print(get_cffex_daily_df)

    get_ine_daily_df = get_ine_daily(date="20230818")
    print(get_ine_daily_df)

    get_czce_daily_df = get_czce_daily(date="20210513")
    print(get_czce_daily_df)

    get_shfe_daily_df = get_shfe_daily(date="20250630")
    print(get_shfe_daily_df)

    get_gfex_daily_df = get_gfex_daily(date="20221228")
    print(get_gfex_daily_df)
