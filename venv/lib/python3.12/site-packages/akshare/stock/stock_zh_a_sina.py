#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/20 19:00
Desc: 新浪财经-A股-实时行情数据和历史行情数据(包含前复权和后复权因子)
https://finance.sina.com.cn/realstock/company/sh689009/nc.shtml
"""

import json
import re

import pandas as pd
import py_mini_racer
import requests

from akshare.stock.cons import (
    zh_sina_a_stock_payload,
    zh_sina_a_stock_url,
    zh_sina_a_stock_count_url,
    zh_sina_a_stock_hist_url,
    hk_js_decode,
    zh_sina_a_stock_hfq_url,
    zh_sina_a_stock_qfq_url,
    zh_sina_a_stock_amount_url,
)
from akshare.utils import demjson
from akshare.utils.tqdm import get_tqdm


def _get_zh_a_page_count() -> int:
    """
    所有股票的总页数
    https://vip.stock.finance.sina.com.cn/mkt/#hs_a
    :return: 需要采集的股票总页数
    :rtype: int
    """
    res = requests.get(zh_sina_a_stock_count_url)
    page_count = int(re.findall(re.compile(r"\d+"), res.text)[0]) / 80
    if isinstance(page_count, int):
        return page_count
    else:
        return int(page_count) + 1


def stock_zh_a_spot() -> pd.DataFrame:
    """
    新浪财经-所有 A 股的实时行情数据; 重复运行本函数会被新浪暂时封 IP
    https://vip.stock.finance.sina.com.cn/mkt/#hs_a
    :return: 所有股票的实时行情数据
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page_count = _get_zh_a_page_count()
    zh_sina_stock_payload_copy = zh_sina_a_stock_payload.copy()
    tqdm = get_tqdm()
    for page in tqdm(
        range(1, page_count + 1), leave=False, desc="Please wait for a moment"
    ):
        zh_sina_stock_payload_copy.update({"page": page})
        r = requests.get(zh_sina_a_stock_url, params=zh_sina_stock_payload_copy)
        data_json = demjson.decode(r.text)
        big_df = pd.concat(objs=[big_df, pd.DataFrame(data_json)], ignore_index=True)

    big_df = big_df.astype(
        {
            "trade": "float",
            "pricechange": "float",
            "changepercent": "float",
            "buy": "float",
            "sell": "float",
            "settlement": "float",
            "open": "float",
            "high": "float",
            "low": "float",
            "volume": "float",
            "amount": "float",
            "per": "float",
            "pb": "float",
            "mktcap": "float",
            "nmc": "float",
            "turnoverratio": "float",
        }
    )
    big_df.columns = [
        "代码",
        "_",
        "名称",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "买入",
        "卖出",
        "昨收",
        "今开",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "时间戳",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "买入",
            "卖出",
            "昨收",
            "今开",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "时间戳",
        ]
    ]
    return big_df


def stock_zh_a_daily(
    symbol: str = "sh603843",
    start_date: str = "19900101",
    end_date: str = "21000118",
    adjust: str = "",
) -> pd.DataFrame:
    """
    新浪财经-A 股-个股的历史行情数据, 大量抓取容易封 IP
    https://finance.sina.com.cn/realstock/company/sh603843/nc.shtml
    :param symbol: sh600000
    :type symbol: str
    :param start_date: 20201103; 开始日期
    :type start_date: str
    :param end_date: 20201103; 结束日期
    :type end_date: str
    :param adjust: 默认为空: 返回不复权的数据; qfq: 返回前复权后的数据; hfq: 返回后复权后的数据; hfq-factor: 返回后复权因子; qfq-factor: 返回前复权因子
    :type adjust: str
    :return: 行情数据
    :rtype: pandas.DataFrame
    """

    def _fq_factor(method: str) -> pd.DataFrame:
        if method == "hfq":
            r = requests.get(zh_sina_a_stock_hfq_url.format(symbol))
            hfq_factor_df = pd.DataFrame(
                eval(r.text.split("=")[1].split("\n")[0])["data"]
            )
            if hfq_factor_df.shape[0] == 0:
                raise ValueError("sina hfq factor not available")
            hfq_factor_df.columns = ["date", "hfq_factor"]
            hfq_factor_df.index = pd.to_datetime(hfq_factor_df.date)
            del hfq_factor_df["date"]
            hfq_factor_df.reset_index(inplace=True)
            return hfq_factor_df
        else:
            r = requests.get(zh_sina_a_stock_qfq_url.format(symbol))
            qfq_factor_df = pd.DataFrame(
                eval(r.text.split("=")[1].split("\n")[0])["data"]
            )
            if qfq_factor_df.shape[0] == 0:
                raise ValueError("sina hfq factor not available")
            qfq_factor_df.columns = ["date", "qfq_factor"]
            qfq_factor_df.index = pd.to_datetime(qfq_factor_df.date)
            del qfq_factor_df["date"]
            qfq_factor_df.reset_index(inplace=True)
            return qfq_factor_df

    if adjust in ("hfq-factor", "qfq-factor"):
        return _fq_factor(adjust.split("-")[0])

    r = requests.get(zh_sina_a_stock_hist_url.format(symbol))
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call(
        "d", r.text.split("=")[1].split(";")[0].replace('"', "")
    )  # 执行js解密代码
    data_df = pd.DataFrame(dict_list)
    data_df.index = pd.to_datetime(data_df["date"]).dt.date
    del data_df["date"]
    try:
        del data_df["prevclose"]
    except:  # noqa: E722
        pass
    try:
        del data_df["postVol"]
        del data_df["postAmt"]
    except:  # noqa: E722
        pass
    data_df = data_df.astype("float")
    r = requests.get(zh_sina_a_stock_amount_url.format(symbol, symbol))
    amount_data_json = demjson.decode(r.text[r.text.find("[") : r.text.rfind("]") + 1])
    amount_data_df = pd.DataFrame(amount_data_json)
    amount_data_df.columns = ["date", "outstanding_share"]
    amount_data_df.index = pd.to_datetime(amount_data_df.date)
    del amount_data_df["date"]
    temp_df = pd.merge(
        data_df, amount_data_df, left_index=True, right_index=True, how="outer"
    )
    try:
        # try for pandas >= 2.1.0
        temp_df.ffill(inplace=True)
    except Exception:
        try:
            temp_df.fillna(method="ffill", inplace=True)
        except Exception as e:
            print("Error:", e)

    temp_df = temp_df.astype(float)
    temp_df["outstanding_share"] = temp_df["outstanding_share"] * 10000
    temp_df["turnover"] = temp_df["volume"] / temp_df["outstanding_share"]
    temp_df.columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "outstanding_share",
        "turnover",
    ]
    if adjust == "":
        temp_df = temp_df[start_date:end_date]
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume", "amount"], inplace=True
        )
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        return temp_df
    if adjust == "hfq":
        res = requests.get(zh_sina_a_stock_hfq_url.format(symbol))
        hfq_factor_df = pd.DataFrame(
            eval(res.text.split("=")[1].split("\n")[0])["data"]
        )
        hfq_factor_df.columns = ["date", "hfq_factor"]
        hfq_factor_df.index = pd.to_datetime(hfq_factor_df.date)
        del hfq_factor_df["date"]
        temp_df = pd.merge(
            temp_df,
            hfq_factor_df,
            left_index=True,
            right_index=True,
            how="outer",
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
        temp_df = temp_df.astype(float)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume", "amount"], inplace=True
        )
        temp_df["open"] = temp_df["open"] * temp_df["hfq_factor"]
        temp_df["high"] = temp_df["high"] * temp_df["hfq_factor"]
        temp_df["close"] = temp_df["close"] * temp_df["hfq_factor"]
        temp_df["low"] = temp_df["low"] * temp_df["hfq_factor"]
        temp_df = temp_df.iloc[:, :-1]
        temp_df = temp_df[start_date:end_date]
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        return temp_df

    if adjust == "qfq":
        res = requests.get(zh_sina_a_stock_qfq_url.format(symbol))
        qfq_factor_df = pd.DataFrame(
            eval(res.text.split("=")[1].split("\n")[0])["data"]
        )
        qfq_factor_df.columns = ["date", "qfq_factor"]
        qfq_factor_df.index = pd.to_datetime(qfq_factor_df.date)
        del qfq_factor_df["date"]
        temp_df = pd.merge(
            temp_df,
            qfq_factor_df,
            left_index=True,
            right_index=True,
            how="outer",
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
        temp_df = temp_df.astype(float)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume", "amount"], inplace=True
        )
        temp_df["open"] = temp_df["open"] / temp_df["qfq_factor"]
        temp_df["high"] = temp_df["high"] / temp_df["qfq_factor"]
        temp_df["close"] = temp_df["close"] / temp_df["qfq_factor"]
        temp_df["low"] = temp_df["low"] / temp_df["qfq_factor"]
        temp_df = temp_df.iloc[:, :-1]
        temp_df = temp_df[start_date:end_date]
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        return temp_df


def stock_zh_a_cdr_daily(
    symbol: str = "sh689009",
    start_date: str = "19900101",
    end_date: str = "22201116",
) -> pd.DataFrame:
    """
    新浪财经-A股-CDR个股的历史行情数据, 大量抓取容易封 IP
    https://finance.sina.com.cn/realstock/company/sh689009/nc.shtml
    :param start_date: 20201103; 开始日期
    :type start_date: str
    :param end_date: 20201103; 结束日期
    :type end_date: str
    :param symbol: sh689009
    :type symbol: str
    :return: specific data
    :rtype: pandas.DataFrame
    """
    res = requests.get(zh_sina_a_stock_hist_url.format(symbol))
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call(
        "d", res.text.split("=")[1].split(";")[0].replace('"', "")
    )  # 执行js解密代码
    data_df = pd.DataFrame(dict_list)
    data_df.index = pd.to_datetime(data_df["date"])
    del data_df["date"]
    data_df = data_df.astype("float")
    temp_df = data_df[start_date:end_date].copy()
    temp_df["open"] = pd.to_numeric(temp_df["open"])
    temp_df["high"] = pd.to_numeric(temp_df["high"])
    temp_df["low"] = pd.to_numeric(temp_df["low"])
    temp_df["close"] = pd.to_numeric(temp_df["close"])
    temp_df.reset_index(inplace=True)
    temp_df["date"] = temp_df["date"].dt.date
    return temp_df


def stock_zh_a_minute(
    symbol: str = "sh600519", period: str = "1", adjust: str = ""
) -> pd.DataFrame:
    """
    股票及股票指数历史行情数据-分钟数据
    https://finance.sina.com.cn/realstock/company/sh600519/nc.shtml
    :param symbol: sh000300
    :type symbol: str
    :param period: 1, 5, 15, 30, 60 分钟的数据
    :type period: str
    :param adjust: 默认为空: 返回不复权的数据; qfq: 返回前复权后的数据; hfq: 返回后复权后的数据;
    :type adjust: str
    :return: specific data
    :rtype: pandas.DataFrame
    """
    url = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"
    )
    params = {
        "symbol": symbol,
        "scale": period,
        "ma": "no",
        "datalen": "1970",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    try:
        data_json = json.loads(data_text.split("=(")[1].split(");")[0])
        temp_df = pd.DataFrame(data_json).iloc[:, :6]
    except:  # noqa: E722
        url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{symbol}_{period}_1658852984203=/CN_MarketDataService.getKLineData"
        params = {
            "symbol": symbol,
            "scale": period,
            "ma": "no",
            "datalen": "1970",
        }
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = json.loads(data_text.split("=(")[1].split(");")[0])
        temp_df = pd.DataFrame(data_json).iloc[:, :6]
    if temp_df.empty:
        print(f"{symbol} 股票数据不存在，请检查是否已退市")
        return pd.DataFrame()
    try:
        stock_zh_a_daily(symbol=symbol, adjust="qfq")
    except:  # noqa: E722
        return temp_df

    if adjust == "":
        return temp_df

    if adjust == "qfq":
        temp_df[["date", "time"]] = temp_df["day"].str.split(" ", expand=True)
        # 处理没有最后一分钟的情况
        need_df = temp_df[
            [
                True if "09:31:00" <= item <= "15:00:00" else False
                for item in temp_df["time"]
            ]
        ]
        need_df.drop_duplicates(subset=["date"], keep="last", inplace=True)
        need_df.index = pd.to_datetime(need_df["date"])
        stock_zh_a_daily_qfq_df = stock_zh_a_daily(symbol=symbol, adjust="qfq")
        stock_zh_a_daily_qfq_df.index = pd.to_datetime(stock_zh_a_daily_qfq_df["date"])
        result_df = stock_zh_a_daily_qfq_df.iloc[-len(need_df) :, :]["close"].astype(
            float
        ) / need_df["close"].astype(float)
        temp_df.index = pd.to_datetime(temp_df["date"])
        merged_df = pd.merge(temp_df, result_df, left_index=True, right_index=True)
        merged_df["open"] = merged_df["open"].astype(float) * merged_df["close_y"]
        merged_df["high"] = merged_df["high"].astype(float) * merged_df["close_y"]
        merged_df["low"] = merged_df["low"].astype(float) * merged_df["close_y"]
        merged_df["close"] = merged_df["close_x"].astype(float) * merged_df["close_y"]
        temp_df = merged_df[["day", "open", "high", "low", "close", "volume"]]
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df
    if adjust == "hfq":
        temp_df[["date", "time"]] = temp_df["day"].str.split(" ", expand=True)
        # 处理没有最后一分钟的情况
        need_df = temp_df[
            [
                True if "09:31:00" <= item <= "15:00:00" else False
                for item in temp_df["time"]
            ]
        ]
        need_df.drop_duplicates(subset=["date"], keep="last", inplace=True)
        need_df.index = pd.to_datetime(need_df["date"])
        stock_zh_a_daily_hfq_df = stock_zh_a_daily(symbol=symbol, adjust="hfq")
        stock_zh_a_daily_hfq_df.index = pd.to_datetime(stock_zh_a_daily_hfq_df["date"])
        result_df = stock_zh_a_daily_hfq_df.iloc[-len(need_df) :, :]["close"].astype(
            float
        ) / need_df["close"].astype(float)
        temp_df.index = pd.to_datetime(temp_df["date"])
        merged_df = pd.merge(temp_df, result_df, left_index=True, right_index=True)
        merged_df["open"] = merged_df["open"].astype(float) * merged_df["close_y"]
        merged_df["high"] = merged_df["high"].astype(float) * merged_df["close_y"]
        merged_df["low"] = merged_df["low"].astype(float) * merged_df["close_y"]
        merged_df["close"] = merged_df["close_x"].astype(float) * merged_df["close_y"]
        temp_df = merged_df[["day", "open", "high", "low", "close", "volume"]]
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df


if __name__ == "__main__":
    stock_zh_a_daily_hfq_df_one = stock_zh_a_daily(
        symbol="sz000001",
        start_date="19910403",
        end_date="20231027",
        adjust="hfq",
    )
    print(stock_zh_a_daily_hfq_df_one)

    stock_zh_a_daily_hfq_df_three = stock_zh_a_daily(
        symbol="sz000001",
        start_date="19900103",
        end_date="20210118",
        adjust="qfq",
    )
    print(stock_zh_a_daily_hfq_df_three)

    stock_zh_a_daily_hfq_df_two = stock_zh_a_daily(
        symbol="sh000001", start_date="20101103", end_date="20210510"
    )
    print(stock_zh_a_daily_hfq_df_two)

    qfq_factor_df = stock_zh_a_daily(symbol="sz000002", adjust="qfq-factor")
    print(qfq_factor_df)

    hfq_factor_df = stock_zh_a_daily(symbol="sz000002", adjust="hfq-factor")
    print(hfq_factor_df)

    stock_zh_a_daily_hfq_factor_df = stock_zh_a_daily(
        symbol="sz000002", adjust="hfq-factor"
    )
    print(stock_zh_a_daily_hfq_factor_df)

    stock_zh_a_daily_df = stock_zh_a_daily(
        symbol="sz300798", start_date="20200601", end_date="20231101", adjust="hfq"
    )
    print(stock_zh_a_daily_df)

    stock_zh_a_cdr_daily_df = stock_zh_a_cdr_daily(
        symbol="sh689009", start_date="20201103", end_date="20201116"
    )
    print(stock_zh_a_cdr_daily_df)

    stock_zh_a_spot_df = stock_zh_a_spot()
    print(stock_zh_a_spot_df)

    stock_zh_a_minute_df = stock_zh_a_minute(
        symbol="sz000876", period="1", adjust="qfq"
    )
    print(stock_zh_a_minute_df)

    stock_zh_a_minute_df = stock_zh_a_minute(
        symbol="sh600519", period="1", adjust="hfq"
    )
    print(stock_zh_a_minute_df)

    stock_zh_a_cdr_daily_df = stock_zh_a_cdr_daily(
        symbol="sh689009", start_date="19900101", end_date="22201116"
    )
    print(stock_zh_a_cdr_daily_df)
